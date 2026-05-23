# Phase 10 Execution Realism And Cost Model Completion Report

Date: 2026-05-24

Commit reference: Phase 10 completion commit
`feat: add execution realism cost model`.

## Objective

Complete Phase 10 by making paper simulation and validation outputs
execution-realistic enough that apparent edge cannot survive by ignoring fees,
min-notional and precision constraints, spread/slippage, stale signals,
low-liquidity fills, funding timestamp alignment, or the owner profile limit of
`max_notional_usd <= 25`. The round preserves no wallet keys, no live order
routing, no live execution, no wallet-key access, no order routing, no live
capital, and `live_execution_enabled=false`.

## External Evidence

Smart Search deep research was run before design and planning. Source-backed
findings used:

- Binance USD-M Futures exchange information documents tick, step, lot-size,
  market-lot, and min-notional filters, and warns that precision fields are not
  tick or step sizes:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information>
- Binance Spot filters define price filters, lot-size filters, min-notional
  and notional filters, and market-lot semantics:
  <https://developers.binance.com/docs/binance-spot-api-docs/filters>
- Binance funding documentation describes scheduled perpetual funding windows
  and possible timing deviations:
  <https://www.binance.com/en/support/faq/detail/360033525031>
- CCXT market metadata exposes maker/taker rates, precision, and limits after
  markets are loaded:
  <https://github.com/ccxt/ccxt/wiki/manual>
- NautilusTrader backtesting docs emphasize simulated exchange processing,
  precision validation, and realistic fill modeling:
  <https://nautilustrader.io/docs/latest/concepts/backtesting/>
- CoinAPI backtesting guidance highlights slippage, liquidity, partial fills,
  and timestamp granularity as execution gaps in basic historical tests:
  <https://www.coinapi.io/blog/backtest-crypto-strategies-with-real-market-data>

## Local Feasibility

- Baseline verification in the isolated Phase 10 worktree passed with
  `864 passed, 4 skipped, 2 warnings`.
- `paper_sim_loop._closed_outcomes` was the narrow seam for converting strategy
  paper trades into ledger outcomes.
- `PaperSimulationOutcome` payloads are JSON-ledger compatible, so the richer
  Phase 10 fields did not require a SQLite schema migration.
- Existing funding-price paper trades already carried funding timestamp, entry
  timestamp, exit timestamp, raw return, entry price, and exit price. The
  registry could add entry volume, exit volume, and `next_funding_at`.
- A Decimal rounding prototype showed that a BTC-like large quantity step can
  be infeasible under 25 USDT while a finer spot-like step can still be
  feasible. This proved simple notional capping was not sufficient.

## Implemented

- Added `src/crypto_alpha_agent/execution/cost_model.py` with strict fee
  schedules, symbol constraints, adverse tick/step rounding, pessimistic fee
  floors, fixed slippage bps, stale-signal checks, volume participation, missed
  fills, partial fills, and `pre_cost_only_profitable` rejection.
- Extended `PaperSimulationOutcome` with venue, `cost_model_mode`,
  `fee_model_id`, maker/taker and applied fee rates, entry/exit fees, slippage
  bps, stale-signal status, signal age, fill status, and fill ratio while
  preserving legacy payload defaults.
- Extended paper evidence aggregation with total notional, gross PnL, total
  fees, total slippage, stale-signal counts, missed-fill counts,
  partial-fill counts, and cost model modes.
- Added funding timestamp alignment checks so invalid `next_funding_at`
  intervals block validation with `funding_alignment_invalid`.
- Added paper-trade entry volume, exit volume, and next funding timestamp to
  the strategy registry output.
- Integrated the cost model into `paper-sim-loop`, including blocked outcomes
  for infeasible symbols, stale signals, missed fills, and pre-cost-only edge.
  Validation and no-signal blocked outcomes now also record the run's execution
  metadata.
- Added CLI flags for venue, cost model mode, max notional, max signal age,
  min notional, min quantity, quantity step, tick size, max volume
  participation, and partial-fill policy.
- Updated README, runbook, roadmap, project asset assessment, documentation
  contracts, project state, and this report.

## Review And Fixes

- A pre-implementation code audit recommended the dedicated cost model module,
  paper-loop integration at the outcome materialization seam, richer evidence
  aggregation, funding alignment checks, and two review passes.
- Review pass 1 found a Critical issue where positive-gross but cost-negative
  trades were emitted as closed outcomes, plus Important issues where
  validation/no-signal blockers missed execution metadata and missed fills were
  counted incorrectly. All were fixed with regression tests.
- Review pass 2 found no Critical or Important findings remaining.

## Verification

- Focused implementation verification after review fixes:
  `uv run --extra dev pytest tests/test_funding_mean_reversion_strategy.py tests/test_execution_cost_model.py tests/test_paper_sim_loop.py tests/test_documentation_contract.py -q`
  passed with 48 tests.
- Full verification:
  `uv run --extra dev pytest -q` passed with 881 tests and 4 skipped.
- `uv run --extra dev ruff check .` passed.
- `git diff --check` passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests`
  returned `[]`.

## Safety

- `uses_real_capital=false`
- `live_order_routing=false`
- `live_execution_enabled=false`
- No wallet keys, exchange live order routing, MEV, premium RPC, speed-edge
  execution, wallet-key access, order routing, live execution, live capital, or
  real-capital deployment were added.

## Remaining Gaps

- Phase 11 must upgrade the AI researcher to reason from accumulated evidence,
  rejected assumptions, and validator outputs without bypassing deterministic
  validators.
- Phase 12 must add portfolio and governance scoring before any profit/no-profit
  decision process.
- Phase 7 historical bootstrap and future out-of-sample paper collection should
  only start after Phases 8 through 12 are complete.
- Tiny-live review remains blocked by the current charter and by the absence of
  sufficient future paper observations.

## Next Phase

Phase 11 is the next phase. It was not started during this round.
