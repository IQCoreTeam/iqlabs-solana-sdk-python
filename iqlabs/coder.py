"""
Anchor-compatible borsh encoding/decoding for IQLabs SDK.

This module handles instruction discriminator generation and borsh serialization
without relying on anchorpy's IDL parsing (which has compatibility issues with Anchor 0.30+).
"""
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass

from solders.pubkey import Pubkey

IDL_PATH = Path(__file__).parent / "idl" / "code_in.json"
with open(IDL_PATH, "r") as f:
    _RAW_IDL = json.load(f)


def sighash(name: str) -> bytes:
    """Generate 8-byte discriminator for Anchor instruction (global namespace)."""
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def account_discriminator(name: str) -> bytes:
    """Generate 8-byte discriminator for Anchor account."""
    return hashlib.sha256(f"account:{name}".encode()).digest()[:8]


# Pre-computed discriminator maps
INSTRUCTION_NAME_TO_DISC: dict[str, bytes] = {}
INSTRUCTION_DISC_TO_NAME: dict[bytes, str] = {}
ACCOUNT_NAME_TO_DISC: dict[str, bytes] = {}
ACCOUNT_DISC_TO_NAME: dict[bytes, str] = {}

for ix in _RAW_IDL.get("instructions", []):
    disc = sighash(ix["name"])
    INSTRUCTION_NAME_TO_DISC[ix["name"]] = disc
    INSTRUCTION_DISC_TO_NAME[disc] = ix["name"]

for acc in _RAW_IDL.get("accounts", []):
    disc = account_discriminator(acc["name"])
    ACCOUNT_NAME_TO_DISC[acc["name"]] = disc
    ACCOUNT_DISC_TO_NAME[disc] = acc["name"]


# =============================================================================
# Borsh Encoding
# =============================================================================

class BorshEncoder:
    """Simple borsh encoder for Anchor instruction arguments."""

    def __init__(self):
        self._parts: list[bytes] = []

    def write_u8(self, value: int) -> "BorshEncoder":
        self._parts.append(value.to_bytes(1, "little"))
        return self

    def write_u32(self, value: int) -> "BorshEncoder":
        self._parts.append(value.to_bytes(4, "little"))
        return self

    def write_u64(self, value: int) -> "BorshEncoder":
        self._parts.append(value.to_bytes(8, "little"))
        return self

    def write_bytes(self, value: bytes) -> "BorshEncoder":
        self.write_u32(len(value))
        self._parts.append(value)
        return self

    def write_string(self, value: str) -> "BorshEncoder":
        encoded = value.encode("utf-8")
        return self.write_bytes(encoded)

    def write_pubkey(self, value: Pubkey) -> "BorshEncoder":
        self._parts.append(bytes(value))
        return self

    def write_option_pubkey(self, value: Pubkey | None) -> "BorshEncoder":
        if value is None:
            self.write_u8(0)
        else:
            self.write_u8(1)
            self.write_pubkey(value)
        return self

    def write_vec_bytes(self, items: list[bytes]) -> "BorshEncoder":
        self.write_u32(len(items))
        for item in items:
            self.write_bytes(item)
        return self

    def write_vec_pubkey(self, items: list[Pubkey] | None) -> "BorshEncoder":
        if items is None:
            self.write_u8(0)
        else:
            self.write_u8(1)
            self.write_u32(len(items))
            for item in items:
                self.write_pubkey(item)
        return self

    def write_option_session_finalize(self, value: dict | None) -> "BorshEncoder":
        if value is None:
            self.write_u8(0)
        else:
            self.write_u8(1)
            self.write_u64(value["seq"])
            self.write_u32(value["total_chunks"])
        return self

    def build(self) -> bytes:
        return b"".join(self._parts)


# =============================================================================
# Borsh Decoding
# =============================================================================

