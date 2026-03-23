from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from ...coder import decode_account
from ...contract import (
    CONNECTION_BLOCKER_NONE,
    CONNECTION_STATUS_APPROVED,
    CONNECTION_STATUS_BLOCKED,
    CONNECTION_STATUS_PENDING,
    get_connection_table_pda,
    get_db_root_pda,
    get_table_pda,
)
from .seed import to_seed_bytes


def decode_table_meta(data: bytes) -> dict:
    decoded = decode_account("Table", data)
    if not decoded:
        raise ValueError("Failed to decode Table account")
    return {
        "columns": [v.decode("utf-8").rstrip("\x00") for v in decoded["column_names"]],
        "id_col": decoded["id_col"].decode("utf-8").rstrip("\x00"),
        "gate": decoded["gate"],
        "writers": decoded["writers"],
    }


def decode_connection_meta(data: bytes) -> dict:
    decoded = decode_account("Connection", data)
    if not decoded:
        raise ValueError("Failed to decode Connection account")
    return {
        "db_root_id": decoded["db_root_id"].decode("utf-8").rstrip("\x00"),
        "columns": [v.decode("utf-8").rstrip("\x00") for v in decoded["column_names"]],
        "id_col": decoded["id_col"].decode("utf-8").rstrip("\x00"),
        "ext_keys": [v.decode("utf-8").rstrip("\x00") for v in decoded["ext_keys"]],
        "name": decoded["name"].decode("utf-8").rstrip("\x00"),
        "gate": decoded["gate"],
        "party_a": decoded["party_a"],
        "party_b": decoded["party_b"],
        "status": decoded["status"],
        "requester": decoded["requester"],
        "blocker": decoded["blocker"],
    }


async def ensure_db_root_exists(connection: AsyncClient, program_id: Pubkey, db_root_id: bytes | str) -> None:
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)
    info = await connection.get_account_info(db_root)
    if not info.value:
        raise ValueError("db_root not found")


async def ensure_table_exists(
    connection: AsyncClient,
    program_id: Pubkey,
    db_root_id: bytes | str,
    table_seed: bytes | str,
) -> dict:
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)
    table_seed_bytes = to_seed_bytes(table_seed)
    table_pda = get_table_pda(db_root, table_seed_bytes, program_id)
    table_info = await connection.get_account_info(table_pda)
    if not table_info.value:
        raise ValueError("table not found")
    return {"table_pda": table_pda}


async def fetch_table_meta(
    connection: AsyncClient,
    program_id: Pubkey,
    db_root_id: bytes | str,
    table_seed: bytes | str,
) -> dict:
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)
    table_seed_bytes = to_seed_bytes(table_seed)
    table_pda = get_table_pda(db_root, table_seed_bytes, program_id)
    info = await connection.get_account_info(table_pda)
    if not info.value:
        raise ValueError("table not found")
    return decode_table_meta(bytes(info.value.data))


async def fetch_connection_meta(
    connection: AsyncClient,
    program_id: Pubkey,
    db_root_id: bytes | str,
    connection_seed: bytes | str,
) -> dict:
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)
    connection_seed_bytes = to_seed_bytes(connection_seed)
    connection_table = get_connection_table_pda(db_root, connection_seed_bytes, program_id)
    info = await connection.get_account_info(connection_table)
    if not info.value:
        raise ValueError("connection table not found")
    return decode_connection_meta(bytes(info.value.data))


def resolve_connection_status(status: int) -> str:
    if status == CONNECTION_STATUS_PENDING:
        return "pending"
    if status == CONNECTION_STATUS_APPROVED:
        return "approved"
    if status == CONNECTION_STATUS_BLOCKED:
        return "blocked"
    return "unknown"


def evaluate_connection_access(meta: dict, signer: Pubkey) -> dict:
    status = resolve_connection_status(meta["status"])

    signer_idx = -1
    if signer == meta["party_a"]:
        signer_idx = 0
    elif signer == meta["party_b"]:
        signer_idx = 1
    else:
        return {"allowed": False, "status": status, "message": "signer is not a connection participant"}

    if meta["status"] == CONNECTION_STATUS_APPROVED:
        return {"allowed": True, "status": status}
    if meta["status"] == CONNECTION_STATUS_PENDING:
        if signer_idx == meta["requester"]:
            return {"allowed": True, "status": status}
        return {"allowed": False, "status": status, "message": "Allow the connection in settings."}
    if meta["status"] == CONNECTION_STATUS_BLOCKED:
        blocker_idx = None if meta["blocker"] == CONNECTION_BLOCKER_NONE else meta["blocker"]
        message = (
            "Allow the connection in settings."
            if blocker_idx == signer_idx
            else "Ask the other party to unblock the connection."
        )
        return {"allowed": False, "status": status, "message": message}

    return {"allowed": False, "status": status, "message": "invalid connection status"}
