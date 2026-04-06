from __future__ import annotations
import json
from enum import IntEnum
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

from ..coder import encode_instruction


class GateType(IntEnum):
    """Gate type enum for user-friendly gate configuration."""
    TOKEN = 0       # Exact token mint match + minimum amount check
    COLLECTION = 1  # NFT collection check via Metaplex metadata verification

IDL_PATH = Path(__file__).parent.parent / "idl" / "code_in.json"
with open(IDL_PATH, "r") as f:
    _raw_idl = json.load(f)


@dataclass
class InstructionBuilder:
    program_id: Pubkey
    _instruction_map: dict[str, dict]

    def build(self, name: str, accounts: dict[str, Pubkey | None], args: dict[str, Any] | None = None) -> Instruction:
        ix_def = self._instruction_map.get(name)
        if not ix_def:
            raise ValueError(f"Unknown instruction: {name}")

        keys: list[AccountMeta] = []
        for acc in ix_def.get("accounts", []):
            acc_name = acc["name"]
            pubkey = Pubkey.from_string(acc["address"]) if acc.get("address") else accounts.get(acc_name)
            if not pubkey:
                if acc.get("optional"):
                    keys.append(AccountMeta(self.program_id, is_signer=False, is_writable=False))
                    continue
                raise ValueError(f"Missing account: {acc_name}")
            keys.append(AccountMeta(pubkey, is_signer=bool(acc.get("signer")), is_writable=bool(acc.get("writable"))))

        data = encode_instruction(name, args or {})
        return Instruction(self.program_id, data, keys)


def create_instruction_builder(program_id: Pubkey) -> InstructionBuilder:
    instructions = _raw_idl.get("instructions", [])
    instruction_map = {ix["name"]: ix for ix in instructions}
    return InstructionBuilder(program_id, instruction_map)


def create_admin_table_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey], args: dict) -> Instruction:
    return builder.build("create_admin_table", accounts, args)


def create_ext_table_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey], args: dict) -> Instruction:
    return builder.build("create_ext_table", accounts, args)


def create_private_table_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey], args: dict) -> Instruction:
    return builder.build("create_private_table", accounts, args)


def create_session_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("create_session", accounts, args)


def create_table_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("create_table", accounts, args)


def user_inventory_code_in_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("user_inventory_code_in", accounts, args)


def user_inventory_code_in_for_free_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("user_inventory_code_in_for_free", accounts, args)


def initialize_config_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("initialize_config", accounts, args)


def initialize_db_root_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("initialize_db_root", accounts, args)


def manage_connection_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("manage_connection", accounts, args)


def post_chunk_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("post_chunk", accounts, args)


def realloc_account_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("realloc_account", accounts, args)


def request_connection_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("request_connection", accounts, args)


def send_code_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("send_code", accounts, args)


def server_initialize_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("server_initialize", accounts, args)


def set_merkle_root_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("set_merkle_root", accounts, args)


def update_db_root_table_list_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("update_db_root_table_list", accounts, args)


def update_db_root_global_table_list_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("update_db_root_global_table_list", accounts, args)


def update_table_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("update_table", accounts, args)


def update_user_metadata_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("update_user_metadata", accounts, args)


def user_initialize_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None]) -> Instruction:
    return builder.build("user_initialize", accounts)


def wallet_connection_code_in_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("wallet_connection_code_in", accounts, args)


def db_code_in_instruction(
    builder: InstructionBuilder,
    accounts: dict[str, Pubkey | None],
    args: dict,
    remaining_accounts: list[Pubkey] | None = None,
) -> Instruction:
    ix = builder.build("db_code_in", accounts, args)
    if remaining_accounts:
        keys = list(ix.accounts)
        for pubkey in remaining_accounts:
            keys.append(AccountMeta(pubkey, is_signer=False, is_writable=False))
        ix = Instruction(ix.program_id, ix.data, keys)
    return ix


def db_instruction_code_in_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("db_instruction_code_in", accounts, args)


def onboard_table_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("onboard_table", accounts, args)


def manage_table_creators_instruction(builder: InstructionBuilder, accounts: dict[str, Pubkey | None], args: dict) -> Instruction:
    return builder.build("manage_table_creators", accounts, args)
