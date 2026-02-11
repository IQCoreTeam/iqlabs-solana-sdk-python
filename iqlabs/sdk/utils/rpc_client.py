from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.rpc.responses import GetTransactionResp

from .connection_helper import get_connection, get_rpc_provider


class RpcClient:
    def __init__(
        self,
        connection: AsyncClient | None = None,
        provider: str | None = None,
        use_helius_enhanced: bool | None = None,
    ):
        self._connection = connection or get_connection()
        self._provider = provider or get_rpc_provider()
        self._use_helius_enhanced = (
            use_helius_enhanced if use_helius_enhanced is not None else self._provider == "helius"
        )

    def get_connection(self) -> AsyncClient:
        return self._connection

    def get_provider(self) -> str:
        return self._provider

    def helius_enhanced_enabled(self) -> bool:
        return self._use_helius_enhanced and self._provider == "helius"

    async def get_signatures_for_address(self, pubkey: Pubkey, before: str | None = None, limit: int | None = None):
        return await self._connection.get_signatures_for_address(pubkey, before=before, limit=limit)

    async def get_transaction(self, signature: str, max_supported_transaction_version: int = 0) -> GetTransactionResp:
        return await self._connection.get_transaction(
            signature, max_supported_transaction_version=max_supported_transaction_version
        )

    async def get_transactions_for_address(
        self,
        pubkey: Pubkey,
        before: str | None = None,
        until: str | None = None,
        limit: int | None = None,
        commitment: str | None = None,
        max_supported_transaction_version: int = 0,
    ) -> list:
        if not self.helius_enhanced_enabled():
            raise RuntimeError("get_transactions_for_address requires a Helius RPC")
        # Helius specific RPC method - would need custom implementation
        # For now, fall back to standard pagination
        raise NotImplementedError("Helius enhanced getTransactionsForAddress not implemented")

    async def try_fetch_transactions_for_address_all(
        self,
        pubkey: Pubkey,
        before: str | None = None,
        limit: int = 1000,
        max_supported_transaction_version: int = 0,
    ) -> list | None:
        if not self.helius_enhanced_enabled():
            return None
        try:
            out = []
            current_before = before
            while True:
                page = await self.get_transactions_for_address(
                    pubkey,
                    before=current_before,
                    limit=limit,
                    max_supported_transaction_version=max_supported_transaction_version,
                )
                if not page:
                    break
                out.extend(page)
                if len(page) < limit:
                    break
                last_sig = page[-1].transaction.signatures[0] if page else None
                if not last_sig or last_sig == current_before:
                    break
                current_before = last_sig
            return out
        except Exception:
            return None
