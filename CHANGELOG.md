# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2026-05-29

Catches up to TypeScript SDK 0.1.27. `speed` parameter now accepts a raw
override dict in addition to the four preset names.

### Added
- `SessionSpeedOption = Union[str, dict]` — `speed` parameter type used
  by every writer/reader function that accepts a speed.
- `resolve_session_config(speed)` — string|dict|None → always returns a
  fresh `{max_rps, max_concurrency, max_concurrency_upload}` dict.
  Missing dials in a dict override fall back to `DEFAULT_SESSION_SPEED`.

### Changed
- All writer/reader `speed: str | None` parameter type hints widened to
  `SessionSpeedOption | None`. String preset names still work; you can
  now also pass `{"max_rps": 80, "max_concurrency_upload": 30}`.
- Internal helpers (`_resolve_session_config`, `_resolve_upload_config`)
  removed — `resolve_session_config` replaces both, exported from
  `iqlabs.utils`.

## [0.2.0] - 2026-05-29

Catches up to TypeScript SDK 0.1.26. One-to-one parity verified for every
contract, writer, reader, utils, and crypto export.

### Added
- v0.2 fee restructure: `create_table_instruction` now requires the new
  `db_root_creator` account, and `writer.create_table` auto-decodes it
  from the DbRoot state — caller signature unchanged.
- New ix wrappers: `set_root_table_creation_fee_instruction`,
  `clear_root_table_creation_fee_instruction`,
  `transfer_db_root_creator_instruction`.
- `decode_table_meta` now returns `last_timestamp` (for gateways).
- `utils` re-exports: `run_with_concurrency`, `SESSION_SPEED_PROFILES`,
  `DEFAULT_SESSION_SPEED`, `resolve_session_speed`.
- `reader.collect_signatures` for paged signature enumeration.
- `writer_utils.send_tx_with_retries` for stable concurrent chunk uploads.
- `SESSION_SPEED_PROFILES` entries now include `max_concurrency_upload`
  (1 / 5 / 50 / 100 for light/medium/heavy/extreme).

### Changed
- `upload_session` uses `max_concurrency_upload` and `send_tx_with_retries`
  for the chunk-fanout phase.
- IDL refreshed to match mainnet program (v0.2 fee structure).

## [0.1.2] - 2026-02-12

### Fixed
- Fixed Table and Connection account decoders to correctly handle optional fields
  - `gate_mint` field now properly decoded as `Option<Pubkey>` instead of required `Pubkey`
  - `writers` field in Table now properly decoded as `Option<Vec<Pubkey>>`
  - This fixes issues where tables created without gate_mint were incorrectly decoded

## [0.1.1] - 2026-02-12

### Fixed
- Fixed `send_tx` function compatibility with solders >= 0.23
  - Updated Transaction creation to use `Message.new_with_blockhash` instead of deprecated `Transaction.new_with_payer`
  - Fixed `recent_blockhash` attribute error with newer solders versions
  - Fixed signature type handling in `confirm_transaction`
- Improved compatibility with httpx >= 0.28.0

### Changed
- Transaction signing now properly handles both Keypair and WalletSigner types

## [0.1.0] - 2026-01-03

### Added
- Initial release
- Support for on-chain data storage
- Database tables and connections
- Code-in functionality
