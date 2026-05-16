# Crypto Alpha Agent

Autonomous research agent for crypto market analysis, on-chain signals, and strategy experiments.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
uv run pytest
```

The project uses Python 3.12 and a `src` layout package named `crypto_alpha_agent`.

## Project Direction

The persistent project goal and constraints are documented in
[`docs/project-charter.md`](docs/project-charter.md). The current delivery plan is
tracked in [`docs/roadmap.md`](docs/roadmap.md).

In short: this project optimizes for low-capital crypto alpha research, not
speed arbitrage. The default workflow is real data ingestion, validation,
reflection, reporting, and paper evidence before any live trading discussion.

## Low-Capital Real Data Ingestion

The ingest CLI is safe by default for operators with ordinary infrastructure and a few hundred USD of capital. The offline check initializes the local research SQLite store without network calls, live capital, wallet keys, or order routing:

```bash
uv run crypto-alpha-agent ingest --offline-check --db var/research.sqlite
```

Real network sources are research and paper-validation inputs only and require an explicit `--allow-network` flag. This project excludes MEV/mempool strategies, sub-second CEX-DEX arbitrage, premium RPC-dependent strategies, and live order routing.

## Phase 1 Research Loop

The Phase 1 closed-loop workflow can pull Binance Public Data candles, store
local research records, generate research-only hypotheses, and optionally write
a Markdown report:

```bash
uv run crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --source binance-public \
  --symbol BTCUSDT \
  --timeframe 1h \
  --year 2026 \
  --month 5 \
  --current-capital-usd 300 \
  --allow-network \
  --report-out var/reports/daily.md
```

This command pulls public historical data only. It writes local SQLite records,
generates research-only hypotheses, and writes the optional Markdown report when
`--report-out` is provided. It submits no orders, reads no wallet keys, and uses
no real capital.
