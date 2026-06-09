# Candidate Quality And Cost-Aware Evidence Expansion Report

Date: 2026-06-09

## Scope

Round 24 optimized the upstream evidence lab after Round 23 expanded data depth
and feasibility v2 but still produced zero `feasibility_passed` candidates.

This phase added deterministic liquid-universe expansion, cost-aware
observation filtering, turnover gates, CLI wiring, and a bounded lab run. It
does not register strategies, open event-driven backtest, open paper
collection, touch live capital, access wallets, or route orders.

## Inputs

- Design:
  `docs/superpowers/specs/2026-06-09-candidate-quality-and-cost-aware-evidence-expansion-design.md`
- Plan:
  `docs/superpowers/plans/2026-06-09-candidate-quality-and-cost-aware-evidence-expansion.md`
- Path map:
  `docs/goals/round-24-candidate-quality-cost-aware-path-map.md`
- Smart Search evidence index:
  `docs/goals/evidence-index/2026-06-09-round-24-next-optimization-evidence-index.md`
- Raw Smart Search evidence:
  `var/smart-search-evidence/2026-06-09-next-optimization-research/`

## Implementation

- Added `liquid-usdm-top20` universe resolution in
  `src/crypto_alpha_agent/pipeline/universe_presets.py`.
- Added cost-aware execution policy fields to feasibility v2:
  `cost_aware_execution`, `min_edge_over_cost_multiplier`, and
  `max_turnover`.
- Added `signal_score`, raw sample count, and cost-aware sample count to
  candidate metrics.
- Added cost-aware filtering per configured cost level, so cost sensitivity is
  recomputed against the active cost threshold.
- Added cost-threshold diagnostics to candidate metrics and per-cost
  sensitivity metrics.
- Added the `excessive_turnover` blocked reason and a timestamp-grouped
  turnover calculation so same-timestamp multi-symbol fanout is not counted as
  strategy churn.
- Added CLI validation so cost-aware policy flags are not silently ignored in
  non-`multi-hypothesis-lab` strategy-feasibility modes.
- Added CLI options for `strategy-feasibility --mode multi-hypothesis-lab`,
  `data-depth-campaign`, and `evidence-universe-lab`.
- Updated the runbook operator command to use the liquid universe preset,
  cost-aware execution, and turnover cap.

## Runtime Command

```bash
uv run crypto-alpha-agent evidence-universe-lab \
  --db var/research.sqlite \
  --memory var/memory/candidate-state.jsonl \
  --universe-preset liquid-usdm-top20 \
  --max-symbols 8 \
  --timeframe 1h \
  --start-year 2026 \
  --start-month 1 \
  --end-year 2026 \
  --end-month 5 \
  --min-unique-months 3 \
  --min-asset-count 3 \
  --min-split-count 3 \
  --purge-gap-bars 24 \
  --cost-bps-grid 5 \
  --cost-bps-grid 10 \
  --cost-bps-grid 20 \
  --cost-bps-grid 50 \
  --cost-aware-execution \
  --min-edge-over-cost-multiplier 2 \
  --max-turnover 0.5 \
  --persist-candidate-state \
  --out-dir var/reports/evidence-universe-lab/round-24-cost-aware-main \
  --json-out var/reports/evidence-universe-lab/round-24-cost-aware-main/evidence-universe-lab.json
```

## Runtime Result

Artifacts:

- `var/reports/evidence-universe-lab/round-24-cost-aware-main/evidence-universe-lab.md`
- `var/reports/evidence-universe-lab/round-24-cost-aware-main/evidence-universe-lab.json`
- `var/reports/evidence-universe-lab/round-24-cost-aware-main/data-depth-campaign.md`
- `var/reports/evidence-universe-lab/round-24-cost-aware-main/data-depth-campaign.json`
- `var/reports/evidence-universe-lab/round-24-cost-aware-main/multi-hypothesis-feasibility.md`
- `var/reports/evidence-universe-lab/round-24-cost-aware-main/multi-hypothesis-feasibility.json`
- `var/memory/candidate-state.jsonl`

Summary from the final `evidence-universe-lab.json` rerun:

- Collection jobs: 0.
- Collection succeeded: 0.
- Collection failed: 0.
- Data-depth readiness: `ready`.
- Candidate-state memory records: 15.
- Candidate count: 11.
- Feasible candidates: 0.
- Blocked candidates: 11.
- Eligible for backtest: `false`.
- Feasibility readiness: `blocked`.
- Feasibility reason codes:
  `insufficient_universe_coverage`,
  `non_positive_cost_adjusted_expectancy`,
  `unstable_walk_forward_performance`,
  `cost_sensitivity_fragile`, and `watchlist_only_source`.
- Safety: `uses_real_capital=false`, `live_order_routing=false`.

## Data Coverage

The Round 24 lab used `liquid-usdm-top20` capped to eight symbols:
BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT, DOGE/USDT, ADA/USDT, and
AVAX/USDT.

The data-depth artifact reports all eight symbols as `ready`, each with five
requested months and five unique months for 2026-01 through 2026-05.

The final rerun reused the already-ready data set and wrote no new collection
jobs. The SQLite `source_records` coverage below is the authoritative evidence
for current data availability.

Current SQLite `source_records` evidence after the run:

| Source | Record type | Records |
| --- | --- | ---: |
| `binance_public` | `market_candle` | 28992 |
| `binance_public` | `source_health` | 40 |
| `binance_usdm` | `basis` | 1500 |
| `binance_usdm` | `long_short_account_ratio` | 1500 |
| `binance_usdm` | `premium_index_kline` | 1500 |
| `binance_usdm` | `source_health` | 24 |
| `binance_usdm` | `taker_buy_sell_volume` | 1500 |
| `ccxt` | `funding_rate` | 231 |
| `ccxt` | `market_candle` | 3000 |
| `ccxt` | `open_interest` | 200 |
| `defillama` | `defi_yield` | 15940 |
| `dexscreener` | `dex_pair` | 30 |

