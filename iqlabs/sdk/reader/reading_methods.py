from typing import Callable, Awaitable

from solders.pubkey import Pubkey

from ..utils.connection_helper import get_reader_connection
from ..utils.rpc_client import RpcClient
from ..utils.concurrency import run_with_concurrency
from ..utils.rate_limiter import create_rate_limiter
from ..utils.session_speed import SESSION_SPEED_PROFILES, resolve_session_speed
from .reader_utils import decode_reader_instruction


def _resolve_session_config(speed: str | None = None) -> dict:
    resolved_speed = resolve_session_speed(speed)
    return SESSION_SPEED_PROFILES[resolved_speed]


def _extract_anchor_instruction(tx, expected_name: str) -> dict | None:
    message = tx.transaction.message
    account_keys = message.account_keys

    for ix in message.instructions:
        decoded = decode_reader_instruction(ix, account_keys)
        if not decoded:
            continue
        if decoded["name"] == expected_name:
            return decoded["data"]
    return None


def _extract_post_chunk(tx) -> list[dict]:
    message = tx.transaction.message
    account_keys = message.account_keys
    chunks = []

    for ix in message.instructions:
        decoded = decode_reader_instruction(ix, account_keys)
        if decoded and decoded["name"] == "post_chunk":
            data = decoded["data"]
            chunks.append({"index": data["index"], "chunk": data["chunk"]})

    return chunks


def _extract_send_code(tx) -> dict | None:
    data = _extract_anchor_instruction(tx, "send_code")
    if not data:
        return None
    return {"code": data["code"], "before_tx": data["before_tx"]}


async def read_session_result(
    session_pubkey: str,
    read_option: dict,
    speed: str | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict:
    connection = get_reader_connection(read_option.get("freshness"))
    rpc_client = RpcClient(connection=connection)
    session_key = Pubkey.from_string(session_pubkey)

    # Try Helius enhanced first
    helius_transactions = await rpc_client.try_fetch_transactions_for_address_all(
        session_key, max_supported_transaction_version=0
    )
    if helius_transactions:
        chunk_map = {}
        total_txs = len(helius_transactions)
        completed = 0
        last_percent = -1
        if on_progress:
            on_progress(0)
            last_percent = 0

        for tx in helius_transactions:
            if not tx:
                continue
            chunks = _extract_post_chunk(tx)
            for chunk in chunks:
                chunk_map[chunk["index"]] = chunk["chunk"]
            completed += 1
            if on_progress and total_txs > 0:
                percent = (completed * 100) // total_txs
                if percent != last_percent:
                    last_percent = percent
                    on_progress(percent)

        if not chunk_map:
            raise ValueError("no session chunks found")
        result = "".join(chunk for _, chunk in sorted(chunk_map.items()))
        if on_progress and total_txs > 0 and last_percent < 100:
            on_progress(100)
        return {"result": result}

    # Fallback to standard pagination
    signatures = []
    before = None
    while True:
        resp = await connection.get_signatures_for_address(session_key, before=before, limit=1000)
        page = resp.value
        if not page:
            break
        signatures.extend(page)
        if len(page) < 1000:
            break
        next_before = page[-1].signature
        if not next_before or next_before == before:
            break
        before = next_before

    chunk_map = {}
    session_config = _resolve_session_config(speed)
    limiter = create_rate_limiter(session_config["max_rps"])
    max_concurrency = session_config["max_concurrency"]
    total_signatures = len(signatures)
    completed = [0]
    last_percent = [-1]
    if on_progress:
        on_progress(0)
        last_percent[0] = 0

    async def worker(entry, _index):
        if limiter:
            await limiter.wait()
        resp = await connection.get_transaction(entry.signature, max_supported_transaction_version=0)
        tx = resp.value
        if not tx:
            return
        chunks = _extract_post_chunk(tx)
        for chunk in chunks:
            chunk_map[chunk["index"]] = chunk["chunk"]
        completed[0] += 1
        if on_progress and total_signatures > 0:
            percent = (completed[0] * 100) // total_signatures
            if percent != last_percent[0]:
                last_percent[0] = percent
                on_progress(percent)

    await run_with_concurrency(signatures, max_concurrency, worker)

    if not chunk_map:
        raise ValueError("no session chunks found")
    result = "".join(chunk for _, chunk in sorted(chunk_map.items()))
    if on_progress and total_signatures > 0 and last_percent[0] < 100:
        on_progress(100)

    return {"result": result}


async def read_linked_list_result(
    tail_tx: str,
    read_option: dict,
    on_progress: Callable[[int], None] | None = None,
    expected_total_chunks: int | None = None,
) -> dict:
    connection = get_reader_connection(read_option.get("freshness"))
    chunks = []
    visited = set()
    cursor = tail_tx
    total_chunks = expected_total_chunks or 0
    processed = 0
    last_percent = -1
    if on_progress:
        on_progress(0)
        last_percent = 0

    while cursor and cursor != "Genesis":
        if cursor in visited:
            raise ValueError("linked list loop detected")
        visited.add(cursor)

        resp = await connection.get_transaction(cursor, max_supported_transaction_version=0)
        tx = resp.value
        if not tx:
            raise ValueError("linked list transaction not found")

        decoded = _extract_send_code(tx)
        if not decoded:
            raise ValueError("send_code instruction not found")

        chunks.append(decoded["code"])
        processed += 1
        if on_progress and total_chunks > 0:
            percent = min(100, (processed * 100) // total_chunks)
            if percent != last_percent:
                last_percent = percent
                on_progress(percent)
        cursor = decoded["before_tx"]

    if on_progress and last_percent < 100:
        on_progress(100)

    return {"result": "".join(reversed(chunks))}
