from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_utils import keccak

from .chains import ChainConfig


def event_topic(signature: str) -> str:
    return "0x" + keccak(text=signature).hex()


TRANSFER_TOPIC = event_topic("Transfer(address,address,uint256)")
APPROVAL_TOPIC = event_topic("Approval(address,address,uint256)")
APPROVAL_FOR_ALL_TOPIC = event_topic("ApprovalForAll(address,address,bool)")
ERC1155_TRANSFER_SINGLE_TOPIC = event_topic("TransferSingle(address,address,address,uint256,uint256)")
ERC1155_TRANSFER_BATCH_TOPIC = event_topic("TransferBatch(address,address,address,uint256[],uint256[])")
STABLE_HINTS = {"usdc", "usdt", "dai", "busd", "fdusd"}


@dataclass
class AssetMove:
    kind: str
    asset: str
    token_address: str | None
    from_address: str
    to_address: str
    raw_value: int
    direction: str
    note: str = ""


def normalize_address(address: str | None) -> str:
    if not address:
        return ""
    address = address.lower()
    if address.startswith("0x") and len(address) == 42:
        return address
    if address.startswith("0x") and len(address) == 66:
        return "0x" + address[-40:]
    return address


def hex_int(value: str | None) -> int:
    return int(value or "0x0", 16)


def short(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}" if len(address) == 42 else address


def topic_address(topic: str | None) -> str:
    topic = (topic or "").lower()
    if topic.startswith("0x") and len(topic) == 66:
        return "0x" + topic[-40:]
    return ""


def native_move(tx: dict[str, Any], watched: str, chain: ChainConfig) -> AssetMove | None:
    value = hex_int(tx.get("value"))
    if value <= 0:
        return None
    from_addr = normalize_address(tx.get("from"))
    to_addr = normalize_address(tx.get("to"))
    if watched not in {from_addr, to_addr}:
        return None
    return AssetMove(
        kind="native_transfer",
        asset=chain.native_symbol,
        token_address=None,
        from_address=from_addr,
        to_address=to_addr,
        raw_value=value,
        direction="in" if to_addr == watched else "out",
    )


def direct_call_move(tx: dict[str, Any], watched: str) -> AssetMove | None:
    from_addr = normalize_address(tx.get("from"))
    to_addr = normalize_address(tx.get("to"))
    if watched not in {from_addr, to_addr}:
        return None
    return AssetMove(
        kind="contract_call",
        asset="contract interaction",
        token_address=to_addr if from_addr == watched else None,
        from_address=from_addr,
        to_address=to_addr,
        raw_value=0,
        direction="out" if from_addr == watched else "in",
        note="Address appeared as transaction sender or receiver.",
    )


def log_moves(receipt: dict[str, Any], watched: str) -> list[AssetMove]:
    moves: list[AssetMove] = []
    for log in receipt.get("logs", []):
        topics = [topic.lower() for topic in log.get("topics", [])]
        if not topics:
            continue
        token = normalize_address(log.get("address"))

        if len(topics) >= 3 and topics[0] == TRANSFER_TOPIC:
            from_addr = topic_address(topics[1])
            to_addr = topic_address(topics[2])
            if watched in {from_addr, to_addr}:
                moves.append(
                    AssetMove(
                        kind="token_transfer",
                        asset=f"ERC20/ERC721 {short(token)}",
                        token_address=token,
                        from_address=from_addr,
                        to_address=to_addr,
                        raw_value=hex_int(log.get("data")),
                        direction="in" if to_addr == watched else "out",
                        note="ERC20 or ERC721 Transfer event.",
                    )
                )
                continue

        if len(topics) >= 4 and topics[0] in {ERC1155_TRANSFER_SINGLE_TOPIC, ERC1155_TRANSFER_BATCH_TOPIC}:
            from_addr = topic_address(topics[2])
            to_addr = topic_address(topics[3])
            if watched in {from_addr, to_addr}:
                moves.append(
                    AssetMove(
                        kind="erc1155_transfer",
                        asset=f"ERC1155 {short(token)}",
                        token_address=token,
                        from_address=from_addr,
                        to_address=to_addr,
                        raw_value=0,
                        direction="in" if to_addr == watched else "out",
                        note="ERC1155 TransferSingle/TransferBatch event.",
                    )
                )
                continue

        if len(topics) >= 3 and topics[0] == APPROVAL_TOPIC:
            owner = topic_address(topics[1])
            spender = topic_address(topics[2])
            if watched in {owner, spender}:
                moves.append(
                    AssetMove(
                        kind="approval",
                        asset=f"approval {short(token)}",
                        token_address=token,
                        from_address=owner,
                        to_address=spender,
                        raw_value=hex_int(log.get("data")),
                        direction="approval",
                        note="ERC20/ERC721 Approval event.",
                    )
                )
                continue

        if len(topics) >= 3 and topics[0] == APPROVAL_FOR_ALL_TOPIC:
            owner = topic_address(topics[1])
            operator = topic_address(topics[2])
            if watched in {owner, operator}:
                moves.append(
                    AssetMove(
                        kind="approval_for_all",
                        asset=f"operator approval {short(token)}",
                        token_address=token,
                        from_address=owner,
                        to_address=operator,
                        raw_value=0,
                        direction="approval",
                        note="ERC721/ERC1155 ApprovalForAll event.",
                    )
                )
                continue

        indexed_addresses = [topic_address(topic) for topic in topics[1:]]
        if watched in indexed_addresses:
            moves.append(
                AssetMove(
                    kind="contract_event",
                    asset=f"event {topics[0][:10]} on {short(token)}",
                    token_address=token,
                    from_address=watched,
                    to_address=token,
                    raw_value=0,
                    direction="event",
                    note="Watched address appeared in an indexed event topic.",
                )
            )
    return moves


