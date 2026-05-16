# Roadmap

This roadmap is the living plan for turning the current research kernel into a
low-capital crypto alpha research system. It should be updated after each major
implementation phase.

The project charter in `docs/project-charter.md` is the governing constraint for
this roadmap.

The standing owner profile remains profit-first research with only a few hundred
USD, ordinary public APIs/RPC, no speed edge, no MEV or premium infrastructure,
and research plus paper validation before any live capital.

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
- Historical validation foundations:
  - Persisted candle history loader for stored market candles.
  - Conservative close-momentum validator over stored candle bars.
  - Funding-rate extremity validator for stored funding records.
  - Walk-forward train/test window utility.
  - Optional `--include-validation` research-loop summaries in JSON and
    Markdown reports.
- Closed-loop MVP foundations:
  - Charter-constrained prompts, LLM contract models, and guardrails for
    research-only proposals.
  - Fake-LLM-tested research adapter plus an opt-in LangGraph LLM research loop.
  - Memory persistence for generated and blocked hypotheses.
  - Local dry-run scheduler planning with explicit network controls.
  - Paper evidence aggregation and a paper eligibility gate.
  - Tiny-live readiness artifact generation only, with documented tiny-live
    controls in `docs/tiny-live-readiness.md`.

Known limits:

- Historical validation currently covers only simple baseline validators, not a
  broad strategy library or full paper-trading evidence package.
- The LLM loop is opt-in and constrained to research contracts; it is not a
  substitute for historical validation or paper evidence.
- The scheduler is dry-run planning only; there is no deployed daily job,
  dashboard, or alerting.
- Paper evidence infrastructure exists, but sustained paper simulation evidence
  still needs to be collected before any live review.
- There is no live execution path, no wallet-key access, no exchange order
  routing, and the system should not deploy capital.

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

## Phase 2: Real Historical Strategy Validation - Partly Complete

Goal: Validate simple low-capital strategy families against real historical
data before any paper proposal.

Delivered:

- Stored Binance Public Data candles can be loaded as typed chronological bars.
- A conservative close-momentum validator produces trade count, net return, max
  drawdown, and fee/slippage-adjusted expectancy.
- Stored funding-rate records can be summarized for positive and negative
  funding extremes.
- Walk-forward train/test windows are available for future out-of-sample
  validation.
- `research-loop --include-validation` can attach historical validation
  summaries to JSON and Markdown reports.

Initial strategy families:

- Funding-rate extremity plus price momentum filter.
- Funding-rate mean reversion after extreme prints.
- DeFi yield regime change filter with TVL and liquidity constraints.
- DEX pair liquidity/volume anomaly watchlist, used for observation rather than
  direct execution.

Completion standard:

- Each initial strategy family has a deterministic validation adapter.
- Results include fees, slippage assumptions, trade count, max drawdown, and
  expectancy where applicable.
- Walk-forward or out-of-sample splits are applied before paper approval.
- Strategies that fail are persisted with rejection reasons.

Remaining Phase 2 gaps:

- Apply walk-forward checks to validators rather than only exposing window
  generation.
- Add a funding-plus-price combined validator instead of separate summaries.
- Persist validation failures and lessons into memory.
- Add enough strategy-family evidence before any paper-trading gate is
  considered.

## Phase 3: LLM Research Agent Loop - Complete

Goal: Move from static templates to an AI-assisted research loop that proposes
and critiques hypotheses while staying inside the charter.

Delivered:

- Charter-constrained prompt templates for supervisor, scanner, hypothesis
  generator, coder, and reflexion roles.
- Strict LLM research contract models that default to research-only behavior and
  reject live-order, private-key, high-capital, MEV, premium-RPC, bridge-race,
  flash-loan, and speed-edge instructions.
- Fake-LLM research adapter with deterministic tests for valid, invalid, and
  unsafe model output.
- Opt-in LangGraph LLM research loop that guards proposals, requests
  validation, critiques evidence, persists memory, and routes paper suggestions
  to human review rather than execution.

Completion standard:

- Agents can generate candidate research tasks from stored real data.
- Every generated strategy includes explicit assumptions and disconfirming
  evidence.
- Generated code is sandboxed and cannot access wallets, shell, or unrestricted
  network.

## Phase 4: Paper Evidence Accumulation - Partly Complete

Goal: Collect paper-trade evidence only for strategy families that passed
historical validation.

Delivered:

- Aggregation of persisted paper outcomes into strategy evidence packages.
- Paper eligibility gate that requires sufficient clean evidence before a
  candidate can be considered for paper approval.
- Failure tracking for paper evidence normalization and eligibility decisions.

Remaining scope:

- Run repeated paper simulations for narrow, charter-compliant strategy families.
- Produce daily and weekly evidence reports from collected paper outcomes.
- Expand evidence coverage across fees, slippage, liquidity, stale signals, and
  overfit behavior.

Completion standard:

- Each paper candidate has a minimum sample size requirement.
- The system tracks net expectancy, drawdown, hit rate, and failure reasons.
- Candidates that degrade are automatically removed from paper consideration.

## Phase 5: Tiny Live Readiness Review - Artifact Only

Goal: Decide whether a narrow strategy family is ready for tiny live testing.

Delivered:

- Tiny-live readiness artifact generation from rollout gates, paper evidence,
  notional limits, and human approval status.
- Readiness artifacts can record both blocking and passing review outcomes.
- Tiny-live controls are documented in `docs/tiny-live-readiness.md`.

Remaining scope:

- This phase still does not include live execution, wallet access, order routing,
  or capital deployment.
- Live readiness remains blocked until repeated paper evidence passes rollout
  gates for a narrow low-capital strategy family and a human explicitly approves.

Completion standard:

- No live path exists until the strategy-specific evidence package passes.
- Live readiness is a review artifact, not an automatic transition.
- A kill switch and max-loss limit are defined before any live test.

## Active Next Step

The next practical work is Phase 4 paper simulation and evidence collection,
plus data-source expansion that can improve slow-to-medium frequency research.
Do not pivot to speed arbitrage, MEV, premium infrastructure, or high-capital
strategies.

Recommended next slice:

1. Run repeated paper simulations for one or two low-capital strategy families
   that already have conservative historical validation evidence.
2. Persist enough paper outcomes to exercise the paper evidence aggregation and
   eligibility gate with realistic pass and fail cases.
3. Expand ordinary public data coverage where it improves evidence quality:
   additional CCXT venues, funding/open-interest history, DefiLlama
   fundamentals, and DEX liquidity snapshots.
4. Feed failed paper assumptions and rejected candidates back into memory so the
   research loop learns what not to retest.

The constraints remain unchanged: low capital measured in a few hundred USD,
ordinary public APIs/RPC only, no speed edge or speed arbitrage, no MEV or
premium infrastructure dependency, no wallet-key access, no order routing, and
no live capital.

## Roadmap Update Rule

After each completed phase or major implementation branch, update this roadmap
with:

- What changed.
- What evidence exists.
- What remains blocked.
- The next smallest useful implementation slice.
