from typing import Protocol
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import Transaction, VersionedTransaction


class WalletSigner(Protocol):
    @property
    def public_key(self) -> Pubkey: ...
    async def sign_transaction(self, tx: Transaction | VersionedTransaction) -> Transaction | VersionedTransaction: ...
    async def sign_all_transactions(self, txs: list[Transaction | VersionedTransaction]) -> list[Transaction | VersionedTransaction]: ...


class KeypairWalletSigner:
    def __init__(self, keypair: Keypair):
        self._keypair = keypair

    @property
    def public_key(self) -> Pubkey:
        return self._keypair.pubkey()

    async def sign_transaction(self, tx: Transaction | VersionedTransaction) -> Transaction | VersionedTransaction:
        if isinstance(tx, Transaction):
            tx.partial_sign([self._keypair])
        else:
            tx.sign([self._keypair])
        return tx

    async def sign_all_transactions(self, txs: list[Transaction | VersionedTransaction]) -> list[Transaction | VersionedTransaction]:
        for tx in txs:
            if isinstance(tx, Transaction):
                tx.partial_sign([self._keypair])
            else:
                tx.sign([self._keypair])
        return txs


def _is_wallet_signer(signer) -> bool:
    return hasattr(signer, "sign_transaction") and callable(getattr(signer, "sign_transaction"))


def to_wallet_signer(signer: Keypair | WalletSigner) -> WalletSigner:
    if _is_wallet_signer(signer):
        return signer
    return KeypairWalletSigner(signer)


SignerInput = Keypair | WalletSigner


def get_public_key(signer: SignerInput) -> Pubkey:
    if isinstance(signer, Keypair):
        return signer.pubkey()
    return signer.public_key
