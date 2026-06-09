# Round 23 Evidence Universe Data Depth Path Map

Date: 2026-06-09

## Objective

Round 23 expands the upstream evidence funnel from "one bounded
multi-hypothesis lab run" to "data-depth campaign plus hypothesis redesign."
It remains research-only and read-only with respect to trading decisions.

## Current Actual State

- Round 22 is complete on branch `round-22-evidence-universe-lab`.
- Round 23 is based on Round 22, not on the older `main` branch.
- Round 23 completed a bounded data-depth campaign covering BTC/USDT, ETH/USDT,
  SOL/USDT, BNB/USDT, and XRP/USDT USD-M futures 1h candles from 2026-01
  through 2026-05.
- Eleven candidate screens were evaluated under feasibility v2.
- Zero candidates reached `feasibility_passed`.
- Event-driven backtest, paper collection, tiny-live review, and live
  readiness remain blocked.

## Expected Round 23 State

Round 23 delivered:

1. A reproducible data-depth campaign plan and report.
2. Longer public market-history coverage where source access succeeds.
3. Wider liquid-universe coverage diagnostics.
4. Source-qualified discovery/regime inputs that are not backfilled into
   history.
5. Redesigned read-only candidate hypothesis families.
6. Feasibility v2 with purge/gap validation, stricter pass gates, and
   multiple-testing awareness.
7. Candidate memory that records pass/block/redesign decisions.
8. A phase report deciding that Round 24 event-driven backtest expansion is not
   eligible because no candidate reached `feasibility_passed`.

## Route

### 1. State Baseline

- Work from `round-23-data-depth-hypothesis-redesign`, based on Round 22.
- Keep `main` untouched until the owner decides how to integrate completed
  branches.
- Preserve Round 22 artifacts and evidence paths.

### 2. Data-Depth Campaign

- Add a plan-only campaign artifact that lists symbols, months, timeframe,
  market namespace, local coverage, and missing jobs.
- Add an explicitly gated collection path for Binance Public Data monthly
  klines.
- Keep trades and aggregate trades as planned targets unless parser and storage
  support are added in this round.
- Record job-level failures instead of treating partial source failure as
  success.

### 3. Source Qualification

- Treat Binance Public Data as the primary long-history market-data route.
- Treat Binance USD-M long/short and taker feeds as recent derivatives context.
- Treat DefiLlama as regime/discovery input until historical point-in-time
  coverage is sufficient.
- Treat DexScreener as point-in-time discovery/watchlist only.
- Treat CoinMetrics or other secondary sources as optional source-qualification
  candidates, not assumed dependencies.

### 4. Universe Gate

- Add unique month coverage.
- Add requested month coverage.
- Add source route and source freshness summary.
- Add point-in-time eligibility status by symbol.
- Block candidates that depend on current watchlists or insufficient history.

### 5. Hypothesis Redesign

- Expand candidate screens into families:
  - regime-gated cross-asset momentum;
  - regime-gated cross-asset reversal;
  - funding/basis convergence with liquidity and volatility filters;
  - recent-window derivatives crowding plus price action;
  - DeFi/DEX regime watchlist;
  - turnover-capped ranking variants.
- Keep screens separate from the strategy registry.

### 6. Feasibility V2

- Add purge/gap between train and test windows.
- Add minimum unique-month and minimum asset gates.
- Keep cost sensitivity at 5/10/20/50 bps.
- Add multiple-testing summary across all evaluated candidates.
- Persist candidate state and reason codes.
- Pass only when the evidence survives cost, split, asset, month, and
  dependency gates.

### 7. Backtest Gate

- No candidate reached `feasibility_passed`.
- Round 24 is not opened.
- A future Round 24 may design event-driven backtesting only after a later
  feasibility v2 run produces a state-qualified candidate.

### 8. Paper Gate

- Paper remains blocked until a later candidate reaches `backtest_passed`.
- Paper must compare backtest expected vs paper actual over 30/60/90
  observations.

### 9. Live Gate

- Live execution remains blocked.
- This path map does not authorize wallet access, order routing, order
  submission, exchange keys, or real capital.

## Round 23 Deliverables

- `docs/superpowers/specs/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign-design.md`
- `docs/superpowers/plans/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign.md`
- `docs/goals/round-23-evidence-universe-data-depth-path-map.md`
- Updated `docs/goals/project-completion-state.md`
- Updated `docs/roadmap.md`
- Data-depth campaign JSON and Markdown artifacts.
- Feasibility v2 JSON and Markdown artifacts.
- Candidate-state memory updates.
- Round 23 phase report.

## Forbidden Transitions

- Do not register current Round 22 candidates as strategies.
- Do not open paper from a single positive split.
- Do not use current discovery lists as historical universe membership.
- Do not weaken cost assumptions to force a pass.
- Do not add live execution, wallet access, order routing, MEV, speed
  arbitrage, premium infrastructure, or high-capital assumptions.
