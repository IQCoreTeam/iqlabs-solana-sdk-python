import os
import time
from dataclasses import dataclass

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from ..constants import (
    CHUNK_SIZE,
    CHUNK_SIZE_V1,
    DEFAULT_LINKED_LIST_THRESHOLD,
    DIRECT_METADATA_MAX_BYTES,
    DIRECT_METADATA_MAX_BYTES_V1,
    FEATURE_PROGRAM_ID,
    TX_V1_FEATURE_GATE,
)


@dataclass(frozen=True)
class TxProfile:
    version: str  # "legacy" | "v1"
    chunk_size: int
    inline_max_bytes: int
    linked_list_threshold: int


LEGACY_TX_PROFILE = TxProfile(
    version="legacy",
    chunk_size=CHUNK_SIZE,
    inline_max_bytes=DIRECT_METADATA_MAX_BYTES,
    linked_list_threshold=DEFAULT_LINKED_LIST_THRESHOLD,
)

V1_TX_PROFILE = TxProfile(
    version="v1",
    chunk_size=CHUNK_SIZE_V1,
    inline_max_bytes=DIRECT_METADATA_MAX_BYTES_V1,
    linked_list_threshold=DEFAULT_LINKED_LIST_THRESHOLD,
)


def can_sign_v1(signer) -> bool:
    """The v1 send path signs the message bytes directly, which needs the raw
    keypair. Wallet signers stay on the legacy profile until the wallet stack
    supports v1 natively."""
    return isinstance(signer, Keypair) or hasattr(signer, "_keypair")


def extract_keypair(signer) -> Keypair:
    if isinstance(signer, Keypair):
        return signer
    return signer._keypair


_INACTIVE_RECHECK_MS = 10 * 60 * 1000

# Keyed by RPC endpoint. Activation is one-way, so a positive result is
# cached forever; a negative one is rechecked on a TTL.
_gate_cache: dict[str, dict] = {}


async def is_tx_v1_active(connection: AsyncClient) -> bool:
    key = str(getattr(getattr(connection, "_provider", None), "endpoint_uri", "default"))
    cached = _gate_cache.get(key)
    now = time.time() * 1000
    if cached and (cached["active"] or now < cached["expires_at"]):
        return cached["active"]
    active = False
    try:
        info = await connection.get_account_info(Pubkey.from_string(TX_V1_FEATURE_GATE))
        value = info.value
        active = (
            value is not None
            and str(value.owner) == FEATURE_PROGRAM_ID
            and len(value.data) > 0
            and value.data[0] == 1  # Option<u64> tag: Some(activation_slot)
        )
    except Exception:
        active = False  # treat RPC failures as inactive; rechecked on TTL
    _gate_cache[key] = {"active": active, "expires_at": now + _INACTIVE_RECHECK_MS}
    return active


async def resolve_tx_profile(connection: AsyncClient, signer) -> TxProfile:
    """Pick the write profile for this connection + signer.
    Override with IQ_TX_PROFILE=legacy|v1 (v1 still requires a keypair signer)."""
    override = os.environ.get("IQ_TX_PROFILE")
    if override == "legacy":
        return LEGACY_TX_PROFILE
    if not can_sign_v1(signer):
        return LEGACY_TX_PROFILE
    if override == "v1":
        return V1_TX_PROFILE
    return V1_TX_PROFILE if await is_tx_v1_active(connection) else LEGACY_TX_PROFILE


async def should_send_v1(connection: AsyncClient, signer) -> bool:
    """Whether a tx for this connection + signer should go out as v1."""
    return (await resolve_tx_profile(connection, signer)).version == "v1"
