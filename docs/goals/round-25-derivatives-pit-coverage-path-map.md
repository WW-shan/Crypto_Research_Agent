# Round 25 Derivatives PIT Coverage Path Map

Date: 2026-06-10

## Objective

Convert the Round 24 blocker analysis into a cleaner point-in-time evidence
foundation for derivatives hypotheses. The round fixes canonical execution
history first, expands first-party Binance USD-M derivatives ingestion, and
then adds read-only derivatives feasibility observations.

## Route

1. Persist the Round 25 design, plan, evidence index, and path map.
2. Canonicalize overlapping execution-history candles by source priority so
   redundant qualified feeds do not create false duplicate timestamp blocks.
3. Add endpoint-level derivatives metadata for latest-30-days-only feeds,
   pageable feeds, request limits, and execution/context roles.
4. Add first-party Binance USD-M funding-rate history and open-interest
   history ingestion.
5. Extend source coverage to include `funding_rate` and `open_interest` with
   exact source-health feed mapping.
6. Add temporal derivatives observation builders for basis/funding and
   crowding candidates.
7. Run a bounded Round 25 lab and persist actual candidate results.
8. Keep event-driven backtest, paper, wallet access, order routing, live
   execution, and real capital blocked unless a real `feasibility_passed`
   candidate exists.

## Gates

- `feasibility_passed` still requires positive cost-adjusted expectancy,
  stable purged walk-forward splits, sufficient month/asset coverage,
  non-fragile cost sensitivity, acceptable turnover, and no lookahead or
  point-in-time source violation.
- Long/short and taker feeds are recent-window context unless a separately
  qualified historical source is added in a future round.
- Funding, basis, premium-index, and open-interest statistics may be used for
  historical observations only when actual coverage exists in the evaluation
  window.
- Backtest remains closed when feasible candidate count is zero.

## Non-Goals

- No strategy registry mutation.
- No paper queue opening.
- No live order routing.
- No wallet access.
- No real capital.
- No MEV, bridge races, flash loans, private order flow, premium RPC, or
  speed-edge assumptions.
- No default paid third-party historical derivatives dependency.

## Evidence

Raw Smart Search evidence remains local at:

`var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/`

Repository evidence index:

`docs/goals/evidence-index/2026-06-10-round-25-derivatives-pit-coverage-evidence-index.md`

## Expected Result

Round 25 may still produce zero feasible candidates. That is acceptable if the
system can explain the result with cleaner source coverage, canonical execution
history, and nonzero derivatives observation counts where data exists. The
required outcome is a more truthful evidence funnel, not a forced pass.
