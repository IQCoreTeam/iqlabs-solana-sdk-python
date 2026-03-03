import json
from typing import Callable

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.keypair import Keypair

from ...contract import (
    create_instruction_builder,
    user_inventory_code_in_instruction,
    get_code_account_pda,
    get_user_inventory_pda,
    PROGRAM_ID,
    get_session_pda,
    get_user_pda,
)
from ..constants import (
    DEFAULT_LINKED_LIST_THRESHOLD,
    DIRECT_METADATA_MAX_BYTES,
    DEFAULT_IQ_MINT,
    DEFAULT_WRITE_FEE_RECEIVER,
)
from ..utils.ata import resolve_associated_token_account
from ..utils.wallet import to_wallet_signer, WalletSigner
from ..utils.writer_utils import ensure_user_initialized, read_magic_bytes, send_tx
from .uploading_methods import upload_linked_list, upload_session
from .reader_context_helper import decode_user_state


async def prepare_code_in(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    chunks: list[str],
    filename: str | None = None,
    method: int = 0,
    filetype: str = "",
    on_progress: Callable[[int], None] | None = None,
    speed: str | None = None,
) -> dict:
    total_chunks = len(chunks)
    if total_chunks == 0:
        raise ValueError("chunks is empty")

    wallet = to_wallet_signer(signer)
    program_id = PROGRAM_ID
    builder = create_instruction_builder(program_id)
    user = wallet.public_key
    user_state = get_user_pda(user, program_id)
    code_account = get_code_account_pda(user, program_id)
    user_inventory = get_user_inventory_pda(user, program_id)

    await ensure_user_initialized(
        connection,
        signer,
        builder,
        {
            "user": user,
            "code_account": code_account,
            "user_state": user_state,
            "user_inventory": user_inventory,
            "system_program": SYSTEM_PROGRAM_ID,
        },
    )

    seq = 0
    info = await connection.get_account_info(user_state)
    if info.value:
        decoded = decode_user_state(bytes(info.value.data))
        if decoded:
            seq = int(decoded["total_session_files"])

    magic = read_magic_bytes(chunks[0])
    resolved_filetype = filetype or magic["mime"]
    safe_filename = filename or f"{seq}.{magic['ext']}"
    base_metadata = {
        "filetype": resolved_filetype,
        "method": method,
        "filename": safe_filename,
        "total_chunks": total_chunks,
    }
    inline_metadata = json.dumps({**base_metadata, "data": chunks[0]}) if total_chunks == 1 else ""
    use_inline = bool(inline_metadata) and len(inline_metadata.encode("utf-8")) <= DIRECT_METADATA_MAX_BYTES
    metadata = inline_metadata if use_inline else json.dumps(base_metadata)

    on_chain_path = ""
    use_session = not use_inline and total_chunks >= DEFAULT_LINKED_LIST_THRESHOLD
    session_account = None
    session_finalize = None

    if not use_inline:
        if not use_session:
            on_chain_path = await upload_linked_list(
                connection, signer, builder, user, code_account, chunks, method, on_progress, speed
            )
        else:
            on_chain_path = await upload_session(
                connection, signer, builder, program_id, user, user_state, seq, chunks, method, speed=speed, on_progress=on_progress
            )
            session_account = get_session_pda(user, seq, program_id)
            session_finalize = {"seq": seq, "total_chunks": total_chunks}

    fee_receiver = Pubkey.from_string(DEFAULT_WRITE_FEE_RECEIVER)
    is_direct_path = not use_session and len(on_chain_path) == 0
    iq_ata = None
    if is_direct_path:
        iq_ata = await resolve_associated_token_account(
            connection, user, Pubkey.from_string(DEFAULT_IQ_MINT), require_exists=False
        )

    return {
        "builder": builder,
        "user": user,
        "user_inventory": user_inventory,
        "on_chain_path": on_chain_path,
        "metadata": metadata,
        "session_account": session_account,
        "session_finalize": session_finalize,
        "fee_receiver": fee_receiver,
        "iq_ata": iq_ata,
    }


async def code_in(
    connection: AsyncClient,
    signer: Keypair | WalletSigner,
    chunks: list[str],
    filename: str | None = None,
    method: int = 0,
    filetype: str = "",
    on_progress: Callable[[int], None] | None = None,
    speed: str | None = None,
) -> str:
    prepared = await prepare_code_in(
        connection, signer, chunks, filename, method, filetype, on_progress, speed
    )

    db_ix = user_inventory_code_in_instruction(
        prepared["builder"],
        {
            "user": prepared["user"],
            "user_inventory": prepared["user_inventory"],
            "system_program": SYSTEM_PROGRAM_ID,
            "receiver": prepared["fee_receiver"],
            "session": prepared["session_account"],
            "iq_ata": prepared["iq_ata"],
        },
        {
            "on_chain_path": prepared["on_chain_path"],
            "metadata": prepared["metadata"],
            "session": prepared["session_finalize"],
        },
    )

    signature = await send_tx(connection, signer, db_ix)
    if on_progress:
        on_progress(100)
    return signature
