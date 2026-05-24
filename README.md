# Crypto Alpha Agent

Autonomous research agent for crypto market analysis, on-chain signals, and
strategy experiments.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
uv run --extra dev pytest
```

The project uses Python 3.12 and a `src` layout package named
`crypto_alpha_agent`.

## Safety Boundary

There is no live execution in this repository. The operator workflow uses
ordinary public APIs, local SQLite, local JSONL memory, Markdown/JSON artifacts,
and a few hundred USD capital profile for research constraints only. Commands
must not read wallet keys, must not require exchange trading keys, and must use
no live order routing.

## Project Direction

The persistent project goal and constraints are documented in
[`docs/project-charter.md`](docs/project-charter.md). The current delivery plan
is tracked in [`docs/roadmap.md`](docs/roadmap.md).

In short: this project optimizes for low-capital crypto alpha research, not
speed arbitrage. The default workflow is real data ingestion, validation,
reflection, reporting, and paper evidence before any live trading discussion.
The registry now has three executable paper-simulated families
(`funding_extremity_price_confirmation`,
`funding_mean_reversion_after_extreme`, and
`funding_open_interest_crowding`) plus three research-only watchlists
(`defi_yield_regime_watchlist`, `dex_liquidity_volume_watchlist`, and
`volatility_compression_expansion_watchlist`). Missing data or unqualified
sources stay blocked with reason codes such as `blocked_by_missing_data` or
`blocked_by_unqualified_source` rather than being promoted to live-capital
paths. The scheduling boundary is operator-controlled:
`evidence-run` is a safe one-shot command that an external cron or systemd timer
may call, while the agent itself does not become an always-on daemon.

## Safe Evidence Run

`evidence-run` is the normal daily operator entry point. It ingests public
research data, validates the configured strategy family, runs the paper
simulation loop, updates memory, and writes daily and optional weekly evidence
reports. It is safe because it records `uses_real_capital=false` and
`live_order_routing=false`.

```bash
uv run --extra dev crypto-alpha-agent evidence-run \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --run-id 2026-05-18-funding-extremity \
  --report-out var/reports/daily/2026-05-18.md \
  --research-report-out var/reports/daily/2026-05-18.research.md \
  --weekly-report-out var/reports/weekly/2026-W21.md \
  --json-out var/reports/daily/2026-05-18.json \
  --manifest-out var/run-manifests/evidence-run/2026-05-18-funding-extremity.json \
  --latest-report-out var/reports/daily/latest.md \
  --latest-json-out var/reports/daily/latest.json \
  --latest-manifest-out var/run-manifests/latest.json \
  --lock-path var/locks/evidence-run.lock \
  --failed-marker-out var/run-manifests/failed/2026-05-18-funding-extremity.json \
  --current-capital-usd 300 \
  --allow-network \
  --ccxt-exchange binance \
  --symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200 \
  --strategy-family funding_extremity_price_confirmation \
  --include-defillama \
  --min-tvl-usd 10000 \
  --include-dexscreener \
  --dex-query "ETH USDC"
```

Use explicit date or run-id naming in artifact paths when a run must be
preserved for recovery or rollout review. The command writes a run manifest,
machine-readable JSON payload, latest pointers, and a failed-run marker on
nonzero exits while keeping live execution disabled.

## Historical Bootstrap And Evidence Campaign

`historical-bootstrap` is the Phase 7 campaign entry point after the data,
validator, cost-model, AI researcher, and governance layers are in place. It
can collect selected historical windows, run registered strategy families over
date-windowed stored records, write a historical bootstrap report, and set
future out-of-sample 30/60/90 evidence targets. It remains paper-only:
`uses_real_capital=false` and `live_order_routing=false`.

```bash
uv run --extra dev crypto-alpha-agent historical-bootstrap \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/phase7/historical-bootstrap.md \
  --json-out var/reports/phase7/historical-bootstrap.json \
  --manifest-out var/run-manifests/historical-bootstrap/2026-05-24.json \
  --run-id 2026-05-24-phase7-bootstrap \
  --price-symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --bootstrap-window 2026-02-01/2026-03-01 \
  --bootstrap-window 2026-03-01/2026-04-01 \
  --bootstrap-window 2026-04-01/2026-05-01 \
  --strategy-family funding_extremity_price_confirmation \
  --strategy-family funding_mean_reversion_after_extreme \
  --strategy-family funding_open_interest_crowding \
  --current-capital-usd 300 \
  --allow-network \
  --ccxt-exchange binance \
  --binance-symbol BTCUSDT \
  --limit 1000 \
  --notional-usd 25
