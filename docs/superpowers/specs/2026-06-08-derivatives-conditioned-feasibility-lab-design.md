# Derivatives-Conditioned Feasibility Lab Design

## Objective

Build the next profit-evidence round as a read-only feasibility lab, not as a
strategy-registration round.

The current blocker is evidence quality. The project can ingest public data,
store it locally, run validation, produce governance reports, and preserve
failed assumptions. The latest large-liquid momentum candidate still failed
after the BTC/ETH/SOL 1h candle gap was resolved: all three walk-forward splits
had negative cost-adjusted expectancy. The next round must therefore test
better signal definitions before any new executable family enters the strategy
registry or paper simulator.

This design does not authorize live execution, wallet access, exchange order
routing, private RPC, MEV, premium data, speed-edge infrastructure, or automatic
promotion from research to capital deployment.

## Current Evidence Baseline

Current repository state at design time:

- Branch: `main`
- Remote state: `main...origin/main`
- Latest pushed follow-up: `b299b20 docs: close out feasibility follow-up`
- Existing Goal tool state: the previous project-completion goal is complete,
  so this owner-approved continuation is recorded as a new design/spec path
  instead of opening a second goal object in the same thread.

Current local data in `var/research.sqlite`:

| Source | Record type | Current records | Useful interpretation |
| --- | --- | ---: | --- |
| `ccxt` | `market_candle` | 3000 | 1000 aligned 1h rows each for BTC/USDT, ETH/USDT, and SOL/USDT |
| `ccxt` | `funding_rate` | 231 | mostly BTC/USDT:USDT funding history |
| `ccxt` | `open_interest` | 200 | mostly BTC/USDT:USDT open-interest history |
| `binance_usdm` | `premium_index_kline` | 24 | BTCUSDT only, current context window |
| `binance_usdm` | `basis` | 24 | BTCUSDT perpetual context window |
| `binance_usdm` | `long_short_account_ratio` | 24 | BTCUSDT only, current context window |
| `binance_usdm` | `taker_buy_sell_volume` | 24 | BTCUSDT only, current context window |
| `defillama` | `defi_yield` | 15940 | one snapshot, useful for watchlist context |
| `dexscreener` | `dex_pair` | 30 | one snapshot, useful for DEX discovery context |

The key gap is not the absence of a data path. The gap is that the current
feasibility command has only one mode, `large-liquid-momentum-regime`, and that
mode uses price/volume features while treating the new derivatives feeds only
as context counts.

## External Evidence

Evidence directory:

`var/smart-search-evidence/2026-06-08-next-strategy-redesign/`

Smart Search commands and artifacts:

- `00-deep-plan.json`: deep-research plan for the next strategy-redesign
  decision after stopped funding families and failed large-liquid momentum.
- `01-broad-candidates.json`: broad discovery for low-capital public-data
  candidates.
- `02-binance-docs-discovery.json`: Binance USD-M derivatives market-data
  discovery.
- `03-defillama-docs-discovery.json`: DeFiLlama public API and methodology
  discovery.
- `04-dexscreener-docs-discovery.json`: DexScreener public API discovery.
- `05-fetch-binance-long-short.md`: fetched Binance USD-M global long/short
  account ratio documentation.
- `06-fetch-binance-taker.md`: fetched Binance USD-M taker buy/sell volume
  documentation.
- `07-fetch-defillama-faq.md`: fetched DeFiLlama FAQ and methodology page.
- `08-fetch-dexscreener-reference.md`: fetched DexScreener API reference.

Claim-level findings used:

- Binance USD-M `globalLongShortAccountRatio` is public market data with
  periods including `1h`, max `limit=500`, and latest-30-days history.
- Binance USD-M `takerlongshortRatio` is public market data with periods
  including `1h`, max `limit=500`, and latest-30-days history.
- Binance USD-M premium-index klines and basis are already integrated in this
  repository and are public, proxy-routable sources.
- DeFiLlama states that TVL, stablecoin supply, yields, DEX volume, fees,
  revenue, and bridge data update hourly or daily depending on metric class,
  making it suitable for slow watchlist and regime context.