Binance Public Data 1h coverage from `source_records`:

| Symbol | Records | First observed | Last observed |
| --- | ---: | --- | --- |
| ADA/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| AVAX/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| BNB/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| BTC/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| DOGE/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| ETH/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| SOL/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |
| XRP/USDT | 3624 | 2026-01-01T00:00:00+00:00 | 2026-05-31T23:00:00+00:00 |

## Feasibility Result

Validation policy:

- Version: `v2`.
- Purge gap bars: 24.
- Minimum unique months: 3.
- Minimum asset count: 3.
- Cost-aware execution: `true`.
- Minimum edge over cost multiplier: 2.0.
- Maximum turnover: 0.5.

Multiple-testing summary:

- Evaluated candidates: 11.
- Feasible candidates: 0.
- Blocked candidates: 11.
- Blocked reason counts:
  - `insufficient_universe_coverage`: 11.
  - `non_positive_cost_adjusted_expectancy`: 5.
  - `unstable_walk_forward_performance`: 5.
  - `cost_sensitivity_fragile`: 5.
  - `watchlist_only_source`: 2.

Candidate metrics:

| Candidate | Samples | Raw | Cost-aware | Threshold | Assets | Splits | Gross mean | Net mean | Turnover | State target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `short_horizon_momentum_volatility_filter` | 13788 | 15041 | 13788 | 0.00200000 | 8 | 3 | -0.00004509 | -0.00104509 | 0.2062 | `redesign_required` |
| `short_horizon_reversal_volatility_filter` | 15424 | 16695 | 15424 | 0.00200000 | 8 | 3 | -0.00013039 | -0.00113039 | 0.1901 | `redesign_required` |
| `perp_spot_basis_funding_deviation` | 0 | 0 | 0 | 0.00200000 | 8 | 0 | n/a | n/a | 0.0000 | `candidate` |
| `derivatives_crowding_price_action` | 0 | 0 | 0 | 0.00200000 | 8 | 0 | n/a | n/a | 0.0000 | `candidate` |
| `defi_dex_regime_discovery` | 0 | 0 | 0 | 0.00200000 | 0 | 0 | n/a | n/a | 0.0000 | `redesign_required` |
| `cross_asset_ranking_turnover_cap` | 2316 | 2368 | 2316 | 0.00200000 | 8 | 3 | -0.00024742 | -0.00124742 | 0.1322 | `redesign_required` |
| `regime_gated_cross_asset_momentum` | 13519 | 14180 | 13519 | 0.00200000 | 8 | 3 | -0.00023458 | -0.00123458 | 0.1216 | `redesign_required` |
| `regime_gated_cross_asset_reversal` | 16552 | 17199 | 16552 | 0.00200000 | 8 | 3 | 0.00000328 | -0.00099672 | 0.1092 | `redesign_required` |
| `funding_basis_convergence_liquidity_filter` | 0 | 0 | 0 | 0.00200000 | 8 | 0 | n/a | n/a | 0.0000 | `candidate` |
| `derivatives_crowding_recent_window_price_action` | 0 | 0 | 0 | 0.00200000 | 8 | 0 | n/a | n/a | 0.0000 | `candidate` |
| `defi_dex_liquidity_regime_watchlist` | 0 | 0 | 0 | 0.00200000 | 0 | 0 | n/a | n/a | 0.0000 | `redesign_required` |

## Decision

Round 24 did not produce a candidate that can enter event-driven backtest.

The practical gap is now more precise than before:

- Wider market-history coverage exists for eight liquid USD-M symbols, but
  price-action candidates remain negative after cost-aware filtering.
- After fixing turnover to compare timestamp-level selected-symbol sets, no
  candidate exceeded the 0.5 turnover cap in the final rerun. The candidates
  still failed because the economic edge remained negative after costs and
  unstable across purged walk-forward splits.
- The lower-turnover cross-asset ranking candidate also still had negative net
  expectancy and fragile cost sensitivity.
- Derivatives and DeFi/DEX candidates still lack enough point-in-time,
  execution-eligible coverage for this lab.

Backtest, paper, tiny-live review, live execution, wallet access, order
routing, and real capital remain blocked.

## Verification

- Focused Round 24 suite:
  `uv run --extra dev pytest tests/test_universe_presets.py tests/test_multi_hypothesis_feasibility.py tests/test_cli_multi_hypothesis_feasibility.py tests/test_cli_evidence_universe_lab.py tests/test_cli_data_depth_campaign.py tests/test_documentation_contract.py -q`
  passed with 43 tests.
- Round 23/24 related suite:
  `uv run --extra dev pytest tests/test_universe_presets.py tests/test_data_depth_campaign.py tests/test_cli_data_depth_campaign.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_candidate_state_memory.py tests/test_cli_multi_hypothesis_feasibility.py tests/test_cli_evidence_universe_lab.py tests/test_documentation_contract.py -q`
  passed with 89 tests.
- Local non-LLM suite:
  `uv run --extra dev pytest -q -m "not llm_integration"` passed with 1217
  tests and 10 deselected real LLM integration tests.
- Full suite:
  `uv run --extra dev pytest -q` passed with 1227 tests.
- Static and patch checks:
  `uv run --extra dev ruff check .` returned `All checks passed!`;
  `git diff --check` and `git diff --cached --check` returned no whitespace
  errors.
- Staged secret scan:
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  returned `[]`.
