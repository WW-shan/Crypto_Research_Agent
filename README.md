# Crypto Alpha Agent

Autonomous research agent for crypto market analysis, on-chain signals, and strategy experiments.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
uv run pytest
```

The project uses Python 3.12 and a `src` layout package named `crypto_alpha_agent`.

## Low-Capital Real Data Ingestion

The ingest CLI is safe by default for operators with ordinary infrastructure and a few hundred USD of capital. The offline check initializes the local research SQLite store without network calls, live capital, wallet keys, or order routing:

```bash
uv run crypto-alpha-agent ingest --offline-check --db var/research.sqlite
```

Real network sources are research and paper-validation inputs only and require an explicit `--allow-network` flag. This project excludes MEV/mempool strategies, sub-second CEX-DEX arbitrage, premium RPC-dependent strategies, and live order routing.