class BorshDecoder:
    """Simple borsh decoder for Anchor instruction/account data."""

    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0

    @property
    def remaining(self) -> int:
        return len(self._data) - self._offset

    def read_u8(self) -> int:
        if self._offset + 1 > len(self._data):
            raise ValueError("Buffer underflow")
        value = self._data[self._offset]
        self._offset += 1
        return value

    def read_u32(self) -> int:
        if self._offset + 4 > len(self._data):
            raise ValueError("Buffer underflow")
        value = int.from_bytes(self._data[self._offset:self._offset + 4], "little")
        self._offset += 4
        return value

    def read_u64(self) -> int:
        if self._offset + 8 > len(self._data):
            raise ValueError("Buffer underflow")
        value = int.from_bytes(self._data[self._offset:self._offset + 8], "little")
        self._offset += 8
        return value

    def read_bytes(self) -> bytes:
        length = self.read_u32()
        if self._offset + length > len(self._data):
            raise ValueError("Buffer underflow")
        value = self._data[self._offset:self._offset + length]
        self._offset += length
        return value

    def read_string(self) -> str:
        return self.read_bytes().decode("utf-8", errors="replace")

    def read_pubkey(self) -> Pubkey:
        if self._offset + 32 > len(self._data):
            raise ValueError("Buffer underflow")
        value = Pubkey.from_bytes(self._data[self._offset:self._offset + 32])
        self._offset += 32
        return value

    def read_option_pubkey(self) -> Pubkey | None:
        is_some = self.read_u8()
        return self.read_pubkey() if is_some else None

    def read_vec_bytes(self) -> list[bytes]:
        length = self.read_u32()
        return [self.read_bytes() for _ in range(length)]

    def read_vec_pubkey(self) -> list[Pubkey]:
        length = self.read_u32()
        return [self.read_pubkey() for _ in range(length)]


# =============================================================================
# Instruction Encoding
# =============================================================================

def encode_instruction(name: str, args: dict) -> bytes:
    """Encode an Anchor instruction with discriminator + borsh-serialized args."""
    discriminator = INSTRUCTION_NAME_TO_DISC.get(name)
    if not discriminator:
        raise ValueError(f"Unknown instruction: {name}")

    encoder = BorshEncoder()

    if name == "create_session":
        encoder.write_u64(args["seq"])

    elif name == "post_chunk":
        encoder.write_u32(args["index"])
        encoder.write_string(args["chunk"])
        encoder.write_u32(args["method"])
        encoder.write_u32(args["decode_break"])

    elif name == "send_code":
        encoder.write_string(args["code"])
        encoder.write_string(args["before_tx"])
        encoder.write_u32(args["method"])
        encoder.write_u32(args["decode_break"])

    elif name == "user_inventory_code_in":
        encoder.write_string(args["on_chain_path"])
        encoder.write_string(args["metadata"])
        encoder.write_option_session_finalize(args.get("session"))

    elif name == "user_initialize":
        pass  # No args

    elif name == "initialize_db_root":
        encoder.write_bytes(args["db_root_id"])

    elif name == "manage_connection":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["connection_seed"])
        encoder.write_u8(args["new_status"])

    elif name == "request_connection":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["connection_seed"])
        encoder.write_pubkey(args["receiver"])
        encoder.write_bytes(args["table_name"])
        encoder.write_vec_bytes(args["column_names"])
        encoder.write_bytes(args["id_col"])
        encoder.write_vec_bytes(args["ext_keys"])
        encoder.write_bytes(args["user_payload"])

    elif name == "db_code_in":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["table_seed"])
        encoder.write_string(args["on_chain_path"])
        encoder.write_string(args["metadata"])
        encoder.write_option_session_finalize(args.get("session"))

    elif name == "db_instruction_code_in":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["table_seed"])
        encoder.write_bytes(args["table_name"])
        encoder.write_bytes(args["target_tx"])
        encoder.write_string(args["on_chain_path"])
        encoder.write_string(args["metadata"])
        encoder.write_option_session_finalize(args.get("session"))

    elif name == "wallet_connection_code_in":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["connection_seed"])
        encoder.write_string(args["on_chain_path"])
        encoder.write_string(args["metadata"])
        encoder.write_option_session_finalize(args.get("session"))

    elif name in ("create_table", "create_admin_table", "create_ext_table", "create_private_table"):
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["table_seed"])
        encoder.write_bytes(args["table_name"])
        encoder.write_vec_bytes(args["column_names"])
        encoder.write_bytes(args["id_col"])
        encoder.write_vec_bytes(args["ext_keys"])
        encoder.write_option_pubkey(args.get("gate_mint_opt"))
        encoder.write_vec_pubkey(args.get("writers_opt"))

    elif name == "update_table":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["table_seed"])
        encoder.write_bytes(args["table_name"])
        encoder.write_vec_bytes(args["column_names"])
        encoder.write_bytes(args["id_col"])
        encoder.write_vec_bytes(args["ext_keys"])
        encoder.write_vec_pubkey(args.get("writers_opt"))

    elif name == "update_user_metadata":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_bytes(args["meta"])

    elif name == "update_db_root_table_list":
        encoder.write_bytes(args["db_root_id"])
        encoder.write_vec_bytes(args["new_table_seeds"])

    elif name == "initialize_config":
        encoder.write_bytes(args["merkle_root"])

    elif name == "set_merkle_root":
        encoder.write_bytes(args["new_root"])
        encoder.write_option_pubkey(args.get("new_authority"))

    elif name == "server_initialize":
        encoder.write_string(args["server_id"])
        encoder.write_string(args["server_type"])
        encoder.write_string(args["allowed_merkle_root"])

    elif name == "user_inventory_code_in_for_free":
        encoder.write_string(args["on_chain_path"])
        encoder.write_string(args["metadata"])
        encoder.write_option_session_finalize(args.get("session"))
        encoder.write_vec_bytes(args["proof"])

    return discriminator + encoder.build()


