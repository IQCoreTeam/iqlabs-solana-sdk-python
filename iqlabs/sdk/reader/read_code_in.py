from typing import Callable

from ...contract import resolve_contract_runtime
from ..utils.connection_helper import get_connection
from .reader_context import resolve_reader_mode_from_tx
from .reading_flow import read_user_inventory_code_in_from_tx


async def read_code_in(
    tx_signature: str,
    speed: str | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict:
    connection = get_connection()
    resp = await connection.get_transaction(tx_signature, max_supported_transaction_version=0)
    if not resp.value:
        raise ValueError("transaction not found")

    tx = resp.value
    user_mode = resolve_contract_runtime()
    resolved_mode = resolve_reader_mode_from_tx(tx) or user_mode
    return await read_user_inventory_code_in_from_tx(tx, speed, resolved_mode, on_progress)
