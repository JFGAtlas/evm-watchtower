from eth_account import Account

from evm_watchtower.auth import recover_signer, sign_in_message


def test_recover_signer_matches_wallet():
    account = Account.create()
    message = sign_in_message(account.address, "nonce-123", issued_at=1)
    signed = Account.sign_message(__import__("eth_account").messages.encode_defunct(text=message), account.key)
    assert recover_signer(message, signed.signature.hex()) == account.address.lower()

