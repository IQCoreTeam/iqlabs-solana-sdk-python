import json

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solders.keypair import Keypair
from solders.instruction import Instruction

from ...coder import decode_account
from ...contract import (
    create_instruction_builder,
    create_table_instruction,
    realloc_account_instruction,
    wallet_connection_code_in_instruction,
    db_instruction_code_in_instruction,
    db_code_in_instruction,
    get_connection_instruction_table_pda,
    get_connection_table_pda,
    get_connection_table_ref_pda,
    get_db_root_pda,
    get_instruction_table_pda,
    PROGRAM_ID,
    get_target_connection_table_ref_pda,
    get_table_pda,
    get_user_pda,
    request_connection_instruction,
    update_user_metadata_instruction,
)
from ..utils.ata import resolve_associated_token_account
from ..utils.global_fetch import (
    decode_connection_meta,
    evaluate_connection_access,
    ensure_db_root_exists,
    ensure_table_exists,
    fetch_table_meta,
)
from ..utils.seed import derive_dm_seed, to_seed_bytes
from ..utils.wallet import SignerInput, get_public_key
from .code_in import prepare_code_in
from ..utils.writer_utils import send_tx
from ..constants import DEFAULT_WRITE_FEE_RECEIVER

# ~20 tables worth of extra space per realloc
_REALLOC_EXTRA = 2048
# trigger realloc when free bytes drop below this
_REALLOC_THRESHOLD = 128


def _vec_vec_serialized_size(vv: list[bytes]) -> int:
    return 4 + sum(4 + len(v) for v in vv)


def _build_realloc_ix_if_needed(
    builder,
    payer: Pubkey,
    target: Pubkey,
    account_data: bytes,
) -> Instruction | None:
    decoded = decode_account("DbRoot", account_data)
    if not decoded:
        return None

    used = (
        8 + 32
        + _vec_vec_serialized_size(decoded["table_seeds"])
        + _vec_vec_serialized_size(decoded["global_table_seeds"])
    )
    # id field may not be decoded if account is old, default to 0
    id_bytes = decoded.get("id", b"")
    used += 4 + len(id_bytes)

    if len(account_data) - used >= _REALLOC_THRESHOLD:
        return None

    return realloc_account_instruction(
        builder,
        {"payer": payer, "target": target, "system_program": SYSTEM_PROGRAM_ID},
        {"new_size": len(account_data) + _REALLOC_EXTRA},
    )


async def create_table(
    connection: AsyncClient,
    signer: SignerInput,
    db_root_id: bytes | str,
    table_seed: bytes | str,
    table_name: bytes | str,
    column_names: list[bytes | str],
    id_col: bytes | str,
    ext_keys: list[bytes | str],
    gate: dict | None = None,
    writers: list[Pubkey] | None = None,
) -> str:
    """Create a table.

    Args:
        gate: Optional access gate config dict with keys:
            - mint (Pubkey): token mint or collection address
            - amount (int, optional): minimum token amount, default 1
            - gate_type (int, optional): 0=Token, 1=Collection, default 0
    """
    program_id = PROGRAM_ID
    builder = create_instruction_builder(program_id)
    db_root_seed = to_seed_bytes(db_root_id)
    table_seed_bytes = to_seed_bytes(table_seed)
    db_root = get_db_root_pda(db_root_seed, program_id)
    table = get_table_pda(db_root, table_seed_bytes, program_id)
    instruction_table = get_instruction_table_pda(db_root, table_seed_bytes, program_id)

    db_root_info = await connection.get_account_info(db_root)
    if not db_root_info.value:
        raise ValueError("db_root not found")

    def to_bytes(v: str | bytes) -> bytes:
        return v.encode("utf-8") if isinstance(v, str) else v

    ixs: list[Instruction] = []

    realloc_ix = _build_realloc_ix_if_needed(
        builder, get_public_key(signer), db_root, bytes(db_root_info.value.data),
    )
    if realloc_ix:
        ixs.append(realloc_ix)

    ixs.append(create_table_instruction(
        builder,
        {
            "db_root": db_root,
            "receiver": Pubkey.from_string(DEFAULT_WRITE_FEE_RECEIVER),
            "signer": get_public_key(signer),
            "table": table,
            "instruction_table": instruction_table,
            "system_program": SYSTEM_PROGRAM_ID,
        },
        {
            "db_root_id": db_root_seed,
            "table_seed": table_seed_bytes,
            "table_name": to_bytes(table_name),
            "column_names": [to_bytes(c) for c in column_names],
            "id_col": to_bytes(id_col),
            "ext_keys": [to_bytes(k) for k in ext_keys],
            "gate_opt": gate,
            "writers_opt": writers,
        },
    ))

    return await send_tx(connection, signer, ixs)


