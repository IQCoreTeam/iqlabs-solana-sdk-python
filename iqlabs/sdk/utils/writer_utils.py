import time
import base64
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.instruction import Instruction
from solders.keypair import Keypair

from ...contract import realloc_account_instruction, user_initialize_instruction, InstructionBuilder
from ..constants import CODE_ACCOUNT_SPACE, USER_INVENTORY_SPACE
from .tx_profile import extract_keypair, resolve_tx_profile, should_send_v1
from .v1_tx import send_tx_v1
from .wallet import to_wallet_signer, WalletSigner

ACCOUNT_CACHE_TTL_MS = 120_000
_account_state_cache: dict[str, dict] = {}


def _get_cache_key(pubkey: Pubkey) -> str:
    return str(pubkey)


def _read_cache(key: str) -> dict | None:
    entry = _account_state_cache.get(key)
    if not entry:
        return None
    if time.time() * 1000 > entry["expires_at"]:
        del _account_state_cache[key]
        return None
    return {"exists": entry["exists"], "data_len": entry["data_len"]}


def _write_cache(key: str, exists: bool, data_len: int = 0) -> None:
    _account_state_cache[key] = {
        "exists": exists,
        "data_len": data_len,
        "expires_at": time.time() * 1000 + ACCOUNT_CACHE_TTL_MS,
    }


def _to_state(value) -> dict:
    return {
        "exists": value is not None,
        "data_len": len(value.data) if value is not None else 0,
    }


async def _refresh_user_accounts_state(
    connection: AsyncClient,
    code_account: Pubkey,
    user_inventory: Pubkey,
) -> dict:
    # Both per-user PDAs in one RPC call; the response already carries the data
    # (and thus the size), which the realloc check below rides on for free.
    resp = await connection.get_multiple_accounts([code_account, user_inventory])
    code_info, inventory_info = resp.value[0], resp.value[1]
    state = {"code": _to_state(code_info), "inventory": _to_state(inventory_info)}
    _write_cache(_get_cache_key(code_account), state["code"]["exists"], state["code"]["data_len"])
    _write_cache(_get_cache_key(user_inventory), state["inventory"]["exists"], state["inventory"]["data_len"])
    return state


async def _get_cached_user_accounts_state(
    connection: AsyncClient,
    code_account: Pubkey,
    user_inventory: Pubkey,
) -> dict:
    code = _read_cache(_get_cache_key(code_account))
    inventory = _read_cache(_get_cache_key(user_inventory))
    if code and inventory:
        return {"code": code, "inventory": inventory}
    return await _refresh_user_accounts_state(connection, code_account, user_inventory)


async def get_cached_account_exists(connection: AsyncClient, pubkey: Pubkey) -> bool:
    key = _get_cache_key(pubkey)
    cached = _read_cache(key)
    if cached is not None:
        return cached["exists"]
    info = await connection.get_account_info(pubkey)
    state = _to_state(info.value)
    _write_cache(key, state["exists"], state["data_len"])
    return state["exists"]


async def refresh_account_exists(connection: AsyncClient, pubkey: Pubkey) -> bool:
    key = _get_cache_key(pubkey)
    info = await connection.get_account_info(pubkey)
    state = _to_state(info.value)
    _write_cache(key, state["exists"], state["data_len"])
    return state["exists"]


MAGIC_SIGNATURES = [
    {"ext": "png", "mime": "image/png", "bytes": [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]},
    {"ext": "jpg", "mime": "image/jpeg", "bytes": [0xFF, 0xD8, 0xFF]},
    {"ext": "gif", "mime": "image/gif", "bytes": [0x47, 0x49, 0x46, 0x38]},
    {"ext": "pdf", "mime": "application/pdf", "bytes": [0x25, 0x50, 0x44, 0x46, 0x2D]},
    {"ext": "zip", "mime": "application/zip", "bytes": [0x50, 0x4B, 0x03, 0x04]},
]


def _looks_base64(value: str) -> bool:
    trimmed = value.strip()
    import re
    return len(trimmed) % 4 == 0 and bool(re.match(r"^[A-Za-z0-9+/=]+$", trimmed))


def _to_bytes(value: str) -> bytes:
    if _looks_base64(value):
        try:
            decoded = base64.b64decode(value)
            if decoded:
                return decoded
        except Exception:
            pass
    return value.encode("utf-8")


def _starts_with(data: bytes, sig_bytes: list[int]) -> bool:
    if len(data) < len(sig_bytes):
        return False
    return all(data[i] == sig_bytes[i] for i in range(len(sig_bytes)))


def _is_webp(data: bytes) -> bool:
    if len(data) < 12:
        return False
    return (
        data[0] == 0x52
        and data[1] == 0x49
        and data[2] == 0x46
        and data[3] == 0x46
        and data[8] == 0x57
        and data[9] == 0x45
        and data[10] == 0x42
        and data[11] == 0x50
    )


def _is_mp4(data: bytes) -> bool:
    if len(data) < 12:
        return False
    return data[4] == 0x66 and data[5] == 0x74 and data[6] == 0x79 and data[7] == 0x70


