from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")


def find_associated_token_address(owner: Pubkey, mint: Pubkey) -> Pubkey:
    return Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM_ID), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]


async def resolve_associated_token_account(
    connection: AsyncClient,
    owner: Pubkey,
    mint: Pubkey,
    require_exists: bool = True,
) -> Pubkey | None:
    from .writer_utils import get_cached_account_exists, refresh_account_exists

    ata = find_associated_token_address(owner, mint)
    exists = await get_cached_account_exists(connection, ata)
    if not exists and require_exists:
        exists = await refresh_account_exists(connection, ata)
    if not exists:
        if require_exists:
            raise ValueError("missing signer_ata")
        return None
    return ata
