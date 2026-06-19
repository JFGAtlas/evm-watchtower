from evm_watchtower.chains import CHAINS
from evm_watchtower.parser import (
    APPROVAL_TOPIC,
    ERC1155_TRANSFER_SINGLE_TOPIC,
    TRANSFER_TOPIC,
    parse_transaction,
)


WATCHED = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
TOKEN = "0x3333333333333333333333333333333333333333"


def topic(address: str) -> str:
    return "0x" + "0" * 24 + address.removeprefix("0x")


def test_parse_native_receive():
    tx = {
        "hash": "0xabc",
        "from": OTHER,
        "to": WATCHED,
        "value": hex(10**18),
        "blockNumber": hex(100),
    }
    events = parse_transaction(CHAINS["ethereum"], tx, {"logs": []}, {WATCHED})
    assert events[0]["action"] == "receive"
    assert events[0]["direction"] == "in"


def test_parse_buy_from_native_out_and_token_in():
    tx = {
        "hash": "0xdef",
        "from": WATCHED,
        "to": OTHER,
        "value": hex(10**17),
        "blockNumber": hex(101),
    }
    receipt = {
        "logs": [
            {
                "address": TOKEN,
                "topics": [TRANSFER_TOPIC, topic(OTHER), topic(WATCHED)],
                "data": hex(5000),
            }
        ]
    }
    events = parse_transaction(CHAINS["base"], tx, receipt, {WATCHED})
    assert events[0]["action"] == "buy"
    assert events[0]["direction"] == "swap"


def test_parse_contract_call_without_asset_move():
    tx = {
        "hash": "0xcall",
        "from": WATCHED,
        "to": OTHER,
        "value": "0x0",
        "blockNumber": hex(102),
    }
    events = parse_transaction(CHAINS["bsc"], tx, {"logs": []}, {WATCHED})
    assert events[0]["action"] == "contract_call"


def test_parse_approval_event():
    tx = {
        "hash": "0xapproval",
        "from": WATCHED,
        "to": TOKEN,
        "value": "0x0",
        "blockNumber": hex(103),
    }
    receipt = {
        "logs": [
            {
                "address": TOKEN,
                "topics": [APPROVAL_TOPIC, topic(WATCHED), topic(OTHER)],
                "data": hex(999),
            }
        ]
    }
    events = parse_transaction(CHAINS["ethereum"], tx, receipt, {WATCHED})
    assert events[0]["action"] == "approval"


def test_parse_erc1155_transfer():
    tx = {
        "hash": "0x1155",
        "from": OTHER,
        "to": TOKEN,
        "value": "0x0",
        "blockNumber": hex(104),
    }
    receipt = {
        "logs": [
            {
                "address": TOKEN,
                "topics": [ERC1155_TRANSFER_SINGLE_TOPIC, topic(OTHER), topic(OTHER), topic(WATCHED)],
                "data": "0x" + "0" * 128,
            }
        ]
    }
    events = parse_transaction(CHAINS["base"], tx, receipt, {WATCHED})
    assert events[0]["action"] == "receive"
    assert events[0]["details"]["moves"][0]["kind"] == "erc1155_transfer"
