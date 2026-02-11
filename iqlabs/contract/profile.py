from solders.pubkey import Pubkey

from ..constants import DEFAULT_CONTRACT_MODE
from .constants import DEFAULT_ANCHOR_PROGRAM_ID, DEFAULT_PINOCCHIO_PROGRAM_ID

DEFAULT_PROGRAM_IDS = {
    "anchor": Pubkey.from_string(DEFAULT_ANCHOR_PROGRAM_ID),
    "pinocchio": Pubkey.from_string(DEFAULT_PINOCCHIO_PROGRAM_ID),
}


def resolve_contract_runtime(mode: str = DEFAULT_CONTRACT_MODE) -> str:
    return "pinocchio" if mode == "pinocchio" else "anchor"


def get_program_id(mode: str = DEFAULT_CONTRACT_MODE) -> Pubkey:
    return DEFAULT_PROGRAM_IDS[resolve_contract_runtime(mode)]
