from solders.pubkey import Pubkey

from ...coder import decode_instruction, INSTRUCTION_DISC_TO_NAME
from ...contract import (
    DEFAULT_ANCHOR_PROGRAM_ID,
    DEFAULT_PINOCCHIO_PROGRAM_ID,
    resolve_contract_runtime,
)
from ...constants import DEFAULT_CONTRACT_MODE


class ReaderContext:
    anchor_program_id = Pubkey.from_string(DEFAULT_ANCHOR_PROGRAM_ID)
    pinocchio_program_id = Pubkey.from_string(DEFAULT_PINOCCHIO_PROGRAM_ID)
    instruction_discriminators = INSTRUCTION_DISC_TO_NAME

    @staticmethod
    def decode_instruction(data: bytes) -> dict | None:
        return decode_instruction(data)


reader_context = ReaderContext()


def resolve_reader_program_id(mode: str = DEFAULT_CONTRACT_MODE) -> Pubkey:
    runtime = resolve_contract_runtime(mode)
    return reader_context.anchor_program_id if runtime == "anchor" else reader_context.pinocchio_program_id


def resolve_reader_mode_from_tx(tx) -> str:
    message = tx.transaction.message
    account_keys = message.account_keys

    saw_anchor = False
    saw_pinocchio = False

    for ix in message.instructions:
        program_id = account_keys[ix.program_id_index]
        if program_id == reader_context.anchor_program_id:
            saw_anchor = True
        if program_id == reader_context.pinocchio_program_id:
            saw_pinocchio = True

    if saw_anchor and not saw_pinocchio:
        return "anchor"
    if saw_pinocchio and not saw_anchor:
        return "pinocchio"

    return resolve_contract_runtime(DEFAULT_CONTRACT_MODE)