```

Without `--allow-network`, the command still writes an auditable offline
report with blocked source-collection steps and source-health probe entries.
With network enabled, at least one explicit `YYYY-MM-DD/YYYY-MM-DD` bootstrap
window is required. It attempts Binance Public Data candles, CCXT funding and
open-interest history, and public Binance USD-M source probes including
`binance_usdm_open_interest_history`, `binance_usdm_basis`, and
`binance_usdm_global_long_short_account_ratio`. Future out-of-sample evidence
must come from later `evidence-run` observations; historical windows are
reported separately and do not count as forward sample progress or prove profit
by themselves. If a network-enabled source collection step fails, the bootstrap
manifest is marked failed and the CLI exits nonzero.

## Low-Capital Real Data Ingestion

The ingest CLI is safe by default for operators with ordinary infrastructure
and a few hundred USD of capital. The offline check initializes the local
research SQLite store without network calls, live capital, wallet keys, or
order routing:

```bash
uv run --extra dev crypto-alpha-agent ingest --offline-check --db var/research.sqlite
```

Real network sources are research and paper-validation inputs only and require
an explicit `--allow-network` flag. This project excludes MEV/mempool
strategies, sub-second CEX-DEX arbitrage, premium RPC-dependent strategies, and
live order routing.

Safe ingestion examples:

```bash
# Binance Public Data source declaration through ingest.
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source binance-public \
  --allow-network

# Binance Public Data historical candle pull for the research loop.
uv run --extra dev crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --source binance-public \
  --symbol BTCUSDT \
  --timeframe 1h \
  --year 2026 \
  --month 5 \
  --current-capital-usd 300 \
  --allow-network \
  --report-out var/reports/daily/binance-public.md

# CCXT OHLCV and funding history.
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed ohlcv \
  --exchange binance \
  --symbol BTC/USDT \
  --timeframe 1h \
  --limit 200
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed funding-rate-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --limit 200
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed open-interest-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200

# DexScreener discovery snapshots.
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source dexscreener \
  --allow-network \
  --query "ETH USDC"

# DefiLlama yield pool snapshots.
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source defillama \
  --allow-network \
  --min-tvl-usd 10000

# Dune slow research snapshots. Keep DUNE_API_KEY in a local operator config
# or environment outside git; never paste a real key into docs or commits.
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source dune \
  --allow-network \
  --dune-query-id 123456 \
  --dune-api-key "$DUNE_API_KEY" \
  --dune-param chain=ethereum

# TheGraph slow research snapshots.
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source thegraph \
  --allow-network \
  --subgraph-url "$THEGRAPH_SUBGRAPH_URL" \
  --graph-query '{ pools(first: 5) { id totalValueLockedUSD } }'
```

## Source Qualification

Use `source-probe` before relying on a new public-data endpoint in research or
validator work. It records source-health evidence for the tested endpoint
family, network route, HTTP status, parse status, typed record count, schema
version, and blocked reason. The command is read-only and records
`uses_real_capital=false` and `live_order_routing=false`.

```bash
uv run --extra dev crypto-alpha-agent source-probe --list-targets

uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history

uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history \
  --allow-network \
  --route direct
```

When a direct route fails but the operator has a local proxy configured, rerun
with `--route proxy`. Proxy values stay in local shell configuration and are
not printed in the JSON payload. See
[`docs/source-coverage-matrix.md`](docs/source-coverage-matrix.md) and
[`docs/source-query-catalog.md`](docs/source-query-catalog.md) before promoting
any source beyond `ResearchUsable`.

## Phase 1 Research Loop

The Phase 1 closed-loop workflow can pull Binance Public Data candles, store
local research records, generate research-only hypotheses, and optionally write
a Markdown report:

```bash
uv run --extra dev crypto-alpha-agent research-loop \
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

For the open-interest-confirmed funding validator, collect CCXT
open-interest-history before running paper simulation:

```bash
uv run --extra dev crypto-alpha-agent ingest --db var/research.sqlite --source ccxt --allow-network --ccxt-feed open-interest-history --symbol BTC/USDT:USDT --timeframe 1h --limit 100
uv run --extra dev crypto-alpha-agent paper-sim-loop --db var/research.sqlite --strategy-family funding_open_interest_crowding --price-symbol BTC/USDT --funding-symbol BTC/USDT:USDT --timeframe 1h --memory var/memory.jsonl
```

`volatility_compression_expansion_watchlist` is research-only. It can appear in
validation and reports, but the registry returns
`paper_simulation_not_supported` if it is routed to paper simulation.

## Paper Simulation

Run the paper simulator after CCXT OHLCV and funding history have been ingested:

