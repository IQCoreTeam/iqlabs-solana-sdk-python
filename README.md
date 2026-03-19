# IQLabs SDK (Python)

> **Draft**: This document is in progress and will be refined.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
   - [Data Storage (Code In)](#data-storage-code-in)
   - [User State PDA](#user-state-pda)
   - [Connection PDA](#connection-pda)
   - [Database Tables](#database-tables)
   - [Encryption (Crypto)](#encryption-crypto)

2. [Function Details](#function-details)
   - [Data Storage and Retrieval](#data-storage-and-retrieval)
   - [Connection Management](#connection-management)
   - [Table Management](#table-management)
   - [Encryption](#encryption)
   - [Environment Settings](#environment-settings)

2.1. [Advanced Functions](#advanced-functions) (list only)

---

## Core Concepts

These are the key concepts to know before using the IQLabs SDK.

---

### Data Storage (Code In)

This is how you store any data (files, text, JSON) on-chain.

#### How is it stored?

Depending on data size, the SDK picks the optimal method:

- **Small data (< 700 bytes)**: store immediately, fastest
- **Medium data (< 8.5 KB)**: split into multiple transactions
- **Large data (>= 8.5 KB)**: upload in parallel for speed

#### Key related functions

- [`code_in()`](#code_in): upload data and get a transaction ID
- [`read_code_in()`](#read_code_in): read data back from a transaction ID

---

### User State PDA

An on-chain profile account for a user.

#### What gets stored?

- Profile info (name, profile picture, bio, etc.)
- Number of uploaded files
- Friend request records

> **Note**: Friend requests are not stored as values in the PDA; they are sent as transactions.

#### When is it created?

It is created automatically the first time you call [`code_in()`](#code_in). No extra setup is required, but the first user may need to sign twice.

---

### Connection PDA

An on-chain account that manages relationships between two users (friends, messages, etc.).

#### What states can it have?

- **pending**: a friend request was sent but not accepted yet
- **approved**: the request was accepted and the users are connected
- **blocked**: one side blocked the other

> **Important**: A blocked connection can only be unblocked by the blocker.

#### Key related functions

- [`request_connection()`](#request_connection): send a friend request (creates pending)
- [`manage_connection()`](#manage_connection): approve/reject/block/unblock a request
- [`read_connection()`](#read_connection): check current relationship status
- [`write_connection_row()`](#write_connection_row): exchange messages/data with a connected friend
- [`fetch_user_connections()`](#fetch_user_connections): fetch all connections (sent & received friend requests)

---

### Database Tables

Store JSON data in tables like a database.

#### How are tables created?

You can create tables explicitly with [`create_table()`](#create_table), or implicitly — the first write via [`write_row()`](#write_row) creates the table automatically.

> **Note**: A table is uniquely identified by the combination of `db_root_id` and `table_seed` (table name).

#### Key related functions

- [`create_table()`](#create_table): create a table explicitly
- [`write_row()`](#write_row): add a new row (creates the table if missing)
- [`read_table_rows()`](#read_table_rows): read rows from a table
- [`get_tablelist_from_root()`](#get_tablelist_from_root): list all tables in a database
- [`fetch_inventory_transactions()`](#fetch_inventory_transactions): list uploaded files

---

### Encryption (Crypto)

The SDK includes a built-in encryption module (`iqlabs.crypto`) for encrypting data before storing it on-chain.

#### Three encryption modes

- **DH Encryption** (single recipient): Ephemeral X25519 ECDH → HKDF-SHA256 → AES-256-GCM. Use when encrypting data for one specific recipient.
- **Password Encryption**: PBKDF2-SHA256 (250k iterations) → AES-256-GCM. Use for password-protected data that anyone with the password can decrypt.
- **Multi-recipient Encryption** (PGP-style hybrid): Generates a random content encryption key (CEK), encrypts data once, then wraps the CEK for each recipient via ECDH. Use when encrypting data for multiple recipients.

#### Key derivation

Users can derive a deterministic X25519 keypair from their wallet signature using [`derive_x25519_keypair()`](#derive_x25519_keypair). This means users don't need to manage separate encryption keys — their wallet is the key.

#### Key related functions

- [`derive_x25519_keypair()`](#derive_x25519_keypair): derive encryption keypair from wallet
- [`dh_encrypt()`](#dh_encrypt) / [`dh_decrypt()`](#dh_decrypt): single-recipient encryption
- [`password_encrypt()`](#password_encrypt) / [`password_decrypt()`](#password_decrypt): password-based encryption
- [`multi_encrypt()`](#multi_encrypt) / [`multi_decrypt()`](#multi_decrypt): multi-recipient encryption

---

## Function Details

### Data Storage and Retrieval

#### `code_in()`

| **Parameters** | `connection`: Solana RPC AsyncClient<br>`signer`: Keypair or WalletSigner<br>`chunks`: data to upload (list[str])<br>`filename`: optional filename (str or None)<br>`method`: upload method (int, default: 0)<br>`filetype`: file type hint (str, default: '')<br>`on_progress`: optional progress callback (Callable[[int], None]) |
|----------|--------------------------|
| **Returns** | Transaction signature (str) |

**Example:**
```python
from iqlabs import writer
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

# Upload data
signature = await writer.code_in(connection, signer, ['Hello, blockchain!'])

# Upload with filename
signature = await writer.code_in(connection, signer, ['file contents here'], filename='hello.txt')
```

---

#### `read_code_in()`

| **Parameters** | `tx_signature`: transaction signature (str)<br>`speed`: rate limit profile (optional, str)<br>`on_progress`: optional progress callback (Callable[[int], None]) |
|----------|--------------------------|
| **Returns** | dict with `metadata` (str) and `data` (str or None) |

**Example:**
```python
from iqlabs import reader

result = await reader.read_code_in('5Xg7...')
print(result['data'])      # 'Hello, blockchain!'
print(result['metadata'])  # JSON string with file metadata
```

---

### Connection Management

#### `request_connection()`

| **Parameters** | `connection`: AsyncClient<br>`signer`: Keypair or WalletSigner<br>`db_root_id`: database ID (bytes or str)<br>`party_a`: first user pubkey (str)<br>`party_b`: second user pubkey (str)<br>`table_name`: connection table name (str or bytes)<br>`columns`: column list (list[str or bytes])<br>`id_col`: ID column (str or bytes)<br>`ext_keys`: extension keys (list[str or bytes]) |
|----------|--------------------------|
| **Returns** | Transaction signature (str) |

**Example:**
```python
from iqlabs import writer

await writer.request_connection(
    connection, signer, 'my-db',
    my_wallet_address, friend_wallet_address,
    'dm_table', ['message', 'timestamp'], 'message_id', []
)
```

---

#### `manage_connection()`

> **Note**: There is no high-level SDK wrapper for this function. Use the contract-level instruction builder directly.

| **Parameters** | `builder`: InstructionBuilder<br>`accounts`: dict with `db_root`, `connection_table`, `signer`<br>`args`: dict with `db_root_id`, `connection_seed`, `new_status` |
|----------|--------------------------|
| **Returns** | Instruction |

**Example:**
```python
from iqlabs import contract

# Create an instruction builder
builder = contract.create_instruction_builder(contract.PROGRAM_ID)

# Approve a friend request
approve_ix = contract.manage_connection_instruction(
    builder,
    {"db_root": db_root, "connection_table": connection_table, "signer": my_pubkey},
    {"db_root_id": db_root_id, "connection_seed": connection_seed, "new_status": contract.CONNECTION_STATUS_APPROVED}
)

# Block a user
block_ix = contract.manage_connection_instruction(
    builder,
    {"db_root": db_root, "connection_table": connection_table, "signer": my_pubkey},
    {"db_root_id": db_root_id, "connection_seed": connection_seed, "new_status": contract.CONNECTION_STATUS_BLOCKED}
)
```

---

#### `read_connection()`

| **Parameters** | `db_root_id`: database ID (bytes or str)<br>`party_a`: first wallet (str)<br>`party_b`: second wallet (str) |
|----------|--------------------------|
| **Returns** | dict with `status`, `requester`, `blocker` |

**Example:**
```python
from iqlabs import reader

conn_info = await reader.read_connection('my-db', party_a, party_b)
print(conn_info['status'])  # 'pending' | 'approved' | 'blocked'
```

---

#### `write_connection_row()`

| **Parameters** | `connection`: AsyncClient<br>`signer`: Keypair or WalletSigner<br>`db_root_id`: database ID (bytes or str)<br>`connection_seed`: connection seed (bytes or str)<br>`row_json`: JSON data (str) |
|----------|--------------------------|
| **Returns** | Transaction signature (str) |

**Example:**
```python
from iqlabs import writer
import json

await writer.write_connection_row(
    connection, signer, 'my-db', connection_seed,
    json.dumps({"message_id": "123", "message": "Hello friend!", "timestamp": 1234567890})
)
```

---

#### `fetch_user_connections()`

Fetch all connections (friend requests) for a user by analyzing their UserState PDA transaction history. Each connection includes its `db_root_id`, identifying which app the connection belongs to.

| **Parameters** | `user_pubkey`: user public key (str or Pubkey)<br>`limit`: max number of transactions to fetch (optional)<br>`before`: signature to paginate from (optional)<br>`speed`: rate limit profile (optional) |
|----------|--------------------------|
| **Returns** | List of connection dicts with db_root_id, connection_pda, party_a, party_b, status, requester, blocker, timestamp |

**Example:**
```python
from iqlabs import reader

connections = await reader.fetch_user_connections(
    my_pubkey,
    speed="light",
    limit=100
)

# Filter by status
pending_requests = [c for c in connections if c['status'] == 'pending']
friends = [c for c in connections if c['status'] == 'approved']
blocked = [c for c in connections if c['status'] == 'blocked']

# Check connection details
for conn in connections:
    print(f"Party A: {conn['party_a']} <-> Party B: {conn['party_b']}, status: {conn['status']}")
```

---

#### `update_user_metadata()`

| **Parameters** | `connection`: AsyncClient<br>`signer`: Keypair or WalletSigner<br>`db_root_id`: database ID (bytes or str)<br>`meta`: metadata to store (bytes or str) |
|----------|--------------------------|
| **Returns** | Transaction signature (str) |

**Example:**
```python
from iqlabs import writer

# Store a codeIn tx signature as user metadata
tx_sig = await writer.update_user_metadata(
    connection, signer, 'my-db', meta_tx_signature
)
```

---

### Table Management

#### `create_table()`

| **Parameters** | `connection`: AsyncClient<br>`signer`: Keypair or WalletSigner<br>`db_root_id`: database ID (bytes or str)<br>`table_seed`: table seed (bytes or str)<br>`table_name`: display name (str or bytes)<br>`column_names`: column names (list[str or bytes])<br>`id_col`: ID column (str or bytes)<br>`ext_keys`: extension keys (list[str or bytes])<br>`gate_mint`: optional SPL token gate (Pubkey)<br>`writers`: optional writer whitelist (list[Pubkey]) |
|----------|--------------------------|
| **Returns** | Transaction signature (str) |

**Example:**
```python
from iqlabs import writer

await writer.create_table(
    connection, signer, 'my-db', 'users', 'Users Table',
    ['name', 'email'], 'user_id', []
)
```

---

#### `write_row()`

| **Parameters** | `connection`: AsyncClient<br>`signer`: Keypair or WalletSigner<br>`db_root_id`: database ID (bytes or str)<br>`table_seed`: table name (bytes or str)<br>`row_json`: JSON row data (str)<br>`skip_confirmation`: skip tx confirmation (default: False) |
|----------|--------------------------|
| **Returns** | Transaction signature (str) |

**Example:**
```python
from iqlabs import writer
import json

# Write the first row to create the table
await writer.write_row(connection, signer, 'my-db', 'users', json.dumps({
    "id": 1, "name": "Alice", "email": "alice@example.com"
}))

# Add another row to the same table
await writer.write_row(connection, signer, 'my-db', 'users', json.dumps({
    "id": 2, "name": "Bob", "email": "bob@example.com"
}))
```

---

#### `read_table_rows()`

| **Parameters** | `account`: table PDA (Pubkey or str)<br>`before`: signature cursor for pagination (optional)<br>`limit`: max number of rows to fetch (optional)<br>`speed`: rate limit profile (optional) |
|----------|--------------------------|
| **Returns** | `list[dict]` |

**Example:**
```python
from iqlabs import reader

# Basic usage
rows = await reader.read_table_rows(table_pda, limit=50)

# Cursor-based pagination
older_rows = await reader.read_table_rows(table_pda, limit=50, before="sig...")
```

---

#### `get_tablelist_from_root()`

| **Parameters** | `connection`: AsyncClient<br>`db_root_id`: database ID (bytes or str) |
|----------|--------------------------|
| **Returns** | dict with `root_pda`, `creator`, `table_seeds`, `global_table_seeds` |

**Example:**
```python
from iqlabs import reader

result = await reader.get_tablelist_from_root(connection, 'my-db')
print('Creator:', result['creator'])
print('Table seeds:', result['table_seeds'])
```

---

#### `fetch_inventory_transactions()`

| **Parameters** | `public_key`: user public key (Pubkey)<br>`limit`: max count (int)<br>`before`: pagination cursor (optional, str) |
|----------|--------------------------|
| **Returns** | Transaction list |

**Example:**
```python
from iqlabs import reader
import json

my_files = await reader.fetch_inventory_transactions(my_pubkey, 20)
for tx in my_files:
    metadata = None
    try:
        metadata = json.loads(tx['metadata'])
    except:
        metadata = None

    if metadata and 'data' in metadata:
        inline_data = metadata['data'] if isinstance(metadata['data'], str) else json.dumps(metadata['data'])
        print(f"Inline data: {inline_data}")
    else:
        print(f"Signature: {tx['signature']}")
```

---

### Encryption

#### `derive_x25519_keypair()`

Derive a deterministic X25519 keypair from a wallet signature. The same wallet always produces the same keypair.

| **Parameters** | `sign_message`: async sign function `Callable[[bytes], Awaitable[bytes]]` |
|----------|--------------------------|
| **Returns** | dict with `priv_key` (bytes) and `pub_key` (bytes) |

**Example:**
```python
from iqlabs import crypto

keypair = await crypto.derive_x25519_keypair(wallet.sign_message)
pub_hex = keypair['pub_key'].hex()
```

---

#### `dh_encrypt()`

| **Parameters** | `recipient_pub_hex`: recipient's X25519 public key (hex str)<br>`plaintext`: data to encrypt (bytes) |
|----------|--------------------------|
| **Returns** | dict with `sender_pub`, `iv`, `ciphertext` (all hex str) |

#### `dh_decrypt()`

| **Parameters** | `priv_key`: recipient's private key (bytes)<br>`sender_pub_hex`: sender's public key from encrypt result (hex str)<br>`iv_hex`: IV from encrypt result (hex str)<br>`ciphertext_hex`: ciphertext from encrypt result (hex str) |
|----------|--------------------------|
| **Returns** | bytes (decrypted plaintext) |

**Example:**
```python
from iqlabs import crypto

# Encrypt
encrypted = crypto.dh_encrypt(recipient_pub_hex, b'secret message')

# Decrypt (recipient side)
decrypted = crypto.dh_decrypt(
    recipient_priv_key, encrypted['sender_pub'], encrypted['iv'], encrypted['ciphertext']
)
```

---

#### `password_encrypt()`

| **Parameters** | `password`: password (str)<br>`plaintext`: data to encrypt (bytes) |
|----------|--------------------------|
| **Returns** | dict with `salt`, `iv`, `ciphertext` (all hex str) |

#### `password_decrypt()`

| **Parameters** | `password`: password (str)<br>`salt_hex`: salt from encrypt result (hex str)<br>`iv_hex`: IV from encrypt result (hex str)<br>`ciphertext_hex`: ciphertext from encrypt result (hex str) |
|----------|--------------------------|
| **Returns** | bytes (decrypted plaintext) |

**Example:**
```python
from iqlabs import crypto

encrypted = crypto.password_encrypt('my-password', b'secret data')
decrypted = crypto.password_decrypt(
    'my-password', encrypted['salt'], encrypted['iv'], encrypted['ciphertext']
)
```

---

#### `multi_encrypt()`

| **Parameters** | `recipient_pub_hexes`: recipient public keys (list[str])<br>`plaintext`: data to encrypt (bytes) |
|----------|--------------------------|
| **Returns** | dict with `recipients` (list[RecipientEntry]), `iv`, `ciphertext` |

#### `multi_decrypt()`

| **Parameters** | `priv_key`: your private key (bytes)<br>`pub_key_hex`: your public key (hex str)<br>`encrypted`: the MultiEncryptResult dict |
|----------|--------------------------|
| **Returns** | bytes (decrypted plaintext) |

**Example:**
```python
from iqlabs import crypto

# Encrypt for multiple recipients
encrypted = crypto.multi_encrypt(
    [alice_pub_hex, bob_pub_hex, carol_pub_hex],
    b'group secret'
)

# Each recipient decrypts with their own key
plaintext = crypto.multi_decrypt(alice_priv_key, alice_pub_hex, encrypted)
```

---

### Environment Settings

#### `set_rpc_url()`

| **Parameters** | `url`: Solana RPC URL (str) |
|----------|--------------------------|
| **Returns** | None |

**Example:**
```python
from iqlabs import set_rpc_url

set_rpc_url('https://your-rpc.example.com')
```

---

## Advanced Functions

These functions are advanced/internal, so this doc lists them only. For details, please see our [developer docs](https://iqlabs.dev).

- `manage_row_data()` (`writer`)
- `read_user_state()` (`reader`)
- `read_inventory_metadata()` (`reader`)
- `read_user_inventory_code_in_from_tx()` (`reader`)
- `get_session_pda_list()` (`reader`)
- `derive_dm_seed()` (`utils`)
- `to_seed_bytes()` (`utils`)
- `hex_to_bytes()` / `bytes_to_hex()` / `validate_pub_key()` (`crypto`)

---

## Additional Resources
- [IQLabs Official X](https://x.com/IQLabsOfficial)
- [IQLabs Official Website](https://iqlabs.dev)
