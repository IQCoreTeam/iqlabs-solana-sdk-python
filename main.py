import asyncio
from iqlabs import reader, writer, set_rpc_url


async def main():
    # 1. Configure RPC
    set_rpc_url("https://api.devnet.solana.com")

    # Example usage (commented out - requires keypair):
    # from solders.keypair import Keypair
    # from solana.rpc.async_api import AsyncClient
    #
    # keypair = Keypair()
    # connection = AsyncClient("https://api.devnet.solana.com")
    #
    # # 2. Write data
    # signature = await writer.code_in(connection, keypair, ["hello"])
    #
    # # 3. Read data back
    # result = await reader.read_code_in(signature)
    # print(result)


if __name__ == "__main__":
    asyncio.run(main())
