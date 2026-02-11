from typing import Callable

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.keypair import Keypair

from ...contract import (
    InstructionBuilder,
    create_session_instruction,
    get_session_pda,
    post_chunk_instruction,
    send_code_instruction,
)
from ..utils.concurrency import run_with_concurrency
from ..utils.rate_limiter import create_rate_limiter
from ..utils.session_speed import SESSION_SPEED_PROFILES, resolve_session_speed
from ..utils.wallet import WalletSigner
from ..utils.writer_utils import send_tx


def _resolve_upload_config(speed: str | None = None) -> dict:
    resolved_speed = resolve_session_speed(speed)
    profile = SESSION_SPEED_PROFILES[resolved_speed]
    return {"max_concurrency": profile["max_concurrency"], "max_rps": profile["max_rps"]}


async def upload_linked_list(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    builder: InstructionBuilder,
    user: Pubkey,
    code_account: Pubkey,
    chunks: list[str],
    method: int,
    on_progress: Callable[[int], None] | None = None,
    speed: str | None = None,
) -> str:
    total_chunks = len(chunks)
    last_percent = -1
    if on_progress:
        on_progress(0)
        last_percent = 0

    config = _resolve_upload_config(speed)
    limiter = create_rate_limiter(config["max_rps"])
    before_tx = "Genesis"

    for index, chunk in enumerate(chunks):
        if limiter:
            await limiter.wait()
        ix = send_code_instruction(
            builder,
            {
                "user": user,
                "code_account": code_account,
                "system_program": SYSTEM_PROGRAM_ID,
            },
            {
                "code": chunk,
                "before_tx": before_tx,
                "method": method,
                "decode_break": 0,
            },
        )
        before_tx = await send_tx(connection, signer, ix)
        if on_progress and total_chunks > 0:
            percent = ((index + 1) * 100) // total_chunks
            if percent != last_percent:
                last_percent = percent
                on_progress(percent)

    return before_tx


async def upload_session(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    builder: InstructionBuilder,
    program_id: Pubkey,
    user: Pubkey,
    user_state: Pubkey,
    seq: int,
    chunks: list[str],
    method: int,
    speed: str | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> str:
    config = _resolve_upload_config(speed)
    total_chunks = len(chunks)
    completed = [0]
    last_percent = [-1]
    if on_progress:
        on_progress(0)
        last_percent[0] = 0

    session = get_session_pda(user, seq, program_id)
    session_info = await connection.get_account_info(session)
    if not session_info.value:
        create_ix = create_session_instruction(
            builder,
            {
                "user": user,
                "user_state": user_state,
                "session": session,
                "system_program": SYSTEM_PROGRAM_ID,
            },
            {"seq": seq},
        )
        await send_tx(connection, signer, create_ix)

    limiter = create_rate_limiter(config["max_rps"])
    payloads = [{"chunk": chunk, "index": index} for index, chunk in enumerate(chunks)]

    async def worker(payload: dict, _idx: int):
        if limiter:
            await limiter.wait()
        ix = post_chunk_instruction(
            builder,
            {"user": user, "session": session},
            {
                "index": payload["index"],
                "chunk": payload["chunk"],
                "method": method,
                "decode_break": 0,
            },
        )
        await send_tx(connection, signer, ix)
        completed[0] += 1
        if on_progress and total_chunks > 0:
            percent = (completed[0] * 100) // total_chunks
            if percent != last_percent[0]:
                last_percent[0] = percent
                on_progress(percent)

    await run_with_concurrency(payloads, config["max_concurrency"], worker)

    return str(session)