async def validate_row_json(
    connection: AsyncClient,
    program_id: Pubkey,
    db_root_id: bytes | str,
    table_seed: bytes | str,
    row_json: str,
    id_col: str | None = None,
) -> dict:
    try:
        parsed = json.loads(row_json)
    except Exception:
        raise ValueError("row_json is invalid")

    if not isinstance(parsed, dict):
        raise ValueError("row_json must be an object")

    meta = await fetch_table_meta(connection, program_id, db_root_id, table_seed)
    required_id = id_col or meta["id_col"]
    allowed_keys = set(meta["columns"]) | {meta["id_col"]}

    for key in parsed.keys():
        if key not in allowed_keys:
            raise ValueError(f"unknown key: {key}")

    if required_id not in parsed:
        raise ValueError(f"missing id_col: {required_id}")

    return meta


METAPLEX_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
GATE_TYPE_COLLECTION = 1


async def resolve_signer_ata(
    connection: AsyncClient,
    signer: SignerInput,
    gate_mint: Pubkey,
) -> Pubkey | None:
    if gate_mint == Pubkey.default():
        return None
    return await resolve_associated_token_account(connection, get_public_key(signer), gate_mint, require_exists=True)


def _get_metadata_pda(mint: Pubkey) -> Pubkey:
    seeds = [b"metadata", bytes(METAPLEX_PROGRAM_ID), bytes(mint)]
    pda, _ = Pubkey.find_program_address(seeds, METAPLEX_PROGRAM_ID)
    return pda


async def _resolve_gate_accounts(
    connection: AsyncClient,
    signer: SignerInput,
    gate: dict,
) -> dict:
    """Resolve signer_ata and metadata_account for gate checks."""
    mint = gate.get("mint", Pubkey.default())
    signer_ata = await resolve_signer_ata(connection, signer, mint)
    if not signer_ata:
        return {"signer_ata": None, "metadata_account": None}

    metadata_account = None
    if gate.get("gate_type") == GATE_TYPE_COLLECTION:
        info = await connection.get_account_info(signer_ata)
        if info.value and len(info.value.data) >= 64:
            nft_mint = Pubkey.from_bytes(bytes(info.value.data)[:32])
            metadata_account = _get_metadata_pda(nft_mint)

    return {"signer_ata": signer_ata, "metadata_account": metadata_account}


async def write_row(
    connection: AsyncClient,
    signer: SignerInput,
    db_root_id: bytes | str,
    table_seed: bytes | str,
    row_json: str,
    skip_confirmation: bool = False,
    remaining_accounts: list[Pubkey] | None = None,
) -> str:
    program_id = PROGRAM_ID
    db_root_seed = to_seed_bytes(db_root_id)
    table_seed_bytes = to_seed_bytes(table_seed)
    db_root = get_db_root_pda(db_root_seed, program_id)

    await ensure_db_root_exists(connection, program_id, db_root_seed)
    result = await ensure_table_exists(connection, program_id, db_root_seed, table_seed_bytes)
    table_pda = result["table_pda"]
    meta = await validate_row_json(connection, program_id, db_root_seed, table_seed_bytes, row_json)
    if meta["writers"] and get_public_key(signer) not in [w for w in meta["writers"]]:
        raise ValueError("signer not in writers")

    gate_accounts = await _resolve_gate_accounts(connection, signer, meta["gate"])
    prepared = await prepare_code_in(connection, signer, [row_json])

    ix = db_code_in_instruction(
        prepared["builder"],
        {
            "user": prepared["user"],
            "signer": get_public_key(signer),
            "user_inventory": prepared["user_inventory"],
            "db_root": db_root,
            "table": table_pda,
            "signer_ata": gate_accounts["signer_ata"],
            "metadata_account": gate_accounts["metadata_account"],
            "system_program": SYSTEM_PROGRAM_ID,
            "receiver": prepared["fee_receiver"],
            "session": prepared["session_account"],
            "iq_ata": prepared["iq_ata"],
        },
        {
            "db_root_id": db_root_seed,
            "table_seed": table_seed_bytes,
            "on_chain_path": prepared["on_chain_path"],
            "metadata": prepared["metadata"],
            "session": prepared["session_finalize"],
        },
        remaining_accounts,
    )
    return await send_tx(connection, signer, ix, skip_confirmation)


