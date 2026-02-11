import struct
from solders.pubkey import Pubkey

from .constants import (
    SEED_BUNDLE,
    SEED_CODE_ACCOUNT,
    SEED_CONFIG,
    SEED_CONNECTION,
    SEED_USER_INVENTORY,
    SEED_DB_ROOT,
    SEED_INSTRUCTION,
    SEED_TABLE,
    SEED_TABLE_REF,
    SEED_TARGET,
    SEED_USER,
)
from .profile import get_program_id

SEED_CONFIG_BYTES = SEED_CONFIG.encode()
SEED_DB_ROOT_BYTES = SEED_DB_ROOT.encode()
SEED_TABLE_BYTES = SEED_TABLE.encode()
SEED_TABLE_REF_BYTES = SEED_TABLE_REF.encode()
SEED_INSTRUCTION_BYTES = SEED_INSTRUCTION.encode()
SEED_TARGET_BYTES = SEED_TARGET.encode()
SEED_USER_BYTES = SEED_USER.encode()
SEED_BUNDLE_BYTES = SEED_BUNDLE.encode()
SEED_CONNECTION_BYTES = SEED_CONNECTION.encode()
SEED_CODE_ACCOUNT_BYTES = SEED_CODE_ACCOUNT.encode()
SEED_USER_INVENTORY_BYTES = SEED_USER_INVENTORY.encode()


def _encode_u64_seed(value: int) -> bytes:
    return struct.pack("<Q", value)


def _find_pda(seeds: list[bytes], program_id: Pubkey) -> Pubkey:
    return Pubkey.find_program_address(seeds, program_id)[0]


def get_db_root_pda(db_root_id: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_DB_ROOT_BYTES, bytes(program_id), db_root_id], program_id)


def get_table_pda(db_root: Pubkey, table_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_TABLE_BYTES, bytes(program_id), bytes(db_root), table_seed], program_id)


def get_instruction_table_pda(db_root: Pubkey, table_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_TABLE_BYTES, bytes(program_id), bytes(db_root), table_seed, SEED_INSTRUCTION_BYTES], program_id)


def get_connection_table_pda(db_root: Pubkey, connection_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_CONNECTION_BYTES, bytes(program_id), bytes(db_root), connection_seed], program_id)


def get_connection_instruction_table_pda(db_root: Pubkey, connection_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_CONNECTION_BYTES, bytes(program_id), bytes(db_root), connection_seed, SEED_INSTRUCTION_BYTES], program_id)


def get_connection_table_ref_pda(db_root: Pubkey, connection_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_TABLE_REF_BYTES, bytes(program_id), bytes(db_root), connection_seed], program_id)


def get_target_table_ref_pda(db_root: Pubkey, table_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_TABLE_REF_BYTES, bytes(program_id), bytes(db_root), table_seed, SEED_TARGET_BYTES], program_id)


def get_target_connection_table_ref_pda(db_root: Pubkey, connection_seed: bytes, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_TABLE_REF_BYTES, bytes(program_id), bytes(db_root), connection_seed, SEED_TARGET_BYTES], program_id)


def get_user_pda(user: Pubkey, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_USER_BYTES, bytes(program_id), bytes(user)], program_id)


def get_session_pda(user: Pubkey, seq: int, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_BUNDLE_BYTES, bytes(program_id), bytes(user), _encode_u64_seed(seq)], program_id)


def get_code_account_pda(user: Pubkey, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_CODE_ACCOUNT_BYTES, bytes(user)], program_id)


def get_user_inventory_pda(user: Pubkey, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([SEED_USER_INVENTORY_BYTES, bytes(user)], program_id)


def get_server_account_pda(user: Pubkey, server_id: str, program_id: Pubkey | None = None) -> Pubkey:
    program_id = program_id or get_program_id()
    return _find_pda([server_id.encode(), bytes(user)], program_id)
