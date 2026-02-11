"""
Basic example showing how to use the IQLabs SDK.

To run this example:
1. Install dependencies: pip install -e .
2. Set your RPC URL (optional): export SOLANA_RPC_ENDPOINT=https://api.devnet.solana.com
3. Run: python examples/hello.py

Note: This example requires a funded keypair to actually write to the blockchain.
"""
import asyncio
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient

from iqlabs import reader, writer, set_rpc_url


async def main():
    # 1. Configure RPC
    set_rpc_url("https://api.devnet.solana.com")

    # 2. Create a connection
    connection = AsyncClient("https://api.devnet.solana.com")

    # 3. Generate a keypair (in real usage, load your funded keypair)
    keypair = Keypair()
    print(f"Using pubkey: {keypair.pubkey()}")

    # Note: The following operations require SOL to pay for transactions
    # Uncomment to test with a funded keypair:

    # # 4. Write data to the blockchain
    # signature = await writer.code_in(
    #     connection,
    #     keypair,
    #     ["Hello, IQLabs!"],  # data chunks to upload
    #     filename="hello.txt",
    #     filetype="text/plain",
    # )
    # print(f"Write signature: {signature}")

    # # 5. Read data back
    # result = await reader.read_code_in(signature)
    # print(f"Metadata: {result['metadata']}")
    # print(f"Data: {result['data']}")

    await connection.close()
    print("Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