def trace_moves(trace: dict[str, Any] | None, watched: str, chain: ChainConfig) -> list[AssetMove]:
    if not trace:
        return []
    moves: list[AssetMove] = []

    def visit(call: dict[str, Any]) -> None:
        from_addr = normalize_address(call.get("from"))
        to_addr = normalize_address(call.get("to"))
        value = hex_int(call.get("value"))
        if watched in {from_addr, to_addr}:
            moves.append(
                AssetMove(
                    kind="internal_call" if value == 0 else "internal_native_transfer",
                    asset=chain.native_symbol if value else "internal contract call",
                    token_address=None,
                    from_address=from_addr,
                    to_address=to_addr,
                    raw_value=value,
                    direction="in" if to_addr == watched else "out",
                    note="Detected via debug_traceTransaction callTracer.",
                )
            )
        for child in call.get("calls", []) or []:
            visit(child)

    visit(trace)
    return moves


def classify_action(moves: list[AssetMove]) -> tuple[str, str]:
    inbound = [move for move in moves if move.direction == "in"]
    outbound = [move for move in moves if move.direction == "out"]
    approvals = [move for move in moves if move.direction == "approval"]
    events = [move for move in moves if move.direction == "event"]
    if inbound and outbound:
        out_native = any(move.token_address is None for move in outbound)
        in_token = any(move.token_address is not None for move in inbound)
        out_token = any(move.token_address is not None for move in outbound)
        in_native = any(move.token_address is None for move in inbound)
        if out_native and in_token:
            return "buy", "swap"
        if out_token and in_native:
            return "sell", "swap"
        return "swap", "mixed"
    if inbound:
        return "receive", "in"
    if outbound:
        if any(move.kind in {"contract_call", "internal_call"} for move in outbound):
            return "contract_call", "out"
        return "send", "out"
    if approvals:
        return "approval", "approval"
    if events:
        return "contract_event", "event"
    return "activity", "unknown"


def summarize(chain: ChainConfig, tx: dict[str, Any], watched: str, moves: list[AssetMove]) -> dict[str, Any]:
    action, direction = classify_action(moves)
    tx_hash = tx.get("hash", "")
    block_number = hex_int(tx.get("blockNumber"))
    explorer = f"{chain.explorer_url}/tx/{tx_hash}"
    parts = []
    for move in moves[:4]:
        if move.direction == "in":
            verb = "received"
        elif move.direction == "out":
            verb = "sent/called"
        elif move.direction == "approval":
            verb = "approved"
        else:
            verb = "matched"
        parts.append(f"{verb} {move.asset} {short(move.from_address)} -> {short(move.to_address)}")
    summary = f"{chain.name}: {short(watched)} {action} - " + "; ".join(parts)
    return {
        "chain_key": chain.key,
        "tx_hash": tx_hash,
        "block_number": block_number,
        "watched_address": watched,
        "action": action,
        "direction": direction,
        "summary": summary,
        "details": {
            "explorer": explorer,
            "from": normalize_address(tx.get("from")),
            "to": normalize_address(tx.get("to")),
            "moves": [move.__dict__ for move in moves],
        },
    }


def parse_transaction(
    chain: ChainConfig,
    tx: dict[str, Any],
    receipt: dict[str, Any],
    watched_addresses: set[str],
    trace: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for watched in watched_addresses:
        moves: list[AssetMove] = []
        move = native_move(tx, watched, chain)
        if move:
            moves.append(move)
        moves.extend(log_moves(receipt, watched))
        moves.extend(trace_moves(trace, watched, chain))
        if not moves:
            call = direct_call_move(tx, watched)
            if call:
                moves.append(call)
        if not moves:
            continue
        event = summarize(chain, tx, watched, moves)
        event["event_key"] = f"{chain.key}:{event['tx_hash']}:{watched}"
        events.append(event)
    return events
