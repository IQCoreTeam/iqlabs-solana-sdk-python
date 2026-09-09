"""Manual devnet check for the v1 tx wire format.

Run: python tests/sdk/v1_tx_devnet.py  (funded keypair at ~/.config/solana/id.json
or V1_TEST_KEYPAIR). Sends a 1-lamport self-transfer as a v1 transaction and
reads it back. Devnet has the v1 feature gate active, so a confirmation proves
the serialization end to end. Mirrors tests/sdk/v1_tx_devnet.ts in the TS SDK.
"""
import asyncio
import json
import os
from pathlib import Path

from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import transfer, TransferParams

from iqlabs.sdk.utils.tx_profile import is_tx_v1_active
from iqlabs.sdk.utils.v1_tx import send_tx_v1


def load_keypair() -> Keypair:
    keypair_path = os.environ.get("V1_TEST_KEYPAIR", str(Path.home() / ".config/solana/id.json"))
    secret = json.loads(Path(keypair_path).read_text())
    return Keypair.from_bytes(bytes(secret))


async def main() -> None:
    connection = AsyncClient("https://api.devnet.solana.com")
    print("v1 gate active on devnet:", await is_tx_v1_active(connection))

    payer = load_keypair()
    print("payer:", payer.pubkey())

    ix = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=payer.pubkey(), lamports=1))
    signature = await send_tx_v1(connection, payer, [ix])
    print("v1 tx confirmed:", signature)

    resp = await connection.get_transaction(
        Signature.from_string(signature), max_supported_transaction_version=1
    )
    print("fetched version:", resp.value.transaction.version)
    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
