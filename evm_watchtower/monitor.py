from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from typing import Any

from .chains import CHAINS, ChainConfig
from .parser import normalize_address, parse_transaction
from .rpc import RpcClient
from .store import Store
from .telegram import render_event_message, send_telegram


def monitors_by_chain(monitors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for monitor in monitors:
        for chain in monitor["chains"]:
            if chain in CHAINS:
                grouped[chain].append(monitor)
    return grouped


class ChainMonitor:
    def __init__(self, store: Store):
        self.store = store
        self.interval = int(os.getenv("MONITOR_INTERVAL_SECONDS", "8"))
        self.max_blocks = int(os.getenv("MAX_BLOCKS_PER_POLL", "4"))
        self.running = False

    async def run_forever(self) -> None:
        self.running = True
        while self.running:
            await self.poll_once()
            await asyncio.sleep(self.interval)

    async def poll_once(self) -> None:
        grouped = monitors_by_chain(self.store.list_monitors(active_only=True))
        for chain_key, monitors in grouped.items():
            try:
                await self.poll_chain(CHAINS[chain_key], monitors)
            except Exception as exc:
                print(f"[watchtower] {chain_key} poll failed: {exc}")

    async def poll_chain(self, chain: ChainConfig, monitors: list[dict[str, Any]]) -> None:
        client = RpcClient(chain)
        latest = await client.latest_block_number()
        last = self.store.get_chain_state(chain.key)
        if last is None:
            self.store.set_chain_state(chain.key, latest)
            return
        if latest <= last:
            return
        stop = min(latest, last + self.max_blocks)
        watched = {normalize_address(monitor["address"]) for monitor in monitors}
        monitor_lookup = {(monitor["user_id"], normalize_address(monitor["address"])): monitor for monitor in monitors}

        for block_number in range(last + 1, stop + 1):
            block = await client.block_by_number(block_number)
            for tx in block.get("transactions", []):
                await self.inspect_transaction(chain, client, tx, watched, monitor_lookup)
            self.store.set_chain_state(chain.key, block_number)

    async def inspect_transaction(
        self,
        chain: ChainConfig,
        client: RpcClient,
        tx: dict[str, Any],
        watched: set[str],
        monitor_lookup: dict[tuple[int, str], dict[str, Any]],
    ) -> None:
        receipt = await client.transaction_receipt(tx["hash"])
        trace = None
        if os.getenv("ENABLE_TRACE", "false").lower() in {"1", "true", "yes"}:
            trace = await client.transaction_trace(tx["hash"])
        parsed = parse_transaction(chain, tx, receipt, watched, trace)
        for event in parsed:
            for (user_id, address), monitor in monitor_lookup.items():
                if address != event["watched_address"]:
                    continue
                stored = {
                    **event,
                    "user_id": user_id,
                    "monitor_id": monitor["id"],
                    "event_key": f"{event['event_key']}:{user_id}:{monitor['id']}",
                }
                if self.store.save_event(stored):
                    await self.notify_user(user_id, stored)

    async def notify_user(self, user_id: int, event: dict[str, Any]) -> None:
        settings = self.store.telegram_for_user(user_id)
        if not settings:
            return
        try:
            await send_telegram(settings["bot_token"], settings["chat_id"], render_event_message(event))
        except Exception as exc:
            print(f"[watchtower] telegram notify failed for user {user_id}: {exc}")