async def write_connection_row(
    connection: AsyncClient,
    signer: SignerInput,
    db_root_id: bytes | str,
    connection_seed: bytes | str,
    row_json: str,
) -> str:
    program_id = PROGRAM_ID
    db_root_seed = to_seed_bytes(db_root_id)
    connection_seed_bytes = to_seed_bytes(connection_seed)
    db_root = get_db_root_pda(db_root_seed, program_id)
    connection_table = get_connection_table_pda(db_root, connection_seed_bytes, program_id)
    table_ref = get_connection_table_ref_pda(db_root, connection_seed_bytes, program_id)

    await ensure_db_root_exists(connection, program_id, db_root_seed)
    connection_info, table_ref_info = await asyncio.gather(
        connection.get_account_info(connection_table),
        connection.get_account_info(table_ref),
    )
    if not connection_info.value or not table_ref_info.value:
        raise ValueError("connection table not found")

    try:
        parsed = json.loads(row_json)
    except Exception:
        raise ValueError("row_json is invalid")
    if not isinstance(parsed, dict):
        raise ValueError("row_json must be an object")

    meta = decode_connection_meta(bytes(connection_info.value.data))
    access = evaluate_connection_access(meta, get_public_key(signer))
    if not access["allowed"]:
        raise ValueError(access.get("message", "connection not writable"))

    # Connection payloads are application-defined (plain or encrypted);
    # the program doesn't validate columns, so the SDK shouldn't either.

    prepared = await prepare_code_in(connection, signer, [row_json])
    ix = wallet_connection_code_in_instruction(
        prepared["builder"],
        {
            "user": prepared["user"],
            "signer": get_public_key(signer),
            "user_inventory": prepared["user_inventory"],
            "db_root": db_root,
            "connection_table": connection_table,
            "table_ref": table_ref,
            "system_program": SYSTEM_PROGRAM_ID,
            "receiver": prepared["fee_receiver"],
            "session": prepared["session_account"],
            "iq_ata": prepared["iq_ata"],
        },
        {
            "db_root_id": db_root_seed,
            "connection_seed": connection_seed_bytes,
            "on_chain_path": prepared["on_chain_path"],
            "metadata": prepared["metadata"],
            "session": prepared["session_finalize"],
        },
    )
    return await send_tx(connection, signer, ix)


async def manage_row_data(
    connection: AsyncClient,
    signer: SignerInput,
    db_root_id: bytes | str,
    seed: bytes | str,
    row_json: str,
    table_name: str | bytes | None = None,
    target_tx: str | bytes | None = None,
) -> str:
    program_id = PROGRAM_ID
    db_root_seed = to_seed_bytes(db_root_id)
    seed_bytes = to_seed_bytes(seed)
    db_root = get_db_root_pda(db_root_seed, program_id)
    table_pda = get_table_pda(db_root, seed_bytes, program_id)
    connection_table = get_connection_table_pda(db_root, seed_bytes, program_id)

    await ensure_db_root_exists(connection, program_id, db_root_seed)

    import asyncio
    table_info, connection_info = await asyncio.gather(
        connection.get_account_info(table_pda),
        connection.get_account_info(connection_table),
    )

    if table_info.value:
        if not table_name or not target_tx:
            raise ValueError("table_name and target_tx are required for table edits")

        result = await ensure_table_exists(connection, program_id, db_root_seed, seed_bytes)
        table = result["table_pda"]
        instruction_table = get_instruction_table_pda(db_root, seed_bytes, program_id)
        instruction_info = await connection.get_account_info(instruction_table)
        if not instruction_info.value:
            raise ValueError("instruction table not found")

        meta = await fetch_table_meta(connection, program_id, db_root_seed, seed_bytes)
        if meta["writers"] and get_public_key(signer) not in [w for w in meta["writers"]]:
            raise ValueError("signer not in writers")

        gate_accounts = await _resolve_gate_accounts(connection, signer, meta["gate"])
        prepared = await prepare_code_in(connection, signer, [row_json])

        table_name_bytes = table_name.encode("utf-8") if isinstance(table_name, str) else table_name
        target_tx_bytes = target_tx.encode("utf-8") if isinstance(target_tx, str) else target_tx

        ix = db_instruction_code_in_instruction(
            prepared["builder"],
            {
                "user": prepared["user"],
                "signer": get_public_key(signer),
                "user_inventory": prepared["user_inventory"],
                "db_root": db_root,
                "table": table,
                "instruction_table": instruction_table,
                "signer_ata": gate_accounts["signer_ata"],
                "metadata_account": gate_accounts["metadata_account"],
                "system_program": SYSTEM_PROGRAM_ID,
                "receiver": prepared["fee_receiver"],
                "session": prepared["session_account"],
                "iq_ata": prepared["iq_ata"],
            },
            {
                "db_root_id": db_root_seed,
                "table_seed": seed_bytes,
                "table_name": table_name_bytes,
                "target_tx": target_tx_bytes,
                "on_chain_path": prepared["on_chain_path"],
                "metadata": prepared["metadata"],
                "session": prepared["session_finalize"],
            },
        )
        return await send_tx(connection, signer, ix)

    if connection_info.value:
        return await write_connection_row(connection, signer, db_root_seed, seed_bytes, row_json)

    raise ValueError("table/connection not found")