# =============================================================================
# Instruction Decoding
# =============================================================================

def decode_instruction(data: bytes) -> dict | None:
    """Decode an Anchor instruction from raw bytes."""
    if len(data) < 8:
        return None

    discriminator = data[:8]
    name = INSTRUCTION_DISC_TO_NAME.get(discriminator)
    if not name:
        return None

    decoder = BorshDecoder(data[8:])
    decoded_args = {}

    try:
        if name == "create_session":
            decoded_args["seq"] = decoder.read_u64()

        elif name == "post_chunk":
            decoded_args["index"] = decoder.read_u32()
            decoded_args["chunk"] = decoder.read_string()
            decoded_args["method"] = decoder.read_u32()
            decoded_args["decode_break"] = decoder.read_u32()

        elif name == "send_code":
            decoded_args["code"] = decoder.read_string()
            decoded_args["before_tx"] = decoder.read_string()
            decoded_args["method"] = decoder.read_u32()
            decoded_args["decode_break"] = decoder.read_u32()

        elif name in ("user_inventory_code_in", "user_inventory_code_in_for_free"):
            decoded_args["on_chain_path"] = decoder.read_string()
            decoded_args["metadata"] = decoder.read_string()

        elif name == "db_code_in":
            decoded_args["db_root_id"] = decoder.read_bytes()
            decoded_args["table_seed"] = decoder.read_bytes()
            decoded_args["on_chain_path"] = decoder.read_string()
            decoded_args["metadata"] = decoder.read_string()

        elif name == "db_instruction_code_in":
            decoded_args["db_root_id"] = decoder.read_bytes()
            decoded_args["table_seed"] = decoder.read_bytes()
            decoded_args["table_name"] = decoder.read_bytes()
            decoded_args["target_tx"] = decoder.read_bytes()
            decoded_args["on_chain_path"] = decoder.read_string()
            decoded_args["metadata"] = decoder.read_string()

        elif name == "wallet_connection_code_in":
            decoded_args["db_root_id"] = decoder.read_bytes()
            decoded_args["connection_seed"] = decoder.read_bytes()
            decoded_args["on_chain_path"] = decoder.read_string()
            decoded_args["metadata"] = decoder.read_string()

    except ValueError:
        pass  # Partial decode is ok

    return {"name": name, "data": decoded_args}


# =============================================================================
# Account Decoding
# =============================================================================

def decode_account(name: str, data: bytes) -> dict | None:
    """Decode an Anchor account from raw bytes (skipping 8-byte discriminator)."""
    if len(data) < 8:
        return None

    decoder = BorshDecoder(data[8:])
    result = {}

    try:
        if name == "UserState":
            result["owner"] = decoder.read_pubkey()
            result["metadata"] = decoder.read_bytes()
            result["total_session_files"] = decoder.read_u64()

        elif name == "Table":
            result["column_names"] = decoder.read_vec_bytes()
            result["id_col"] = decoder.read_bytes()
            result["gate_mint"] = decoder.read_pubkey()
            result["writers"] = decoder.read_vec_pubkey()

        elif name == "Connection":
            result["db_root_id"] = decoder.read_bytes()
            result["column_names"] = decoder.read_vec_bytes()
            result["id_col"] = decoder.read_bytes()
            result["ext_keys"] = decoder.read_vec_bytes()
            result["name"] = decoder.read_bytes()
            result["gate_mint"] = decoder.read_pubkey()
            result["party_a"] = decoder.read_pubkey()
            result["party_b"] = decoder.read_pubkey()
            result["status"] = decoder.read_u8()
            result["requester"] = decoder.read_u8()
            result["blocker"] = decoder.read_u8()

        elif name == "DbRoot":
            result["creator"] = decoder.read_pubkey()
            result["table_seeds"] = decoder.read_vec_bytes()
            result["global_table_seeds"] = decoder.read_vec_bytes()

    except ValueError:
        pass  # Partial decode is ok

    return result
