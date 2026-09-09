import struct

from solana.rpc.async_api import AsyncClient
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import Message

# v1 transactions execute with a zero compute budget unless the limits are set
# explicitly, so every v1 tx carries these via the config mask (SIMD-0385).
COMPUTE_UNIT_LIMIT = 200_000
LOADED_ACCOUNTS_DATA_SIZE_LIMIT = 32 * 1024 * 1024

V1_VERSION_BYTE = 129
# Config mask bits: 0+1 priority fee (u64), 2 compute unit limit, 3 loaded
# accounts data size limit, 4 heap size. We set 2 and 3.
CONFIG_MASK = (1 << 2) | (1 << 3)


def build_v1_transaction(
    signer: Keypair,
    instructions: list[Instruction],
    recent_blockhash,
) -> tuple[bytes, str]:
    """Serialize and sign a v1 transaction (SIMD-0296/0385).

    The v1 wire format is not the v0 envelope: signatures move to the end, the
    compute budget lives in a config mask instead of instructions, and there
    are no address table lookups. Account ordering and index resolution reuse
    the legacy message compiler, which the spec matches. Byte-for-byte port of
    the TS SDK's src/sdk/writer/v1_tx.ts, which is devnet-verified.
    """
    msg = Message.new_with_blockhash(instructions, signer.pubkey(), recent_blockhash)
    header = msg.header

    if header.num_required_signatures != 1:
        raise ValueError("v1 send path supports a single keypair signer")
    if len(msg.account_keys) > 64 or len(msg.instructions) > 64:
        raise ValueError("v1 transactions allow at most 64 accounts and 64 instructions")

    out = bytearray()
    out += bytes([
        V1_VERSION_BYTE,
        header.num_required_signatures,
        header.num_readonly_signed_accounts,
        header.num_readonly_unsigned_accounts,
    ])
    out += struct.pack("<I", CONFIG_MASK)
    out += bytes(msg.recent_blockhash)  # lifetime specifier
    out += bytes([len(msg.instructions), len(msg.account_keys)])
    for key in msg.account_keys:
        out += bytes(key)
    out += struct.pack("<I", COMPUTE_UNIT_LIMIT)
    out += struct.pack("<I", LOADED_ACCOUNTS_DATA_SIZE_LIMIT)

    payloads = bytearray()
    for ix in msg.instructions:
        accounts = bytes(ix.accounts)
        data = bytes(ix.data)
        out += bytes([ix.program_id_index, len(accounts)])
        out += struct.pack("<H", len(data))
        payloads += accounts
        payloads += data
    out += payloads

    # Signatures sign everything before the Signatures field and sit at the end.
    signature = signer.sign_message(bytes(out))
    return bytes(out) + bytes(signature), str(signature)


async def send_tx_v1(
    connection: AsyncClient,
    signer: Keypair,
    instructions: list[Instruction],
    skip_confirmation: bool = False,
) -> str:
    blockhash_resp = await connection.get_latest_blockhash()
    raw, _ = build_v1_transaction(signer, instructions, blockhash_resp.value.blockhash)
    result = await connection.send_raw_transaction(raw)
    signature = result.value
    if not skip_confirmation:
        await connection.confirm_transaction(signature)
    return str(signature)