async def update_user_metadata(
    connection: AsyncClient,
    signer: SignerInput,
    db_root_id: bytes | str,
    meta: bytes | str,
) -> str:
    program_id = PROGRAM_ID
    builder = create_instruction_builder(program_id)
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)
    user = get_user_pda(get_public_key(signer), program_id)
    meta_bytes = meta.encode("utf-8") if isinstance(meta, str) else meta

    ix = update_user_metadata_instruction(
        builder,
        {
            "user": user,
            "db_root": db_root,
            "signer": get_public_key(signer),
            "system_program": SYSTEM_PROGRAM_ID,
        },
        {
            "db_root_id": db_root_seed,
            "meta": meta_bytes,
        },
    )
    return await send_tx(connection, signer, ix)


async def request_connection(
    connection: AsyncClient,
    signer: SignerInput,
    db_root_id: bytes | str,
    party_a: str,
    party_b: str,
    table_name: str | bytes,
    columns: list[str | bytes],
    id_col: str | bytes,
    ext_keys: list[str | bytes],
) -> str:
    program_id = PROGRAM_ID
    builder = create_instruction_builder(program_id)
    requester = get_public_key(signer)
    requester_base58 = str(requester)

    if requester_base58 != party_a and requester_base58 != party_b:
        raise ValueError("signer must be partyA or partyB")

    receiver_base58 = party_b if requester_base58 == party_a else party_a
    receiver = Pubkey.from_string(receiver_base58)
    db_root_seed = to_seed_bytes(db_root_id)
    db_root = get_db_root_pda(db_root_seed, program_id)
    connection_seed_bytes = derive_dm_seed(party_a, party_b)
    connection_table = get_connection_table_pda(db_root, connection_seed_bytes, program_id)
    instruction_table = get_connection_instruction_table_pda(db_root, connection_seed_bytes, program_id)
    table_ref = get_connection_table_ref_pda(db_root, connection_seed_bytes, program_id)
    target_table_ref = get_target_connection_table_ref_pda(db_root, connection_seed_bytes, program_id)
    requester_user = get_user_pda(requester, program_id)
    receiver_user = get_user_pda(receiver, program_id)

    def to_bytes(value: str | bytes) -> bytes:
        return value.encode("utf-8") if isinstance(value, str) else value

    payload_buf = json.dumps({"dmTable": str(connection_table)}).encode("utf-8")

    ix = request_connection_instruction(
        builder,
        {
            "requester": requester,
            "db_root": db_root,
            "connection_table": connection_table,
            "instruction_table": instruction_table,
            "requester_user": requester_user,
            "receiver_user": receiver_user,
            "table_ref": table_ref,
            "target_table_ref": target_table_ref,
            "system_program": SYSTEM_PROGRAM_ID,
        },
        {
            "db_root_id": db_root_seed,
            "connection_seed": connection_seed_bytes,
            "receiver": receiver,
            "table_name": to_bytes(table_name),
            "column_names": [to_bytes(c) for c in columns],
            "id_col": to_bytes(id_col),
            "ext_keys": [to_bytes(k) for k in ext_keys],
            "user_payload": payload_buf,
        },
    )
    return await send_tx(connection, signer, ix)


import asyncio
