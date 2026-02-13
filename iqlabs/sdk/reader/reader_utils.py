import json
from typing import Any

from solders.pubkey import Pubkey

from ...coder import decode_account, decode_instruction
from ...contract import get_session_pda, get_user_pda
from ..utils.connection_helper import get_connection
from ..utils.rate_limiter import create_rate_limiter
from ..utils.session_speed import resolve_session_speed, SESSION_SPEED_PROFILES
from .reader_context import reader_context


def decode_reader_instruction(ix, account_keys: list[Pubkey]) -> dict | None:
    program_id = account_keys[ix.program_id_index]
    if program_id != reader_context.anchor_program_id:
        return None
    try:
        return decode_instruction(bytes(ix.data))
    except Exception:
        return None


def decode_user_inventory_code_in(tx) -> dict:
    message = tx.transaction.message
    account_keys = message.account_keys

    for ix in message.instructions:
        decoded = decode_reader_instruction(ix, account_keys)
        if not decoded:
            continue
        if decoded["name"] in (
            "user_inventory_code_in",
            "user_inventory_code_in_for_free",
            "db_code_in",
            "db_instruction_code_in",
            "wallet_connection_code_in",
        ):
            data = decoded["data"]
            return {"on_chain_path": data.get("on_chain_path", ""), "metadata": data.get("metadata", "")}

    raise ValueError("user_inventory_code_in instruction not found")


def extract_code_in_payload(tx) -> dict:
    decoded = decode_user_inventory_code_in(tx)
    on_chain_path = decoded["on_chain_path"]
    metadata = decoded["metadata"]

    if on_chain_path:
        return {"on_chain_path": on_chain_path, "metadata": metadata, "inline_data": None}

    data = None
    cleaned_metadata = metadata
    try:
        parsed = json.loads(metadata)
        if isinstance(parsed, dict) and "data" in parsed:
            data_value = parsed.pop("data")
            cleaned_metadata = json.dumps(parsed)
            if isinstance(data_value, str):
                data = data_value
            elif data_value is not None:
                data = json.dumps(data_value)
    except Exception:
        pass

    return {"on_chain_path": on_chain_path, "metadata": cleaned_metadata, "inline_data": data}


async def fetch_account_transactions(account: str | Pubkey, before: str | None = None, limit: int | None = None) -> list:
    if limit is not None and limit <= 0:
        return []
    pubkey = Pubkey.from_string(account) if isinstance(account, str) else account
    connection = get_connection()
    resp = await connection.get_signatures_for_address(pubkey, before=before, limit=limit)
    return resp.value


async def get_session_pda_list(user_pubkey: str) -> list[str]:
    connection = get_connection()
    user = Pubkey.from_string(user_pubkey)
    program_id = reader_context.anchor_program_id
    user_state = get_user_pda(user, program_id)
    info = await connection.get_account_info(user_state)
    if not info.value:
        raise ValueError("user_state not found")

    decoded = decode_account("UserState", bytes(info.value.data))
    if not decoded:
        raise ValueError("Failed to decode UserState account")
    total_session_files = int(decoded["total_session_files"])
    sessions = []
    for seq in range(total_session_files):
        session = get_session_pda(user, seq, program_id)
        sessions.append(str(session))
    return sessions


async def fetch_user_connections(
    user_pubkey: Pubkey | str,
    limit: int | None = None,
    before: str | None = None,
    speed: str | None = None,
) -> list[dict]:
    from ..utils.global_fetch import decode_connection_meta

    program_id = reader_context.anchor_program_id
    pubkey = Pubkey.from_string(user_pubkey) if isinstance(user_pubkey, str) else user_pubkey
    user_state = get_user_pda(pubkey, program_id)

    signatures = await fetch_account_transactions(user_state, before=before, limit=limit)

    speed_key = resolve_session_speed(speed)
    profile = SESSION_SPEED_PROFILES[speed_key]
    rate_limiter = create_rate_limiter(profile["max_rps"])

    connection_pda_set = set()
    connection_pda_data = []
    connection = get_connection()

    for sig in signatures:
        if rate_limiter:
            await rate_limiter.wait()
        try:
            resp = await connection.get_transaction(sig.signature, max_supported_transaction_version=0)
            tx = resp.value
        except Exception:
            continue
        if not tx:
            continue

        message = tx.transaction.message
        account_keys = message.account_keys

        for ix in message.instructions:
            decoded = decode_reader_instruction(ix, account_keys)
            if not decoded or decoded["name"] != "request_connection":
                continue
            connection_table_pubkey = account_keys[ix.accounts[2]]
            pda_key = str(connection_table_pubkey)
            if pda_key not in connection_pda_set:
                connection_pda_set.add(pda_key)
                connection_pda_data.append({
                    "connection_pda": connection_table_pubkey,
                    "timestamp": sig.block_time,
                })

    connections = []
    for item in connection_pda_data:
        if rate_limiter:
            await rate_limiter.wait()
        try:
            info = await connection.get_account_info(item["connection_pda"])
            if not info.value:
                continue
            meta = decode_connection_meta(bytes(info.value.data))
            party_a = str(meta["party_a"])
            party_b = str(meta["party_b"])

            status_num = meta["status"]
            status = "pending" if status_num == 0 else "approved" if status_num == 1 else "blocked" if status_num == 2 else "pending"
            requester = "a" if meta["requester"] == 0 else "b"
            blocker = "a" if meta["blocker"] == 0 else "b" if meta["blocker"] == 1 else "none"

            connections.append({
                "db_root_id": meta["db_root_id"],
                "connection_pda": str(item["connection_pda"]),
                "party_a": party_a,
                "party_b": party_b,
                "status": status,
                "requester": requester,
                "blocker": blocker,
                "timestamp": item["timestamp"],
            })
        except Exception:
            continue

    return connections
