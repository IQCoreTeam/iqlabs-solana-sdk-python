DEFAULT_LINKED_LIST_THRESHOLD = 10
DIRECT_METADATA_MAX_BYTES = 700
CHUNK_SIZE = 850
DEFAULT_WRITE_FEE_RECEIVER = "EWNSTD8tikwqHMcRNuuNbZrnYJUiJdKq9UXLXSEU4wZ1"
DEFAULT_IQ_MINT = "3uXACfojUrya7VH51jVC1DCHq3uzK4A7g469Q954LABS"

# v1 transaction profile (SIMD-0296 raises the tx cap from 1,232 to 4,096
# bytes). Chunks stay ~500 bytes under the cap to leave room for signature,
# account keys, config fields, and the JSON envelope. Mirrors the TS SDK.
CHUNK_SIZE_V1 = 3600
DIRECT_METADATA_MAX_BYTES_V1 = 3400

# Post-upgrade account sizes from user_initialize (IQLabsContract#3):
# code_account   8 + 1 + 1 + 1 + (4 + 4096) + (4 + 100)
# user_inventory 8 + 1 + (4 + 100) + (4 + 4096)
# Accounts smaller than this were created pre-upgrade and must be grown
# with realloc_account before a v1-sized write.
CODE_ACCOUNT_SPACE = 4215
USER_INVENTORY_SPACE = 4213

# Feature gate for v1 transactions; owned by the Feature program with an
# activation slot once live.
TX_V1_FEATURE_GATE = "txv1aq4pp281K9um3tnPgkfX8UqtFT6wcVW3hNezGLL"
FEATURE_PROGRAM_ID = "Feature111111111111111111111111111111111111"
