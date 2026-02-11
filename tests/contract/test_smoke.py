import pytest
from solders.pubkey import Pubkey
from solders.keypair import Keypair

from iqlabs.contract import (
    DEFAULT_ANCHOR_PROGRAM_ID,
    DEFAULT_PINOCCHIO_PROGRAM_ID,
    create_instruction_builder,
    create_session_instruction,
    get_code_account_pda,
    get_db_root_pda,
    get_session_pda,
    get_user_pda,
    get_user_inventory_pda,
    get_program_id,
    resolve_contract_runtime,
    user_initialize_instruction,
)


program_id = Pubkey.from_string(DEFAULT_ANCHOR_PROGRAM_ID)
user = Keypair().pubkey()

db_root_id = bytes([1, 2, 3, 4])
user_state = get_user_pda(user, program_id)
session = get_session_pda(user, 1, program_id)
code_account = get_code_account_pda(user, program_id)
user_inventory = get_user_inventory_pda(user, program_id)
db_root = get_db_root_pda(db_root_id, program_id)


def test_pda_generation():
    assert isinstance(user_state, Pubkey)
    assert isinstance(session, Pubkey)
    assert isinstance(code_account, Pubkey)
    assert isinstance(user_inventory, Pubkey)
    assert isinstance(db_root, Pubkey)


def test_instruction_builder():
    builder = create_instruction_builder(program_id)

    create_session_ix = create_session_instruction(
        builder,
        {
            "user": user,
            "user_state": user_state,
            "session": session,
        },
        {"seq": 1},
    )

    assert str(create_session_ix.program_id) == str(program_id)
    assert len(create_session_ix.accounts) == 4
    assert len(create_session_ix.data) > 0


def test_user_initialize_instruction():
    builder = create_instruction_builder(program_id)

    user_init_ix = user_initialize_instruction(
        builder,
        {
            "user": user,
            "code_account": code_account,
            "user_state": user_state,
            "user_inventory": user_inventory,
        },
    )

    assert str(user_init_ix.program_id) == str(program_id)


def test_resolve_contract_runtime():
    pinocchio_runtime = resolve_contract_runtime("pinocchio")
    assert pinocchio_runtime == "pinocchio"

    inferred_anchor = resolve_contract_runtime("anything_else")
    assert inferred_anchor == "anchor"


def test_get_program_id():
    default_anchor_program = get_program_id("anchor")
    assert str(default_anchor_program) == DEFAULT_ANCHOR_PROGRAM_ID

    default_pinocchio_program = get_program_id("pinocchio")
    assert str(default_pinocchio_program) == DEFAULT_PINOCCHIO_PROGRAM_ID


def test_custom_program_id():
    custom_program_id = Keypair().pubkey()
    custom_user_state = get_user_pda(user, custom_program_id)
    assert isinstance(custom_user_state, Pubkey)


if __name__ == "__main__":
    test_pda_generation()
    test_instruction_builder()
    test_user_initialize_instruction()
    test_resolve_contract_runtime()
    test_get_program_id()
    test_custom_program_id()
    print("contract smoke test ok")
