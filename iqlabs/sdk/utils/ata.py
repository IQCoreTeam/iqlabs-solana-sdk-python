from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_2022_PROGRAM_ID = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")


def find_associated_token_address(
    owner: Pubkey,
    mint: Pubkey,
    token_program_id: Pubkey = TOKEN_PROGRAM_ID,
) -> Pubkey:
    # token_program_id defaults to the legacy program, so every existing caller is unchanged;
    # pass the Token-2022 id when the mint lives there (its ATA is seeded with that id).
    return Pubkey.find_program_address(
        [bytes(owner), bytes(token_program_id), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]


async def _mint_token_program(connection: AsyncClient, mint: Pubkey) -> Pubkey:
    # Legacy is the fallback, so a missing/unreadable mint (or an RPC hiccup) resolves exactly
    # as before — this only ever ADDS the Token-2022 branch.
    try:
        info = await connection.get_account_info(mint)
        if info.value is not None and info.value.owner == TOKEN_2022_PROGRAM_ID:
            return TOKEN_2022_PROGRAM_ID
    except Exception:
        pass
    return TOKEN_PROGRAM_ID


async def resolve_associated_token_account(
    connection: AsyncClient,
    owner: Pubkey,
    mint: Pubkey,
    require_exists: bool = True,
) -> Pubkey | None:
    from .writer_utils import get_cached_account_exists, refresh_account_exists

    token_program_id = await _mint_token_program(connection, mint)
    ata = find_associated_token_address(owner, mint, token_program_id)
    exists = await get_cached_account_exists(connection, ata)
    if not exists and require_exists:
        exists = await refresh_account_exists(connection, ata)
    if not exists:
        if require_exists:
            raise ValueError("missing signer_ata")
        return None
    return ata
