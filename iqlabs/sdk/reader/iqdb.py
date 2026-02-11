from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from ...coder import decode_account
from ...contract import (
    CONNECTION_STATUS_APPROVED,
    CONNECTION_STATUS_BLOCKED,
    CONNECTION_STATUS_PENDING,
    get_connection_table_pda,
    get_db_root_pda,
)
from ...constants import DEFAULT_CONTRACT_MODE
from ..utils.connection_helper import get_connection
from ..utils.global_fetch import decode_connection_meta
from ..utils.rate_limiter import create_rate_limiter
from ..utils.session_speed import resolve_session_speed, SESSION_SPEED_PROFILES
from ..utils.seed import derive_dm_seed, to_seed_bytes
from .read_code_in import read_code_in
from .reader_context import resolve_reader_program_id
from .reader_utils import fetch_account_transactions


def _resolve_connection_status(status: int) -> str:
    if status == CONNECTION_STATUS_PENDING:
        return "pending"
    if status == CONNECTION_STATUS_APPROVED:
        return "approved"
    if status == CONNECTION_STATUS_BLOCKED:
        return "blocked"
    return "unknown"


async def read_connection(
    db_root_id: bytes | str,
    party_a: str,
    party_b: str,
    mode: str = DEFAULT_CONTRACT_MODE,
) -> dict:
    connection = get_connection()
    db_root_seed = to_seed_bytes(db_root_id)
    program_id = resolve_reader_program_id(mode)
    db_root = get_db_root_pda(db_root_seed, program_id)
    connection_seed = derive_dm_seed(party_a, party_b)
    connection_table = get_connection_table_pda(db_root, connection_seed, program_id)

    info = await connection.get_account_info(connection_table)
    if not info.value:
        raise ValueError("connection table not found")

    meta = decode_connection_meta(bytes(info.value.data))
    status = _resolve_connection_status(meta["status"])
    requester = "a" if meta["requester"] == 0 else "b"
    blocker = "a" if meta["blocker"] == 0 else "b" if meta["blocker"] == 1 else "none"

    return {"status": status, "requester": requester, "blocker": blocker}


async def get_tablelist_from_root(
    connection: AsyncClient,
    db_root_id: bytes | str,
    mode: str = DEFAULT_CONTRACT_MODE,
) -> dict:
    program_id = resolve_reader_program_id(mode)
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)

    info = await connection.get_account_info(db_root)
    if not info.value:
        return {
            "root_pda": db_root,
            "creator": None,
            "table_seeds": [],
            "global_table_seeds": [],
        }

    decoded = decode_account("DbRoot", bytes(info.value.data))
    if not decoded:
        return {
            "root_pda": db_root,
            "creator": None,
            "table_seeds": [],
            "global_table_seeds": [],
        }
    creator = str(decoded["creator"]) if decoded.get("creator") else None
    table_seeds = [v.hex() for v in decoded.get("table_seeds", [])]
    global_table_seeds = [v.hex() for v in decoded.get("global_table_seeds", [])]

    return {
        "root_pda": db_root,
        "creator": creator,
        "table_seeds": table_seeds,
        "global_table_seeds": global_table_seeds,
    }


async def read_table_rows(
    account: Pubkey | str,
    before: str | None = None,
    limit: int | None = None,
    speed: str | None = None,
) -> list[dict]:
    signatures = await fetch_account_transactions(account, before=before, limit=limit)
    speed_key = resolve_session_speed(speed)
    limiter = create_rate_limiter(SESSION_SPEED_PROFILES[speed_key]["max_rps"])
    rows = []

    for sig in signatures:
        if limiter:
            await limiter.wait()
        try:
            result = await read_code_in(sig.signature, speed)
        except ValueError as err:
            if "user_inventory_code_in instruction not found" in str(err):
                continue
            raise

        data = result["data"]
        metadata = result["metadata"]
        if not data:
            rows.append({"signature": sig.signature, "metadata": metadata, "data": None})
            continue

        try:
            import json
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                rows.append({**parsed, "__tx_signature": sig.signature})
                continue
        except Exception:
            pass
        rows.append({"signature": sig.signature, "metadata": metadata, "data": data})

    return rows