- DexScreener exposes pair search and pair lookup fields such as liquidity,
  volume, transactions, price change, FDV, market cap, and boosts. Those fields
  are useful for discovery and liquidity filters, but the local repository
  currently has only snapshots, not enough historical depth for a direct
  execution-realistic paper strategy.

## Approaches Considered

### Approach A: Register a New Derivatives Strategy Now

Add a strategy family immediately, using the newly ingested Binance USD-M
derivatives feeds as signal inputs.

Rejected for this round. The project just demonstrated why this is unsafe:
plausible strategy code without a passed feasibility gate becomes another
governance failure. The local derivatives records are also too shallow at 24
BTCUSDT rows.

### Approach B: Build a Read-Only Derivatives Feasibility Lab

Extend `strategy-feasibility` so it can consume enough already-ingested recent
Binance USD-M derivatives context, align those records with market candles, and
compare several signal hypotheses without registering a strategy family.

Recommended. This path reuses the existing feasibility/report pattern, keeps
product behavior fail-closed, and can reject weak candidates before they enter
registry or paper simulation.

### Approach C: Pivot to DeFiLlama or DexScreener Execution Strategies

Use DeFiLlama fundamentals or DexScreener pair metrics to create a new
paper-simulated family.

Rejected for the next executable round. Those sources are valuable, but the
local data is snapshot-style. They are better suited to a future watchlist and
candidate-pool accumulation slice until historical snapshots exist.

## Design Decision

Implement Approach B.

The next round should create a derivatives-conditioned feasibility lab with
these properties:

- read-only CLI/report behavior;
- no strategy registry changes unless a later plan proves a candidate passes;
- no paper simulation changes in this round;
- no live-capital or live-order fields other than explicit false safety fields;
- enough recent Binance USD-M data to test short-horizon signals under the
  documented 30-day and 500-row endpoint limits;
- explicit rejection reasons for every candidate that fails.

## Candidate Hypotheses

The lab should test several hypotheses against aligned market candles and
derivatives records. These names are feasibility candidates, not registered
strategy families:

| Candidate | Signal idea | Expected failure mode to record |
| --- | --- | --- |
| `long_short_crowding_contrarian` | Fade crowded long/short positioning after extreme account-ratio readings | weak sample, no positive cost-adjusted expectancy, unstable splits |
| `taker_imbalance_reversal` | Fade short-horizon taker buy/sell pressure after imbalance extremes | choppy flow, cost drag, no stable win rate |
| `premium_basis_risk_filter` | Use premium index and basis as a risk filter on momentum or reversal entries | filter too sparse, no improvement over baseline |
| `momentum_derivatives_confirmation` | Re-test large-liquid momentum only when derivatives confirmation is favorable | still negative after costs or too few selected observations |

The lab must rank and report all candidates. It must not select a winner unless
the selected candidate has positive cost-adjusted mean return across all
required walk-forward splits.

## Architecture

### CLI

Extend the existing `strategy-feasibility` command instead of adding a new top
level command.

Recommended new mode:

`derivatives-conditioned-lab`

The mode should accept the same safety and storage arguments as the existing
feasibility command:

- `--db`
- `--symbol`
- `--timeframe`
- `--current-capital-usd`
- `--out`
- `--json-out`

Recommended additions:

- `--derivatives-symbol`, defaulting from symbols when possible, e.g.
  `BTC/USDT` maps to `BTCUSDT`.
- `--derivatives-period`, default `1h`.
- `--candidate`, repeatable, defaulting to all lab candidates.
- `--min-split-count`, default `3`.
- `--cost-bps`, default matching the existing 10 bps assumption.

### Data Alignment

The lab should load all needed records through `ResearchDataStore` and normalize
symbol identities at the reporting boundary:

- market candles: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`;
- Binance USD-M symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`;
- Binance basis pairs: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`;
- CCXT derivative symbols when relevant: `BTC/USDT:USDT` style.

Alignment should be timestamp-based and fail closed when the requested
timeframe, period, or symbol cannot be matched.

### Report Model

Add a separate strict Pydantic report model for the lab. Keep the existing
large-liquid momentum report model intact, and share helper functions only where
that keeps behavior clearer. The lab report should include:

- command and mode;
- generated timestamp;
- requested symbols and normalized derivatives symbols;
- candidate metrics;
- candidate rejection reasons;
- per-record-type coverage counts;
- aligned observation count;
- walk-forward split metrics;
- cost model assumptions;
- `uses_real_capital=false`;
- `live_order_routing=false`.

### Report Rendering

Markdown and JSON output should show:

- one decision line for the whole lab: `blocked` or `feasible`;
- one row per candidate;
- split-level net mean and win-rate diagnostics;
- data coverage by symbol and record type;
- stable reasons such as `insufficient_derivatives_history`,
  `insufficient_aligned_history`, `non_positive_cost_adjusted_expectancy`,
  `insufficient_walk_forward_splits`, and `unstable_walk_forward_performance`.

## Data Flow

1. Operator collects recent Binance USD-M derivatives data for BTCUSDT,
   ETHUSDT, and SOLUSDT with `limit=500` where the endpoint supports it.
2. Operator confirms 1h market candles are present for BTC/USDT, ETH/USDT, and
   SOL/USDT.
3. `strategy-feasibility --mode derivatives-conditioned-lab` loads local
   records from SQLite only.
4. The lab maps market symbols to Binance derivatives symbols and aligns
   observations by timestamp.
5. Each candidate produces gross return, cost-adjusted return, win rate,
   selected-symbol counts, and walk-forward split metrics.
6. The report blocks the whole lab unless at least one candidate clears all
   gates.
7. A later strategy-registration design may be written only if the report is
   feasible.

## Error Handling

The lab should prefer explicit blocked reports over exceptions for ordinary
research failures:

- missing records;
- insufficient aligned history;
- duplicate timestamps;
- unavailable candidate inputs;
- non-positive cost-adjusted expectancy;
- too few split observations;
- unstable split performance.

Exceptions remain appropriate for programmer errors, invalid CLI arguments,
malformed stored payloads that violate strict model assumptions, and filesystem
write failures.

## Testing Strategy

Use TDD for implementation.

Focused tests should cover:

- CLI parser accepts the new mode and candidate arguments.
- A fixture with missing derivatives data returns
  `insufficient_derivatives_history`.
- A fixture with enough aligned records but negative returns preserves candidate
  and split diagnostics while returning `blocked`.
- A fixture with one positive candidate and one rejected candidate returns
  `feasible` only for the passing candidate and keeps rejection reasons for the
  failed candidate.
- Symbol mapping handles `BTC/USDT` to `BTCUSDT` and basis `pair` fields.
- Duplicate timestamps fail closed.
- Markdown rendering includes all candidate rows and safety flags.
- JSON serialization is strict and contains no live-capital or live-order
  authorization.

Verification should include:

```bash
uv run --extra dev pytest tests/test_strategy_feasibility.py tests/test_cli_ingest.py tests/test_documentation_contract.py -q
uv run --extra dev ruff check .
git diff --check
```

Before committing any implementation slice, run staged diff checks and the
staged secret scan.

## Acceptance Criteria

The next implementation round is acceptable when:

- the lab can run locally from SQLite without network access;
- the lab tests multiple derivatives-conditioned candidates in one report;
- failed candidates keep diagnostics instead of hiding split metrics;
- no strategy family is registered by the lab implementation;
- no paper outcomes are produced by the lab implementation;
- safety fields remain false for real capital and live routing;
- documentation records whether the best candidate is feasible or blocked;
- all focused tests, full project tests, ruff, diff checks, and staged secret
  checks pass before commit.

## Implementation Handoff

The implementation plan should be written only after this spec is reviewed.

Recommended plan shape:

1. Add RED tests for lab report models, symbol mapping, and candidate metrics.
2. Add minimal read-only lab model and report builder.
3. Add CLI mode wiring and Markdown/JSON rendering.
4. Collect/confirm enough recent derivatives records for BTCUSDT, ETHUSDT, and
   SOLUSDT.
5. Run the lab against local SQLite.
6. If all candidates fail, update docs with rejected candidates and do not
   write strategy-registration code.
7. If exactly one candidate passes, stop and write a new strategy-registration
   design before adding registry or paper-simulation code.
