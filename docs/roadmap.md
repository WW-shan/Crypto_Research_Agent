# Roadmap

This roadmap is the living plan for turning the current research kernel into a
low-capital crypto alpha research system. It should be updated after each major
implementation phase.

The project charter in `docs/project-charter.md` is the governing constraint for
this roadmap.

## Current Baseline

Implemented:

- LangGraph orchestration skeleton with loops, branch routing, checkpoint hooks,
  human checkpoint behavior, and deterministic regression coverage.
- Canonical opportunity and research state models.
- Market scanner, anomaly detector, hypothesis generator, feasibility scoring,
  strategy coder sandbox, reflection, memory, ranking, paper execution, risk
  guardian, rollout gates, observability, CLI smoke commands, and end-to-end
  deterministic tests.
- Real-data ingestion foundations:
  - Binance Public Data historical candle client.
  - CCXT OHLCV and funding-rate collector.
  - DexScreener discovery client.
  - DefiLlama yield-pool client.
  - SQLite research data store.
  - Scanner bridge for candles, funding rates, DEX pairs, DeFi yields, stored
    records, and JSON payloads.
  - Safe `ingest` CLI that defaults to offline initialization and requires
    `--allow-network` for source declarations.
- Stored-data research loop:
  - `research-loop` command that loads stored records, scans signals, runs
    anomaly detection, generates research-only hypotheses, and records loop
    artifacts.
  - Gated Binance Public Data historical candle ingestion through
    `research-loop` with explicit `--allow-network`.
  - Optional Markdown report artifact written with `--report-out`.

Known limits:

- Backtests are still mostly synthetic or toy-path validations rather than
  strategy tests over persisted real market history.
- Agent behavior is mostly deterministic and template-driven, not a live
  multi-agent LLM research process.
- There is no scheduler, daily report job, dashboard, alerting, or deployment
  configuration.
- There is no live trading path, by design.

## Phase 1: Real Data Closed-Loop MVP - Complete

Goal: Run a full local research loop from real data to a daily report without
live trading.

Delivered:

- `research-loop` can explicitly pull Binance Public Data historical candles
  with `--allow-network`.
- Normalized records and loop artifacts are persisted into SQLite.
- Stored records are loaded and converted into scanner signals.
- Anomaly detection and hypothesis generation run over stored data.
- A Markdown daily report can be generated from the run.

Completion evidence:

- One command can run a safe local pipeline for a limited source/symbol set.
- The command writes durable data and a reproducible report.
- No wallet keys, exchange order routing, or live capital are touched.

Example command:

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

## Phase 2: Real Historical Strategy Validation

Goal: Validate simple low-capital strategy families against real historical
data before any paper proposal.

Initial strategy families:

- Funding-rate extremity plus price momentum filter.
- Funding-rate mean reversion after extreme prints.
- DeFi yield regime change filter with TVL and liquidity constraints.
- DEX pair liquidity/volume anomaly watchlist, used for observation rather than
  direct execution.

Completion standard:

- Each strategy family has a deterministic backtest adapter.
- Results include fees, slippage assumptions, trade count, max drawdown, and
  expectancy.
- Walk-forward or out-of-sample splits are included before paper approval.
- Strategies that fail are persisted with rejection reasons.

## Phase 3: LLM Research Agent Loop

Goal: Move from static templates to an AI-assisted research loop that proposes
and critiques hypotheses while staying inside the charter.

Scope:

- Supervisor prompt that must read `docs/project-charter.md`.
- Research agent that proposes hypotheses from anomaly bundles.
- Validator agent that demands falsifiable evidence.
- Coder agent restricted to backtests, transforms, and indicators.
- Reflector agent that writes failure lessons into memory.

Completion standard:

- Agents can generate candidate research tasks from stored real data.
- Every generated strategy includes explicit assumptions and disconfirming
  evidence.
- Generated code is sandboxed and cannot access wallets, shell, or unrestricted
  network.

## Phase 4: Paper Evidence Accumulation

Goal: Collect paper-trade evidence only for strategy families that passed
historical validation.

Scope:

- Paper execution against deterministic fill assumptions.
- Strategy-specific paper logs.
- Daily and weekly evidence reports.
- Failure tracking for slippage, liquidity, stale signal, and overfit behavior.

Completion standard:

- Each paper candidate has a minimum sample size requirement.
- The system tracks net expectancy, drawdown, hit rate, and failure reasons.
- Candidates that degrade are automatically removed from paper consideration.

## Phase 5: Tiny Live Readiness Review

Goal: Decide whether a narrow strategy family is ready for tiny live testing.

Scope:

- Use the rollout gates in `docs/rollout-gates.md`.
- Require human approval.
- Require venue and API permission scoping.
- Start with tiny notional only if all gates pass.

Completion standard:

- No live path exists until the strategy-specific evidence package passes.
- Live readiness is a review artifact, not an automatic transition.
- A kill switch and max-loss limit are defined before any live test.

## Active Next Step

The next implementation should be Phase 2: Real Historical Strategy Validation.

Recommended next slice:

1. Add a persisted candle history loader that reads normalized Binance Public
   Data candles from SQLite for a symbol/timeframe/date range.
2. Add a conservative validator/backtest over stored data, including fees,
   slippage assumptions, trade count, drawdown, and expectancy.
3. Add a funding extremity validator for funding-rate strategy families.
4. Add walk-forward checks so candidate strategies must survive out-of-sample
   periods before any paper-trading proposal.

The constraints remain unchanged: low capital, no speed arbitrage, no MEV or
premium infrastructure dependency, no wallet-key access, no order routing, and
no live capital.

## Roadmap Update Rule

After each completed phase or major implementation branch, update this roadmap
with:

- What changed.
- What evidence exists.
- What remains blocked.
- The next smallest useful implementation slice.
