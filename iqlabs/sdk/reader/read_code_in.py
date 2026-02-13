from typing import Callable

from ..utils.connection_helper import get_connection
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
    return await read_user_inventory_code_in_from_tx(tx, speed, on_progress)
