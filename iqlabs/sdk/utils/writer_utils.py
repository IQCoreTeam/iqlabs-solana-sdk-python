import time
import base64
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.instruction import Instruction
from solders.keypair import Keypair

from ...contract import user_initialize_instruction, InstructionBuilder
from .wallet import to_wallet_signer, WalletSigner

ACCOUNT_CACHE_TTL_MS = 120_000
_account_exists_cache: dict[str, dict] = {}


def _get_cache_key(pubkey: Pubkey) -> str:
    return str(pubkey)


def _read_cache(key: str) -> bool | None:
    entry = _account_exists_cache.get(key)
    if not entry:
        return None
    if time.time() * 1000 > entry["expires_at"]:
        del _account_exists_cache[key]
        return None
    return entry["exists"]


def _write_cache(key: str, exists: bool) -> None:
    _account_exists_cache[key] = {
        "exists": exists,
        "expires_at": time.time() * 1000 + ACCOUNT_CACHE_TTL_MS,
    }


async def get_cached_account_exists(connection: AsyncClient, pubkey: Pubkey) -> bool:
    key = _get_cache_key(pubkey)
    cached = _read_cache(key)
    if cached is not None:
        return cached
    info = await connection.get_account_info(pubkey)
    exists = info.value is not None
    _write_cache(key, exists)
    return exists


async def refresh_account_exists(connection: AsyncClient, pubkey: Pubkey) -> bool:
    key = _get_cache_key(pubkey)
    info = await connection.get_account_info(pubkey)
    exists = info.value is not None
    _write_cache(key, exists)
    return exists


def _mark_account_exists(pubkey: Pubkey, exists: bool = True) -> None:
    _write_cache(_get_cache_key(pubkey), exists)


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
) -> str:
    wallet = to_wallet_signer(signer)
    blockhash_resp = await connection.get_latest_blockhash()
    blockhash = blockhash_resp.value.blockhash

    ix_list = instructions if isinstance(instructions, list) else [instructions]
    tx = Transaction.new_with_payer(ix_list, wallet.public_key)
    tx.recent_blockhash = blockhash

    signed = await wallet.sign_transaction(tx)
    result = await connection.send_raw_transaction(bytes(signed))
    signature = str(result.value)

    await connection.confirm_transaction(signature)
    return signature


async def ensure_user_initialized(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    builder: InstructionBuilder,
    accounts: dict[str, Pubkey],
) -> None:
    exists = await get_cached_account_exists(connection, accounts["user_inventory"])
    if not exists:
        exists = await refresh_account_exists(connection, accounts["user_inventory"])
    if exists:
        return
    ix = user_initialize_instruction(builder, accounts)
    await send_tx(connection, signer, ix)
    _mark_account_exists(accounts["user_inventory"], True)
