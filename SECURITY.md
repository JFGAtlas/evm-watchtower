# Security Policy

Do not report wallet signatures, Telegram bot tokens, private RPC keys, or private monitored addresses in public issues.

Report security issues privately through GitHub security advisories when available, or contact the repository owner directly.

## Wallet Login

EVM Watchtower verifies signed messages server-side and stores only the wallet address and session token. It never asks for private keys or seed phrases.

