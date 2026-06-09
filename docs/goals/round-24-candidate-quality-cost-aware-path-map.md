# Round 24 Candidate Quality Cost-Aware Path Map

Date: 2026-06-09

## Objective

Improve the upstream evidence lab's ability to find real feasible candidates by
reducing low-edge overtrading and expanding the campaign universe, while
preserving the project charter's paper/live blockers.

## Route

1. Persist the design and implementation plan.
2. Add deterministic liquid universe presets for bounded wider campaigns.
3. Add signal-score-aware observation filtering to feasibility v2.
4. Add computed cost-threshold diagnostics to feasibility JSON and Markdown.
5. Add timestamp-grouped turnover measurement plus a turnover gate that blocks
   overactive candidates explicitly.
6. Thread the new controls through `strategy-feasibility`,
   `data-depth-campaign`, and `evidence-universe-lab`.
7. Run a bounded Round 24 lab with the new controls.
8. Persist actual results, verification, and remaining blockers.

## Gates

- `feasibility_passed` requires positive cost-adjusted expectancy, stable
  purged walk-forward splits, sufficient month/asset coverage, non-fragile
  cost sensitivity, and no excessive turnover.
- Event-driven backtest remains blocked unless at least one candidate reaches
  `feasibility_passed`.
- Paper remains blocked unless a later event-driven backtest passes.
- Live remains blocked regardless of this round.

## Non-Goals

- No strategy registry mutation.
- No paper queue opening.
- No live order routing.
- No wallet access.
- No real capital.
- No speed-edge, MEV, private order flow, premium RPC, bridge race, or flash
  loan assumptions.

## Evidence

The supporting search evidence is stored locally at:

`var/smart-search-evidence/2026-06-09-next-optimization-research/`

The repository evidence index is:

`docs/goals/evidence-index/2026-06-09-round-24-next-optimization-evidence-index.md`

## Final Result

- Final lab artifacts:
  `var/reports/evidence-universe-lab/round-24-cost-aware-main/`.
- Data-depth readiness: `ready`.
- Feasibility readiness: `blocked`.
- Candidates evaluated: 11.
- Feasible candidates: 0.
- Blocked candidates: 11.
- Backtest eligibility: `false`.
- Final report-level blocker reasons:
  `insufficient_universe_coverage`,
  `non_positive_cost_adjusted_expectancy`,
  `unstable_walk_forward_performance`,
  `cost_sensitivity_fragile`, and `watchlist_only_source`.

The turnover gate remains available, but the final rerun did not include
`excessive_turnover` in report-level reasons after same-timestamp multi-symbol
fanout was excluded from turnover churn.
