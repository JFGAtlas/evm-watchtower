from __future__ import annotations

import secrets
import time

from eth_account import Account
from eth_account.messages import encode_defunct


def normalize_address(address: str) -> str:
    address = (address or "").strip()
    if not address.startswith("0x") or len(address) != 42:
        raise ValueError("Invalid EVM address")
    return address.lower()


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def session_token() -> str:
    return secrets.token_urlsafe(32)


def sign_in_message(address: str, nonce: str, issued_at: int | None = None) -> str:
    issued = issued_at or int(time.time())
    return (
        "EVM Watchtower wants you to sign in with your wallet.\n\n"
        f"Address: {normalize_address(address)}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued}\n\n"
        "Only sign this message if you trust this app."
    )


def recover_signer(message: str, signature: str) -> str:
    encoded = encode_defunct(text=message)
    return Account.recover_message(encoded, signature=signature).lower()

