# EVM Watchtower

EVM Watchtower is a wallet-gated address activity monitor for Ethereum, Base, and BNB Smart Chain.

Users sign in with an EVM wallet, add addresses to monitor, choose which mainnets to watch, and connect a Telegram bot for immediate alerts. When a watched address becomes active, Watchtower parses the transaction and explains whether it looks like a receive, send, buy, sell, or mixed swap.

Static project page:

```text
https://jfgatlas.github.io/evm-watchtower/
```

Live hosted app:

```text
http://131.186.56.210/
```

## Features

- EVM wallet login with signed-message verification
- Per-user monitored addresses
- Chain selection per address
- Ethereum Mainnet, Base Mainnet, and BNB Smart Chain support
- Native transfer detection
- ERC20 and ERC721 `Transfer` log detection
- ERC1155 `TransferSingle` and `TransferBatch` detection
- ERC20/ERC721 `Approval` and ERC721/ERC1155 `ApprovalForAll` detection
- Direct contract-call detection even when no asset moves
- Generic indexed event-topic matching when the watched address appears in logs
- Optional `debug_traceTransaction` support for internal calls and internal native transfers
- Buy/sell/swap heuristics from token and native asset flows
- Telegram bot notifications
- SQLite storage, no external database required
- FastAPI Web app and background chain monitor
- Docker, CI, tests, and MIT license

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
evm-watchtower
```

Open:

```text
http://127.0.0.1:8877
```

## Telegram Setup

1. Create a bot with `@BotFather`.
2. Copy the bot token.
3. Send a message to your bot.
4. Get your chat id, then save bot token and chat id in the Watchtower UI.

## Chain RPC Defaults

| Chain | Env var | Default |
| --- | --- | --- |
| Ethereum | `ETHEREUM_RPC_URL` | `https://eth.llamarpc.com` |
| Base | `BASE_RPC_URL` | `https://base.llamarpc.com` |
| BNB Smart Chain | `BSC_RPC_URL` | `https://bsc-dataseed.binance.org` |

For production, use reliable RPC providers. Public RPC endpoints can rate-limit.

## Docker

```bash
docker build -t evm-watchtower .
docker run --rm -p 8877:8877 --env-file .env -v watchtower-data:/data evm-watchtower
```

Set `DATABASE_PATH=/data/watchtower.sqlite3` when using Docker volumes.

## How Parsing Works

Watchtower scans new blocks on selected chains. For every transaction, it checks:

- Native value moving to or from a watched address
- Direct transaction sender/receiver involvement
- ERC20/ERC721 `Transfer` logs involving a watched address
- ERC1155 transfer logs involving a watched address
- Approval and operator-approval events involving a watched address
- Any indexed event topic containing the watched address
- Combined in/out asset flow inside the same transaction
- Optional internal call traces when `ENABLE_TRACE=true` and your RPC supports `debug_traceTransaction`

Heuristics:

- Native out + ERC20 in: likely buy
- ERC20 out + native in: likely sell
- Only inbound movement: receive
- Only outbound movement: send
- Inbound and outbound token movement: swap/mixed activity
- Direct address-to-contract interaction with no asset movement: contract call
- Approval event: approval
- Indexed event match: contract event

## Limits

This is an open-source monitor, not an indexer. It works well for lightweight monitoring, but high-volume production usage should move parsing to a queue and use dedicated RPC or indexing providers.

Internal transfers are not available from plain `eth_getTransactionReceipt`. To catch them, use an RPC provider that supports `debug_traceTransaction` and set:

```bash
ENABLE_TRACE=true
```

Public RPC endpoints often disable tracing, so production deployments should use paid RPC, archive/tracing nodes, or explorer/indexer APIs.

## Roadmap

- WebSocket RPC subscriptions
- ERC20 metadata cache
- NFT transfer parsing
- Stablecoin-aware swap classification
- Per-monitor alert thresholds
- Telegram test button

## License

MIT
