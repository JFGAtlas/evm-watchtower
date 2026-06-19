from __future__ import annotations

from typing import Any

import httpx

from .chains import ChainConfig


class RpcClient:
    def __init__(self, chain: ChainConfig):
        self.chain = chain

    async def call(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.chain.rpc_url, json=payload)
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise RuntimeError(body["error"])
        return body.get("result")

    async def latest_block_number(self) -> int:
        return int(await self.call("eth_blockNumber", []), 16)

    async def block_by_number(self, number: int) -> dict[str, Any]:
        result = await self.call("eth_getBlockByNumber", [hex(number), True])
        if not result:
            raise RuntimeError(f"Block {number} not found on {self.chain.key}")
        return result

    async def transaction_receipt(self, tx_hash: str) -> dict[str, Any]:
        result = await self.call("eth_getTransactionReceipt", [tx_hash])
        if not result:
            raise RuntimeError(f"Receipt {tx_hash} not found on {self.chain.key}")
        return result

    async def transaction_trace(self, tx_hash: str) -> dict[str, Any] | None:
        try:
            return await self.call("debug_traceTransaction", [tx_hash, {"tracer": "callTracer"}])
        except Exception:
            return None
