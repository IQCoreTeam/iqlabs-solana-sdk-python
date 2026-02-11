import time

from ...constants import DEFAULT_CONTRACT_MODE
from ..utils.connection_helper import get_connection
from .reader_context import resolve_reader_mode_from_tx
from .reader_utils import decode_reader_instruction
from ...contract import resolve_contract_runtime

DAY_SECONDS = 86_400
WEEK_SECONDS = 7 * DAY_SECONDS
SIG_MIN_LEN = 80


def _resolve_on_chain_path(tx, mode: str = DEFAULT_CONTRACT_MODE) -> str:
    message = tx.transaction.message
    account_keys = message.account_keys
    user_mode = resolve_contract_runtime(mode)
    resolved_mode = resolve_reader_mode_from_tx(tx) or user_mode

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
            return decoded["data"].get("on_chain_path", "")

    raise ValueError("user_inventory_code_in instruction not found")


def resolve_read_mode(on_chain_path: str, block_time: int | None = None) -> dict:
    now = int(time.time())
    age_seconds = max(0, now - block_time) if block_time is not None else None

    if len(on_chain_path) == 0:
        freshness = "fresh" if age_seconds is not None and age_seconds <= DAY_SECONDS else "recent"
        return {"freshness": freshness}

    kind = "linked_list" if len(on_chain_path) >= SIG_MIN_LEN else "session"

    if kind == "linked_list":
        freshness = "fresh" if age_seconds is not None and age_seconds <= DAY_SECONDS else "recent"
        return {"freshness": freshness}

    if age_seconds is not None and age_seconds <= DAY_SECONDS:
        return {"freshness": "fresh"}
    if age_seconds is not None and age_seconds <= WEEK_SECONDS:
        return {"freshness": "recent"}
    return {"freshness": "archive"}


async def decide_read_mode(tx_signature: str, mode: str = DEFAULT_CONTRACT_MODE) -> dict:
    connection = get_connection()
    resp = await connection.get_transaction(tx_signature, max_supported_transaction_version=0)
    if not resp.value:
        raise ValueError("transaction not found")
    tx = resp.value
    on_chain_path = _resolve_on_chain_path(tx, mode)
    return resolve_read_mode(on_chain_path, tx.block_time)
