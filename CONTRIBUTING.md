# Contributing

Thanks for helping improve EVM Watchtower.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Pull Requests

- Add tests for parser, monitor, auth, or storage behavior changes.
- Keep chain integrations configurable through environment variables.
- Do not commit RPC keys, bot tokens, database files, or private addresses.

