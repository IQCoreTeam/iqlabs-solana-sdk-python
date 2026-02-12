# Changelog

All notable changes to this project will be documented in this file.

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
