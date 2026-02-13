import json
from typing import Callable

from solders.pubkey import Pubkey

from ...coder import decode_account
from ...contract import get_user_inventory_pda, get_user_pda
from ..utils.connection_helper import get_connection, get_reader_connection
from .reader_profile import resolve_read_mode
from .reading_methods import read_linked_list_result, read_session_result
from .reader_context import reader_context
from .reader_utils import decode_user_inventory_code_in, extract_code_in_payload, fetch_account_transactions

SIG_MIN_LEN = 80


async def read_inventory_metadata(tx_signature: str) -> dict:
    connection = get_connection()
    resp = await connection.get_transaction(tx_signature, max_supported_transaction_version=0)
    if not resp.value:
        raise ValueError("transaction not found")
    return decode_user_inventory_code_in(resp.value)


async def fetch_inventory_transactions(public_key: Pubkey, limit: int, before: str | None = None) -> list:
    inventory_pda = get_user_inventory_pda(public_key)
    signatures = await fetch_account_transactions(inventory_pda, limit=limit, before=before)
    with_metadata = []
    for sig in signatures:
        try:
            inventory_metadata = await read_inventory_metadata(sig.signature)
            with_metadata.append({**sig.__dict__, **inventory_metadata})
        except ValueError as err:
            if "user_inventory_code_in instruction not found" in str(err):
                continue
            raise
    return with_metadata


async def read_session(
    session_pubkey: str,
    read_option: dict,
    speed: str | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict:
    connection = get_reader_connection(read_option.get("freshness"))
    info = await connection.get_account_info(Pubkey.from_string(session_pubkey))
    if not info.value:
        raise ValueError("session account not found")
    return await read_session_result(session_pubkey, read_option, speed, on_progress)


async def read_linked_list_from_tail(
    tail_tx: str,
    read_option: dict,
    on_progress: Callable[[int], None] | None = None,
    expected_total_chunks: int | None = None,
) -> dict:
    connection = get_reader_connection(read_option.get("freshness"))
    resp = await connection.get_transaction(tail_tx, max_supported_transaction_version=0)
    if not resp.value:
        raise ValueError("tail transaction not found")
    return await read_linked_list_result(tail_tx, read_option, on_progress, expected_total_chunks)


async def read_user_inventory_code_in_from_tx(
    tx,
    speed: str | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict:
    block_time = tx.block_time
    payload = extract_code_in_payload(tx)
    on_chain_path = payload["on_chain_path"]
    metadata = payload["metadata"]
    inline_data = payload["inline_data"]

    total_chunks = None
    try:
        parsed = json.loads(metadata)
        raw_total = parsed.get("total_chunks")
        if isinstance(raw_total, (int, float)) and not isinstance(raw_total, bool):
            total_chunks = int(raw_total)
        elif isinstance(raw_total, str):
            total_chunks = int(raw_total)
    except Exception:
        pass

    if len(on_chain_path) == 0:
        if on_progress:
            on_progress(100)
        return {"metadata": metadata, "data": inline_data}

    read_option = resolve_read_mode(on_chain_path, block_time)
    kind = "linked_list" if len(on_chain_path) >= SIG_MIN_LEN else "session"

    if kind == "session":
        result = await read_session(on_chain_path, read_option, speed, on_progress)
        return {"metadata": metadata, "data": result["result"]}

    result = await read_linked_list_from_tail(on_chain_path, read_option, on_progress, total_chunks)
    return {"metadata": metadata, "data": result["result"]}


async def read_user_state(user_pubkey: str) -> dict:
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
    raw_metadata = decoded["metadata"].decode("utf-8")
    metadata = raw_metadata.rstrip("\x00").strip() or None
    total_session_files = int(decoded["total_session_files"])

    if metadata:
        from .read_code_in import read_code_in
        result = await read_code_in(metadata)
        profile_data = result["data"]
        return {
            "owner": str(decoded["owner"]),
            "metadata": metadata,
            "total_session_files": total_session_files,
            "profile_data": profile_data,
        }

    return {
        "owner": str(decoded["owner"]),
        "metadata": None,
        "total_session_files": total_session_files,
    }
