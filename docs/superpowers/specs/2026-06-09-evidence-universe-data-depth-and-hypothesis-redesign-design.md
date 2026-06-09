# Evidence Universe Data Depth And Hypothesis Redesign Design

Date: 2026-06-09

## Purpose

Round 23 turns the Round 22 read-only evidence funnel into a deeper and more
durable upstream research lab. The goal is not to register strategies, open a
paper queue, or build live execution. The goal is to increase the amount and
quality of public-data evidence before any candidate can reach the later
event-driven backtest phase.

The triggering gap is clear: Round 22 proved the pipeline shape, but the local
bounded run only covered BTC/USDT, ETH/USDT, and SOL/USDT Binance Public Data
USD-M futures 1h candles for May 2026. No candidate reached
`feasibility_passed`. Round 23 must therefore expand data depth and redesign
hypotheses before the same gates are tried again.

## Current Baseline

Round 22 delivered:

- Binance Public Data USD-M monthly kline ingestion.
- DefiLlama and DexScreener source qualification routes.
- Point-in-time evidence universe diagnostics.
- Read-only candidate screen catalog.
- Multi-hypothesis feasibility reporting.
- Candidate state memory.
- A persistent path map that blocks backtest, paper, and live work unless
  upstream gates pass.

Round 22 did not deliver:

- Long-history evidence across 12-24 months.
- A wider liquid universe beyond BTC/ETH/SOL in the local run.
- Enough derivatives history for basis, funding, crowding, and taker-flow
  hypotheses.
- Purged or embargoed time-series validation.
- Multiple-testing or overfit-risk accounting across many candidate variants.
- Any event-driven backtest eligibility.

## Design Decision

Round 23 remains a read-only research phase. It adds a data-depth campaign
layer, strengthens universe coverage checks, expands candidate hypotheses, and
upgrades feasibility gates. It does not create strategy registry entries, paper
trades, order routing, wallet access, or live-capital paths.

The recommended path is:

1. Build and persist a reproducible data-depth campaign plan.
2. Collect or audit longer Binance Public Data history for a wider liquid
   universe where network access succeeds.
3. Keep DefiLlama, DexScreener, and optional secondary sources as source-
   qualified discovery or regime inputs until point-in-time snapshots exist.
4. Upgrade universe coverage so each candidate sees explicit asset, month,
   source, route, staleness, duplicate, alignment, and lookahead-risk status.
5. Redesign candidate screens into hypothesis families rather than a small
   fixed set.
6. Upgrade feasibility into a v2 lab with purge/gap validation, stricter pass
   gates, cost sensitivity, asset/month coverage, and failure memory.
7. Produce a phase report that decides whether any candidate is eligible for
   Round 24 event-driven backtest expansion.

## Architecture

### Data-Depth Campaign Layer

Add a focused planning and reporting module that can describe a campaign before
it performs network collection. The campaign should enumerate symbols, months,
timeframes, markets, source routes, expected record types, and local coverage.

The layer should support two modes:

- `plan`: inspect current local coverage and write a campaign plan without
  network access.
- `collect`: explicitly gated by `--allow-network`; run bounded public-data
  collection jobs and record job-level success or failure.

The first implementation should focus on Binance Public Data USD-M futures
monthly klines because Round 22 already qualified that path. Trades and
aggregate trades can remain planned targets until parser and storage contracts
are added in a later task.

### Universe Coverage Upgrade

The evidence universe report should become more useful for long-history
validation. In addition to existing coverage and quality issues, it should
report unique month count, requested month coverage, source route status,
minimum-history thresholds, and point-in-time eligibility by symbol.

The universe builder must keep failing closed when today's discovery list would
be backfilled into historical windows.

### Candidate Hypothesis Redesign

The candidate catalog should expand from six fixed screens into families that
can be evaluated consistently:

- Regime-gated cross-asset momentum.
- Regime-gated cross-asset reversal.
- Funding or basis convergence with liquidity and volatility filters.
- Recent-window OI/funding/taker crowding plus price action.
- DeFi/DEX liquidity or revenue regime watchlist.
- Turnover-capped ranking variants.

These remain candidate screens only. They must not write strategy registry
records or paper outcomes.

### Feasibility V2

Feasibility v2 should add:

- Purge/gap between train and test windows.
- Optional embargo after test windows when supported by the local data shape.
- Minimum unique months and minimum asset count.
- Cost sensitivity at 5/10/20/50 bps.
- Split-level net expectancy.
- Single-symbol and single-month dependency blocking.
- Multiple-testing summary across the candidate set.
- Candidate-state memory for passed, blocked, stopped, and redesign-required
  results.

Passing feasibility should remain hard. A candidate may reach
`feasibility_passed` only when net expectancy is positive after costs, multiple
chronological splits are stable, cost sensitivity is not fragile, and the
result is not a one-symbol or one-month accident.

## Data Flow

1. Operator runs a plan-only data-depth campaign.
2. Campaign report reads local SQLite records and source-health rows.
3. If approved by explicit CLI flags, campaign collection fetches bounded
   Binance Public Data monthly history and writes typed records.
4. Universe builder reads the updated store and emits coverage and quality
   diagnostics.
5. Candidate screens read only local records and emit read-only signals.
6. Feasibility v2 scores candidates with cost, split, purge/gap, and
   dependency checks.
7. Candidate state memory records the final state and reason codes.
8. Phase report records actual vs expected, pass/block outcomes, and the next
   allowed phase.

## Success Criteria

Round 23 is complete when:

- The design, path map, implementation plan, and project state are persisted.
- A data-depth campaign command can write Markdown and JSON artifacts.
- The campaign can plan coverage without network access.
- Bounded collection is explicitly gated and records per-job results.
- Universe diagnostics include long-history coverage and point-in-time
  eligibility.
- Candidate screens include redesigned families and remain read-only.
- Feasibility v2 reports purge/gap policy, month/asset coverage, cost
  sensitivity, split stability, multiple-testing summary, and candidate states.
- A local Round 23 lab run writes artifacts and a phase report.
- No live execution, wallet access, order routing, paper promotion, or strategy
  registration is introduced.

## Non-Goals

- No live execution.
- No wallet keys or wallet-key access.
- No exchange order routing or order submission.
- No real capital.
- No MEV, bridge races, flash loans, premium RPC, private order flow,
  colocation, or speed-edge strategy.
- No paper queue without `feasibility_passed` and later `backtest_passed`.
- No event-driven backtest until a candidate passes feasibility.
- No use of current DexScreener trending or token lists as historical evidence.

## Research Evidence

The Round 23 route is backed by two persisted research directories:

- `var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`
- `var/smart-search-evidence/2026-06-09-next-route-gap-research/`

Key source references:

- Binance Public Data: <https://github.com/binance/binance-public-data>
- DefiLlama docs: <https://docs.llama.fi/>
- DexScreener API: <https://docs.dexscreener.com/api/reference>
- scikit-learn `TimeSeriesSplit`: <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
- Freqtrade lookahead analysis: <https://www.freqtrade.io/en/stable/lookahead-analysis/>
- QuantConnect slippage: <https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts>
- QuantConnect fills: <https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts>
- Binance filters: <https://developers.binance.com/docs/binance-spot-api-docs/filters>
- HFTBacktest fills: <https://hftbacktest.readthedocs.io/en/latest/order_fill.html>

## Review Notes

This spec intentionally keeps Round 23 upstream of trading. If Round 23 still
produces no `feasibility_passed` candidate, that is a valid result: it means
the system rejected more weak hypotheses with better evidence.
