from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ChainConfig:
    key: str
    name: str
    chain_id: int
    native_symbol: str
    rpc_env: str
    default_rpc_url: str
    explorer_url: str

    @property
    def rpc_url(self) -> str:
        return os.getenv(self.rpc_env, self.default_rpc_url)


CHAINS: dict[str, ChainConfig] = {
    "ethereum": ChainConfig(
        key="ethereum",
        name="Ethereum Mainnet",
        chain_id=1,
        native_symbol="ETH",
        rpc_env="ETHEREUM_RPC_URL",
        default_rpc_url="https://eth.llamarpc.com",
        explorer_url="https://etherscan.io",
    ),
    "base": ChainConfig(
        key="base",
        name="Base Mainnet",
        chain_id=8453,
        native_symbol="ETH",
        rpc_env="BASE_RPC_URL",
        default_rpc_url="https://base.llamarpc.com",
        explorer_url="https://basescan.org",
    ),
    "bsc": ChainConfig(
        key="bsc",
        name="BNB Smart Chain",
        chain_id=56,
        native_symbol="BNB",
        rpc_env="BSC_RPC_URL",
        default_rpc_url="https://bsc-dataseed.binance.org",
        explorer_url="https://bscscan.com",
    ),
}


def chain_or_raise(key: str) -> ChainConfig:
    if key not in CHAINS:
        raise KeyError(f"Unsupported chain: {key}")
    return CHAINS[key]