```bash
uv run --extra dev crypto-alpha-agent paper-sim-loop \
  --db var/research.sqlite \
  --strategy-family funding_extremity_price_confirmation \
  --price-symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --current-capital-usd 300 \
  --notional-usd 25 \
  --venue binance \
  --cost-model-mode pessimistic \
  --max-signal-age-seconds 3600 \
  --max-volume-participation-rate 0.05 \
  --memory var/memory/evidence.jsonl \
  --report-out var/reports/paper/funding-extremity.json
```

`paper-sim-loop` now uses the Phase 10 execution-realism gate by default. Each
closed or blocked paper outcome records `cost_model_mode`, venue, maker/taker
fee assumptions, applied entry/exit fees, slippage bps, stale-signal status,
fill status, notional, gross PnL, net PnL, and failure reasons. The default
mode is `pessimistic`: it uses taker-style fee assumptions, fixed conservative
slippage, symbol constraints such as min notional and quantity/tick steps, a
stale-signal check, and low-liquidity missed/partial fill checks. A candidate
that cannot trade inside `max_notional_usd <= 25` is blocked with reasons such
as `min_notional_exceeds_max_notional`; stale signals use `stale_signal`,
pre-cost-only edges erased by fees or slippage use
`pre_cost_only_profitable`, unfilled low-liquidity simulations use
`missed_fill_assumed`, and enabled partial fills are recorded with
`partial_fill` evidence.

## Evidence Reports

Generate daily and weekly Markdown reports from SQLite plus memory:

```bash
uv run --extra dev crypto-alpha-agent evidence-report --daily \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/daily/2026-05-18.md \
  --strategy-family funding_extremity_price_confirmation

uv run --extra dev crypto-alpha-agent evidence-report --weekly \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/weekly/2026-W21.md
```

Generate the profit governance artifact when the owner needs an explicit
profit/no-profit review:

```bash
uv run --extra dev crypto-alpha-agent governance-report \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/monthly/2026-05-governance.md \
  --current-capital-usd 300
```

The report is deterministic and paper-only. It contains the weekly family
scoreboard, profit review, stopped-family ledger, paper-only portfolio
selector, and monthly owner review. It compares the best paper strategy against
doing nothing, fees, slippage, opportunity cost, and the owner's few hundred USD
capital constraint while keeping `uses_real_capital=false` and
`live_order_routing=false`.

## Experiment Planning

Plan the next bounded research experiments without live capital:

```bash
uv run --extra dev crypto-alpha-agent plan-experiments \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --strategy-family funding_extremity_price_confirmation \
  --max-proposals 3 \
  --current-capital-usd 300 \
  --offline-only
```

`plan-experiments` now sends the AI researcher a sanitized evidence context:
recent validation evidence, paper outcome summaries, source health, stopped
families, blocked parameter sets, available data fields, and registered
validators. LLM proposals are accepted only when they cite existing evidence
or a supported data gap, select a registered validator, declare required data
fields, include disconfirmation tests and stop conditions, and stay inside the
current capital profile. The planner rejects duplicate experiments,
unavailable data fields, unsupported sources, direct paper-outcome creation,
live execution, private RPC, MEV, wallet keys, and any live order routing.

Generate the weekly AI research memo from accumulated evidence:

```bash
uv run --extra dev crypto-alpha-agent ai-research-memo \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/weekly/2026-W21-ai-memo.md \
  --current-capital-usd 300
```

The memo is read-only. It explains what changed, what failed, what should stop,
and which bounded experiment is next. It cannot create paper outcomes or route
orders.

## Rollout Review

`rollout-review` builds a tiny-live readiness artifact and preserves the
strategy-specific evidence package used for the review. Fewer than 30 paper
observations blocks tiny-live review, and the output remains review-only with
no live execution.

```bash
uv run --extra dev crypto-alpha-agent rollout-review \
  --db var/research.sqlite \
  --strategy-family funding_extremity_price_confirmation \
  --max-notional-usd 25 \
  --max-daily-loss-usd 10 \
  --artifact-out var/rollout/funding-extremity/tiny-live-readiness.json \
  --evidence-package-out var/rollout/funding-extremity/evidence-package.json
```

## Replay And Recovery

For existing observability event artifacts, use replay to recover counts or
regenerate a daily observability report after an interrupted run. `evidence-run`
writes stdout JSON and Markdown/JSON evidence artifacts; it does not create this
observability JSONL unless an operator wrapper or older observability pipeline
explicitly writes one.

```bash
uv run --extra dev crypto-alpha-agent replay \
  --events var/events/research-observability.jsonl \
  --date 2026-05-18
```

If no observability JSONL exists, recover from the `evidence-run` stdout JSON,
daily Markdown/JSON output, weekly report, memory JSONL, SQLite database, and
rollout artifacts instead. Preserve originals before manual cleanup so the
evidence package preservation trail remains auditable for tiny-live review.
