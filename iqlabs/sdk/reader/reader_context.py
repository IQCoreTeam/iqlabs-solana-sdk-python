from solders.pubkey import Pubkey

from ...coder import INSTRUCTION_DISC_TO_NAME
from ...contract import DEFAULT_ANCHOR_PROGRAM_ID


class ReaderContext:
    anchor_program_id = Pubkey.from_string(DEFAULT_ANCHOR_PROGRAM_ID)
    instruction_discriminators = INSTRUCTION_DISC_TO_NAME


reader_context = ReaderContext()