def read_magic_bytes(chunk: str) -> dict:
    data = _to_bytes(chunk)
    for sig in MAGIC_SIGNATURES:
        if _starts_with(data, sig["bytes"]):
            return {"ext": sig["ext"], "mime": sig["mime"]}
    if _is_webp(data):
        return {"ext": "webp", "mime": "image/webp"}
    if _is_mp4(data):
        return {"ext": "mp4", "mime": "video/mp4"}
    return {"ext": "bin", "mime": "application/octet-stream"}


async def send_tx(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    instructions: Instruction | list[Instruction],
    skip_confirmation: bool = False,
) -> str:
    from solders.message import Message

    # The v1 decision stays internal: the feature-gate lookup is cached per
    # endpoint, so callers never need to carry a profile around.
    if await should_send_v1(connection, signer):
        ix_list = instructions if isinstance(instructions, list) else [instructions]
        return await send_tx_v1(connection, extract_keypair(signer), ix_list, skip_confirmation)

    wallet = to_wallet_signer(signer)
    blockhash_resp = await connection.get_latest_blockhash()
    blockhash = blockhash_resp.value.blockhash

    ix_list = instructions if isinstance(instructions, list) else [instructions]

    # Use Message.new_with_blockhash for solders >= 0.23
    msg = Message.new_with_blockhash(ix_list, wallet.public_key, blockhash)

    # Get the actual keypair from wallet
    if hasattr(wallet, '_keypair'):
        kp = wallet._keypair
    else:
        kp = signer  # Fallback to original signer if it's a Keypair

    tx = Transaction([kp], msg, blockhash)

    try:
        raw = bytes(tx)
    except Exception as e:
        if "too large" in str(e).lower():
            raise ValueError(
                "Transaction size exceeded. "
                "If you are passing many remaining_accounts, reduce the number of accounts "
                "or store data via inscription and pass the txid instead."
            ) from e
        raise

    result = await connection.send_raw_transaction(raw)
    signature = result.value

    if not skip_confirmation:
        await connection.confirm_transaction(signature)
    return str(signature)


async def send_tx_with_retries(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    instructions: Instruction | list[Instruction],
    skip_confirmation: bool = False,
    max_retries: int = 10,
    retry_delay_ms: int = 1500,
) -> str:
    """Retry-wrapped send_tx for unstable chunk uploads under high concurrency."""
    import asyncio

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await send_tx(connection, signer, instructions, skip_confirmation)
        except Exception as error:
            last_error = error
            if attempt == max_retries:
                break
            delay = (retry_delay_ms * (attempt + 1)) / 1000.0
            print(
                f"[send_tx_with_retries] Attempt {attempt + 1}/{max_retries + 1} failed. "
                f"Retrying in {delay}s... {error}"
            )
            await asyncio.sleep(delay)

    print(f"[send_tx_with_retries] Failed after {max_retries + 1} attempts")
    raise last_error if last_error else RuntimeError("Unknown transaction error after retries")


async def ensure_user_initialized(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    builder: InstructionBuilder,
    accounts: dict[str, Pubkey],
) -> None:
    state = await _get_cached_user_accounts_state(
        connection, accounts["code_account"], accounts["user_inventory"]
    )
    if not state["inventory"]["exists"]:
        state = await _refresh_user_accounts_state(
            connection, accounts["code_account"], accounts["user_inventory"]
        )

    if not state["inventory"]["exists"]:
        ix = user_initialize_instruction(builder, accounts)
        await send_tx(connection, signer, ix)
        # The upgraded program creates full-size accounts; the pre-upgrade one
        # still creates the 900-byte layout, which the realloc pass below
        # catches on this refresh.
        state = await _refresh_user_accounts_state(
            connection, accounts["code_account"], accounts["user_inventory"]
        )

    # Account size doubles as the layout version marker: anything below the
    # v1 sizes is a pre-upgrade account and gets grown (both accounts in one
    # tx, rent paid by the user) before the first v1-profile write. Legacy
    # profile writes fit the old layout, so nothing is grown there.
    profile = await resolve_tx_profile(connection, signer)
    if profile.version != "v1":
        return

    reallocs: list[Instruction] = []
    if state["code"]["exists"] and state["code"]["data_len"] < CODE_ACCOUNT_SPACE:
        reallocs.append(
            realloc_account_instruction(
                builder,
                {
                    "payer": accounts["user"],
                    "target": accounts["code_account"],
                    "system_program": accounts.get("system_program"),
                },
                {"new_size": CODE_ACCOUNT_SPACE},
            )
        )
    if state["inventory"]["exists"] and state["inventory"]["data_len"] < USER_INVENTORY_SPACE:
        reallocs.append(
            realloc_account_instruction(
                builder,
                {
                    "payer": accounts["user"],
                    "target": accounts["user_inventory"],
                    "system_program": accounts.get("system_program"),
                },
                {"new_size": USER_INVENTORY_SPACE},
            )
        )
    if not reallocs:
        return
    await send_tx(connection, signer, reallocs)
    await _refresh_user_accounts_state(
        connection, accounts["code_account"], accounts["user_inventory"]
    )
