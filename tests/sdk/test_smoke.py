import os
import pytest
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from Crypto.Hash import keccak

from iqlabs.sdk.utils.connection_helper import (
    choose_rpc_url_for_freshness,
    detect_connection_settings,
)
from iqlabs.sdk.utils.seed import (
    derive_dm_seed,
    derive_seed_bytes,
    sort_pubkeys,
    to_seed_bytes,
)
from iqlabs.contract import (
    CONNECTION_BLOCKER_NONE,
    CONNECTION_STATUS_APPROVED,
    CONNECTION_STATUS_BLOCKED,
    CONNECTION_STATUS_PENDING,
)
from iqlabs.sdk.utils.global_fetch import evaluate_connection_access


ENV_KEYS = [
    "IQLABS_RPC_ENDPOINT",
    "IQLABS_RPC_PROVIDER",
    "RPC_PROVIDER",
    "SOLANA_RPC_ENDPOINT",
    "SOLANA_RPC",
    "RPC_ENDPOINT",
    "RPC_URL",
    "HELIUS_RPC_URL",
    "ZEROBLOCK_RPC_URL",
    "FRESH_RPC_URL",
    "RECENT_RPC_URL",
]


def backup_env() -> dict:
    return {key: os.environ.get(key) for key in ENV_KEYS}


def restore_env(snapshot: dict) -> None:
    for key in ENV_KEYS:
        value = snapshot.get(key)
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]


def test_connection_helper():
    snapshot = backup_env()
    try:
        os.environ["IQLABS_RPC_ENDPOINT"] = "https://rpc.primary"
        os.environ["HELIUS_RPC_URL"] = "https://rpc.helius"
        os.environ["ZEROBLOCK_RPC_URL"] = "https://rpc.zeroblock"
        os.environ["FRESH_RPC_URL"] = "https://rpc.fresh"
        os.environ["RECENT_RPC_URL"] = "https://rpc.recent"

        settings = detect_connection_settings()
        assert settings["rpc_url"] == "https://rpc.primary"
        assert settings["helius_rpc_url"] == "https://rpc.helius"
        assert settings["zeroblock_rpc_url"] == "https://rpc.zeroblock"

        assert choose_rpc_url_for_freshness("fresh") == "https://rpc.fresh"
        assert choose_rpc_url_for_freshness("recent") == "https://rpc.recent"
        assert choose_rpc_url_for_freshness("archive") == "https://rpc.primary"
    finally:
        restore_env(snapshot)


def test_seed_utils():
    # Test hex pass-through
    hex_str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    seed_bytes = derive_seed_bytes(hex_str)
    assert seed_bytes.hex() == hex_str

    # Test keccak256 hashing
    text = "iq-labs"
    hashed = derive_seed_bytes(text)
    k = keccak.new(digest_bits=256)
    k.update(text.encode("utf-8"))
    expected = k.digest()
    assert hashed.hex() == expected.hex()

    # Test sort_pubkeys
    a, b = sort_pubkeys("z-user", "a-user")
    assert a == "a-user"
    assert b == "z-user"

    # Test derive_dm_seed
    dm_seed = derive_dm_seed("user-2", "user-1")
    k = keccak.new(digest_bits=256)
    k.update("user-1:user-2".encode("utf-8"))
    manual = k.digest()
    assert dm_seed.hex() == manual.hex()

    # Test to_seed_bytes
    sample = bytes([5, 6, 7])
    assert to_seed_bytes(sample) == sample
    via_string = to_seed_bytes("abc")
    assert via_string != sample


def test_evaluate_connection_access():
    party_a = Keypair().pubkey()
    party_b = Keypair().pubkey()
    gate_mint = Keypair().pubkey()

    base_meta = {
        "columns": [],
        "id_col": "id",
        "ext_keys": [],
        "name": "dm",
        "gate_mint": gate_mint,
        "party_a": party_a,
        "party_b": party_b,
        "status": CONNECTION_STATUS_PENDING,
        "requester": 0,
        "blocker": CONNECTION_BLOCKER_NONE,
    }

    def evaluate(overrides: dict, signer: Pubkey) -> dict:
        meta = {**base_meta, **overrides}
        return evaluate_connection_access(meta, signer)

    # Pending - requester can send
    pending_requester = evaluate({}, party_a)
    assert pending_requester["allowed"] == True
    assert pending_requester["status"] == "pending"

    # Pending - other party needs to allow
    pending_other = evaluate({}, party_b)
    assert pending_other["allowed"] == False
    assert pending_other["status"] == "pending"
    assert pending_other["message"] == "Allow the connection in settings."

    # Approved - both can write
    approved = evaluate({"status": CONNECTION_STATUS_APPROVED}, party_a)
    assert approved["allowed"] == True
    assert approved["status"] == "approved"

    # Blocked by A - A needs to unblock
    blocked_by_a = evaluate({"status": CONNECTION_STATUS_BLOCKED, "blocker": 0}, party_a)
    assert blocked_by_a["allowed"] == False
    assert blocked_by_a["status"] == "blocked"
    assert blocked_by_a["message"] == "Allow the connection in settings."

    # Blocked by B - A asks B to unblock
    blocked_by_other = evaluate({"status": CONNECTION_STATUS_BLOCKED, "blocker": 1}, party_a)
    assert blocked_by_other["allowed"] == False
    assert blocked_by_other["status"] == "blocked"
    assert blocked_by_other["message"] == "Ask the other party to unblock the connection."

    # Outsider - not allowed
    outsider = evaluate({}, Keypair().pubkey())
    assert outsider["allowed"] == False
    assert outsider["status"] == "pending"
    assert outsider["message"] == "signer is not a connection participant"


if __name__ == "__main__":
    test_connection_helper()
    test_seed_utils()
    test_evaluate_connection_access()
    print("sdk smoke test ok")
