# Evidence Universe Data Depth And Hypothesis Redesign Report

Date: 2026-06-09

## Scope

Round 23 expanded the Round 22 read-only evidence funnel with:

- a data-depth campaign planner and gated collection command;
- refreshed post-collection coverage reporting;
- read-only data-depth auditing for missing databases;
- evidence universe month and asset depth gates;
- five redesigned candidate screen families;
- feasibility v2 with validation policy, purge/gap split metrics, month/asset
  gates, and multiple-testing summary;
- candidate state memory fields for feasibility v2.

This phase did not add strategy registration, paper queue promotion, live
execution, wallet access, exchange order routing, exchange order submission,
real capital, MEV, premium RPC, private order flow, or any speed-edge path.

## Design And Plan Sources

- Design:
  `docs/superpowers/specs/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign-design.md`
- Implementation plan:
  `docs/superpowers/plans/2026-06-09-evidence-universe-data-depth-and-hypothesis-redesign.md`
- Path map:
  `docs/goals/round-23-evidence-universe-data-depth-path-map.md`
- Smart Search evidence:
  `var/smart-search-evidence/2026-06-08-expand-profit-evidence-loop/`
  and `var/smart-search-evidence/2026-06-09-next-route-gap-research/`

## Data-Depth Campaign

Plan-only artifact:

- Markdown: `var/reports/data-depth-campaign/round-23-plan.md`
- JSON: `var/reports/data-depth-campaign/round-23-plan.json`

Collection artifact:

- Markdown: `var/reports/data-depth-campaign/round-23-collect.md`
- JSON: `var/reports/data-depth-campaign/round-23-collect.json`

The final gated collection used Binance Public Data USD-M futures monthly
klines for five symbols from 2026-01 through 2026-05:

| Symbol | Unique months | Records |
| --- | ---: | ---: |
| BTC/USDT | 5 | 3624 |
| ETH/USDT | 5 | 3624 |
| SOL/USDT | 5 | 3624 |
| BNB/USDT | 5 | 3624 |
| XRP/USDT | 5 | 3624 |

Collection result:

- Missing jobs before collection: 25.
- Collection jobs succeeded: 25.
- Collection jobs failed: 0.
- Final campaign readiness: `ready`.
- SQLite `market_candle` rows: 18120.
- SQLite `source_health` rows: 25.

The campaign command remained explicitly gated: `--collect` requires
`--allow-network`, and both the command payload and collection job records keep
`uses_real_capital=false` and `live_order_routing=false`.

## Feasibility V2 Run

Artifact paths:

- Markdown: `var/reports/strategy-feasibility/multi-hypothesis-lab-v2.md`
- JSON: `var/reports/strategy-feasibility/multi-hypothesis-lab-v2.json`
- Candidate memory: `var/memory/candidate-state.jsonl`

Configuration:

- Mode: `multi-hypothesis-lab`
- Feasibility version: `v2`
- Symbols: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT
- Timeframe: 1h
- Market history window: 2026-01-01 through 2026-05-31
- Cost grid: 5, 10, 20, and 50 bps
- Minimum split count: 3
- Purge gap: 24 bars
- Minimum unique months: 3
- Minimum asset count: 3
- Candidate state memory records written: 15

Overall result:

- Readiness: `blocked`
- Candidates evaluated: 11
- Feasible candidates: 0
- Blocked candidates: 11

Multiple-testing blocked reason counts:

| Reason | Count |
| --- | ---: |
| `non_positive_cost_adjusted_expectancy` | 5 |
| `unstable_walk_forward_performance` | 5 |
| `cost_sensitivity_fragile` | 5 |
| `insufficient_universe_coverage` | 6 |
| `watchlist_only_source` | 2 |

## Candidate Outcomes

| Candidate | Samples | Net mean at 10 bps | State target | Reasons |
| --- | ---: | ---: | --- | --- |
| `short_horizon_momentum_volatility_filter` | 8717 | -0.00100881 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `short_horizon_reversal_volatility_filter` | 9266 | -0.00112702 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `perp_spot_basis_funding_deviation` | 0 | n/a | `candidate` | `insufficient_universe_coverage` |
| `derivatives_crowding_price_action` | 0 | n/a | `candidate` | `insufficient_universe_coverage` |
| `defi_dex_regime_discovery` | 0 | n/a | `redesign_required` | `watchlist_only_source`, `insufficient_universe_coverage` |
| `cross_asset_ranking_turnover_cap` | 2184 | -0.00115115 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `regime_gated_cross_asset_momentum` | 8257 | -0.00117335 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `regime_gated_cross_asset_reversal` | 9491 | -0.00100621 | `redesign_required` | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `funding_basis_convergence_liquidity_filter` | 0 | n/a | `candidate` | `insufficient_universe_coverage` |
| `derivatives_crowding_recent_window_price_action` | 0 | n/a | `candidate` | `insufficient_universe_coverage` |
| `defi_dex_liquidity_regime_watchlist` | 0 | n/a | `redesign_required` | `watchlist_only_source`, `insufficient_universe_coverage` |

The five market-history candidates all had enough asset and month coverage, but
they remained negative after costs and unstable across purged walk-forward
splits. The derivatives and DeFi/DEX candidates did not have the required
source universe coverage in this run.

## Fixes During The Phase

Two implementation issues were found during Task 8 and fixed before closeout:

- Plan-only data-depth audits no longer create a missing SQLite database.
- Data-depth collection artifacts now refresh coverage after collection, so the
  final collect report shows post-collection coverage instead of stale
  pre-collection coverage.
- Redesigned market screens are included in multi-hypothesis historical
  observations, so they are evaluated rather than incorrectly blocked by
  `insufficient_samples`.

## Verification

Focused Round 23 verification:

- `uv run --extra dev pytest tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_candidate_state_memory.py tests/test_documentation_contract.py -q`
- Result: 68 tests passed.

Local non-LLM suite:

- `uv run --extra dev pytest -q -m "not llm_integration"`
- Result: 1202 tests passed and 10 real LLM integration tests were deselected.

Full unrestricted pytest:

- `uv run --extra dev pytest -q`
- Result: 1202 tests passed and 10 tests failed before execution because the
  local environment did not provide `OPENAI_BASE_URL`, `OPENAI_API_KEY`, or an
  OpenAI model setting. The failing tests are marked `llm_integration` and
  require a configured real LLM provider.

Static and patch checks:

- `uv run --extra dev ruff check .`
- `git diff --check`
- Result: ruff returned `All checks passed!`; `git diff --check` returned no
  whitespace errors.

## Backtest And Paper Decision

No candidate reached `feasibility_passed`.

Round 24 Event-Driven Backtest Expansion is not eligible from this run. No
candidate may move to `backtest_passed`, `paper_collecting`, paper simulation,
tiny-live review, or live readiness.

The next practical work remains evidence redesign: add missing derivatives and
DeFi/DEX point-in-time coverage, improve hypothesis definitions, and rerun
feasibility v2. It should not register strategies or start paper until a
candidate passes feasibility.

## Safety Confirmation

- `uses_real_capital=false`
- `live_order_routing=false`
- no wallet keys
- no wallet-key access
- no exchange order routing
- no exchange order submission
- no live order path
- no live capital
- no strategy registry promotion
- no paper queue promotion
