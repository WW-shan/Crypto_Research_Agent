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
The first strategy family has an implemented funding-plus-price validator and a
hard walk-forward gate. Before the complete autonomous evidence system plan, the
scheduler remains dry-run only; active work is now the complete autonomous
evidence system.

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

## Safe Research And Paper Memory Workflow

Use this current workflow to collect OHLCV price candles and funding-rate
history, run the paper loop so it writes ledger and memory, then generate a
research report with validation and paper evidence:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source ccxt --allow-network --ccxt-feed ohlcv --symbol BTC/USDT --timeframe 1h --limit 100
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source ccxt --allow-network --ccxt-feed funding-rate-history --symbol BTC/USDT:USDT --limit 100
uv run --extra dev crypto-alpha-agent paper-sim-loop --db var/research.sqlite --strategy-family funding_extremity_price_confirmation --price-symbol BTC/USDT --funding-symbol BTC/USDT:USDT --timeframe 1h --memory var/memory.jsonl
uv run --extra dev crypto-alpha-agent research-loop --db var/research.sqlite --include-validation --include-paper-evidence --report-out var/reports/daily.md
```

The paper simulation loop needs both OHLCV price bars and funding history. These
commands collect public research data, produce local reports, and persist paper
evidence memory records; they do not touch wallets, live order routing, or real
capital.
