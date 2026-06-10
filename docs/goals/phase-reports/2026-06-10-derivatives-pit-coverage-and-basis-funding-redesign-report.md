# Derivatives PIT Coverage And Basis/Funding Redesign Report

Date: 2026-06-10

## Scope

Round 25 turned the Round 24 blocker analysis into a cleaner point-in-time
derivatives evidence foundation. The phase fixed canonical execution-history
handling, added first-party Binance USD-M funding-rate and open-interest
history ingestion, exposed endpoint metadata in source coverage, and added
read-only derivatives temporal observations for basis/funding and crowding
candidates.

This phase does not register strategies, open event-driven backtest, open paper
collection, touch live capital, access wallets, or route orders.

## Inputs

- Design:
  `docs/superpowers/specs/2026-06-10-derivatives-pit-coverage-and-basis-funding-redesign-design.md`
- Plan:
  `docs/superpowers/plans/2026-06-10-derivatives-pit-coverage-and-basis-funding-redesign.md`
- Path map:
  `docs/goals/round-25-derivatives-pit-coverage-path-map.md`
- Smart Search evidence index:
  `docs/goals/evidence-index/2026-06-10-round-25-derivatives-pit-coverage-evidence-index.md`
- Raw Smart Search evidence:
  `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/`

## Implementation

- Added canonical execution-history selection for overlapping qualified market
  candles. `binance_public` is preferred over `ccxt` for the same
  symbol/timeframe/timestamp, while true duplicate timestamps inside a
  canonical source still remain detectable.
- Added Binance USD-M funding-rate history ingestion from
  `GET /fapi/v1/fundingRate` as `funding_rate` source records with source
  `binance_usdm`.
- Added Binance USD-M open-interest history ingestion from
  `GET /futures/data/openInterestHist` as `open_interest` source records with
  source `binance_usdm`.
- Added `source-probe` catalog target `binance_usdm_funding_rate_history` so
  first-party funding history has the same canary/source-health discovery path
  as open interest, basis, premium-index, long/short, and taker feeds.
- Added CLI choices `funding-rate-history` and `open-interest-history` under
  `ingest --source binance-usdm` with strict argument validation.
- Extended evidence-universe source coverage with endpoint metadata:
  endpoint family, max limit, start/end pagination, and
  `latest_30_day_limited`.
- Added `funding_rate` and `open_interest` to derivatives source coverage and
  source-health feed mapping.
- Qualified first-party `binance_usdm` funding and open-interest records for
  candidate screens without touching the strategy registry.
- Added temporal derivatives observations for basis/funding and crowding
  candidates, using only derivatives records observed at or before the signal
  timestamp and the next market candle return.
- Bounded `evidence-universe-lab` feasibility windows to the requested campaign
  months so later source records do not contaminate the January-May evaluation
  window.
- Made lookahead blocking candidate-specific so future watchlist/regime-only
  records do not block unrelated market or derivatives candidates.
- Hardened real-LLM structured-output prompts and planner draft normalization
  after full-suite verification exposed provider drift: source-research
  judgement prompts now list exact decision enum values, and experiment
  planner drafts ignore safe locally computed fields and coerce string-list
  narrative fields into single strings before validation.

## Runtime Command

```bash
uv run crypto-alpha-agent evidence-universe-lab   --db var/research.sqlite   --memory var/memory/candidate-state.jsonl   --universe-preset liquid-usdm-top20   --max-symbols 8   --timeframe 1h   --start-year 2026   --start-month 1   --end-year 2026   --end-month 5   --min-unique-months 3   --min-asset-count 3   --min-split-count 3   --purge-gap-bars 24   --cost-bps-grid 5   --cost-bps-grid 10   --cost-bps-grid 20   --cost-bps-grid 50   --cost-aware-execution   --min-edge-over-cost-multiplier 2   --max-turnover 0.5   --persist-candidate-state   --out-dir var/reports/evidence-universe-lab/round-25-derivatives-pit-main   --json-out var/reports/evidence-universe-lab/round-25-derivatives-pit-main/evidence-universe-lab.json
```

The closeout run used no live capital and no live order routing:
`uses_real_capital=false`, `live_order_routing=false`.

## Runtime Result

Artifacts:

- `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/evidence-universe-lab.md`
- `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/evidence-universe-lab.json`
- `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/data-depth-campaign.md`
- `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/data-depth-campaign.json`
- `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/multi-hypothesis-feasibility.md`
- `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/multi-hypothesis-feasibility.json`
- `var/memory/candidate-state.jsonl`

Summary from `evidence-universe-lab.json`:

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
- Feasibility version: `v2`.
- Minimum assets: 3.
- Minimum unique months: 3.
- Purge gap bars: 24.
- Report-level reason codes:
  `non_positive_cost_adjusted_expectancy`,
  `unstable_walk_forward_performance`, `cost_sensitivity_fragile`,
  `insufficient_walk_forward_splits`, `insufficient_month_coverage`,
  `single_asset_or_time_window_dependency`, `lookahead_risk`,
  `watchlist_only_source`, and `insufficient_universe_coverage`.

## Data Coverage

The Round 25 lab used `liquid-usdm-top20` capped to eight symbols:
BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT, DOGE/USDT, ADA/USDT, and
AVAX/USDT.

Each requested asset had 3624 canonical Binance Public Data 1h market candles
from `2026-01-01T00:00:00Z` through `2026-05-31T23:00:00Z`, five requested
months, five unique market months, no missing requested months, and no asset
blocked reasons.

Current SQLite `source_records` evidence after the run:

| Source | Record type | Records | First observed | Last observed |
| --- | --- | ---: | --- | --- |
| `binance_public` | `market_candle` | 28992 | `2026-01-01T00:00:00+00:00` | `2026-05-31T23:00:00+00:00` |
| `binance_public` | `source_health` | 40 | `2026-06-09T05:05:37.963986+00:00` | `2026-06-09T06:04:06.761563+00:00` |
| `binance_usdm` | `basis` | 1500 | `2026-05-18T15:00:00+00:00` | `2026-06-08T10:00:00+00:00` |
| `binance_usdm` | `funding_rate` | 600 | `2026-04-04T16:00:00+00:00` | `2026-06-10T00:00:00.001000+00:00` |
| `binance_usdm` | `long_short_account_ratio` | 1500 | `2026-05-18T16:00:00+00:00` | `2026-06-08T11:00:00+00:00` |
| `binance_usdm` | `open_interest` | 1500 | `2026-05-20T10:00:00+00:00` | `2026-06-10T05:00:00+00:00` |
| `binance_usdm` | `premium_index_kline` | 1500 | `2026-05-18T16:00:00+00:00` | `2026-06-08T11:00:00+00:00` |
| `binance_usdm` | `source_health` | 31 | `2026-06-07T12:30:53.240768+00:00` | `2026-06-10T05:13:03.175110+00:00` |
| `binance_usdm` | `taker_buy_sell_volume` | 1500 | `2026-05-18T15:00:00+00:00` | `2026-06-08T10:00:00+00:00` |
| `ccxt` | `funding_rate` | 231 | `2026-03-23T08:00:00.003000+00:00` | `2026-06-08T00:00:00+00:00` |
| `ccxt` | `market_candle` | 3000 | `2026-04-27T12:00:00+00:00` | `2026-06-08T03:00:00+00:00` |
| `ccxt` | `open_interest` | 200 | `2026-05-30T18:00:00+00:00` | `2026-06-08T01:00:00+00:00` |
| `defillama` | `defi_yield` | 15940 | `2026-06-07T14:31:51.503215+00:00` | `2026-06-07T14:31:51.503215+00:00` |
| `dexscreener` | `dex_pair` | 30 | `2026-06-07T14:29:14.261050+00:00` | `2026-06-07T14:29:14.261050+00:00` |

Source coverage now distinguishes endpoint metadata for first-party Binance
USD-M derivatives records:

| Source | Record type | Feed | Records | Endpoint | Max limit | Start/end | Latest 30d only |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| `binance_usdm` | `basis` | `basis` | 963 | `GET /futures/data/basis` | 500 | `true` | `false` |
| `binance_usdm` | `funding_rate` | `funding_rate_history` | 516 | `GET /fapi/v1/fundingRate` | 1000 | `true` | `false` |
| `binance_usdm` | `long_short_account_ratio` | `long_short_account_ratio` | 960 | `GET /futures/data/globalLongShortAccountRatio` | 500 | `true` | `true` |
| `binance_usdm` | `open_interest` | `open_interest_history` | 834 | `GET /futures/data/openInterestHist` | 500 | `true` | `false` |
| `binance_usdm` | `premium_index_kline` | `premium_index_kline` | 960 | `GET /fapi/v1/premiumIndexKlines` | 1500 | `true` | `false` |
| `binance_usdm` | `taker_buy_sell_volume` | `taker_buy_sell_volume` | 963 | `GET /futures/data/takerlongshortRatio` | 500 | `true` | `true` |

The full universe still reports `point_in_time_universe=false` because
DefiLlama watchlist/regime-only records are future single-snapshot records
relative to the January-May campaign window. Round 25 made that lookahead risk
candidate-specific: watchlist candidates remain blocked, but unrelated market
and derivatives candidates are evaluated against their own historical records.

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
  - `cost_sensitivity_fragile`: 9.
  - `insufficient_month_coverage`: 4.
  - `insufficient_universe_coverage`: 2.
  - `insufficient_walk_forward_splits`: 2.
  - `lookahead_risk`: 2.
  - `non_positive_cost_adjusted_expectancy`: 7.
  - `single_asset_or_time_window_dependency`: 2.
  - `unstable_walk_forward_performance`: 7.
  - `watchlist_only_source`: 2.

Candidate metrics from the closeout rerun:

| Candidate | State | Raw | Samples | Assets | Months | Splits | Gross mean | Net mean | Turnover | Reasons |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `short_horizon_momentum_volatility_filter` | `redesign_required` | 13720 | 12731 | 8 | 5 | 3 | -0.00007074 | -0.00107074 | 0.1970 | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `short_horizon_reversal_volatility_filter` | `redesign_required` | 15024 | 14018 | 8 | 5 | 3 | -0.00010253 | -0.00110253 | 0.1860 | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `perp_spot_basis_funding_deviation` | `redesign_required` | 957 | 3 | 8 | 1 | 0 | 0.00396644 | 0.00296644 | 0.0000 | `insufficient_walk_forward_splits`, `insufficient_month_coverage`, `cost_sensitivity_fragile`, `single_asset_or_time_window_dependency` |
| `derivatives_crowding_price_action` | `redesign_required` | 957 | 957 | 8 | 1 | 3 | -0.00009830 | -0.00109830 | 0.0000 | `insufficient_month_coverage`, `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `defi_dex_regime_discovery` | `redesign_required` | 0 | 0 | 0 | 0 | 0 | n/a | n/a | 0.0000 | `lookahead_risk`, `watchlist_only_source`, `insufficient_universe_coverage` |
| `cross_asset_ranking_turnover_cap` | `redesign_required` | 2368 | 2316 | 8 | 5 | 3 | -0.00024638 | -0.00124638 | 0.1317 | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `regime_gated_cross_asset_momentum` | `redesign_required` | 12837 | 12331 | 8 | 5 | 3 | -0.00025744 | -0.00125744 | 0.1150 | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `regime_gated_cross_asset_reversal` | `redesign_required` | 15547 | 15037 | 8 | 5 | 3 | 0.00004148 | -0.00095852 | 0.1080 | `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `funding_basis_convergence_liquidity_filter` | `redesign_required` | 957 | 3 | 8 | 1 | 0 | 0.00396644 | 0.00296644 | 0.0000 | `insufficient_walk_forward_splits`, `insufficient_month_coverage`, `cost_sensitivity_fragile`, `single_asset_or_time_window_dependency` |
| `derivatives_crowding_recent_window_price_action` | `redesign_required` | 957 | 957 | 8 | 1 | 3 | -0.00009830 | -0.00109830 | 0.0000 | `insufficient_month_coverage`, `non_positive_cost_adjusted_expectancy`, `unstable_walk_forward_performance`, `cost_sensitivity_fragile` |
| `defi_dex_liquidity_regime_watchlist` | `redesign_required` | 0 | 0 | 0 | 0 | 0 | n/a | n/a | 0.0000 | `lookahead_risk`, `watchlist_only_source`, `insufficient_universe_coverage` |

## Decision

Round 25 improved the truthfulness of the evidence funnel but did not produce a
candidate that can enter event-driven backtest.

The gap versus the expected system is now clearer:

- Execution-history coverage is cleaner: redundant `binance_public`/`ccxt`
  overlap no longer creates false duplicate timestamp blocks for market
  history.
- First-party Binance USD-M funding and open-interest ingestion exists, source
  health exists, and source coverage now reports exact endpoint metadata.
- Derivatives candidates now produce nonzero temporal observations where local
  derivatives records align with market history.
- The basis/funding candidates still have only one unique month of effective
  derivatives observations in the bounded January-May campaign, so they fail
  month and split gates despite a positive tiny cost-aware sample subset.
- The crowding candidates also have only one unique month and are negative
  after the 10 bps baseline cost assumption.
- Market-only and cross-asset candidates remain negative after cost-aware
  filtering and unstable across purged walk-forward splits.
- Watchlist/regime-only DeFi/DEX candidates remain blocked by future snapshot
  lookahead risk and watchlist-only source role.

Backtest, paper, tiny-live review, live execution, wallet access, order
routing, and real capital remain blocked.

## Next Work

Round 26 should not open event-driven backtest unless a new rerun produces a
real `feasibility_passed` candidate. The next useful route is another upstream
evidence round focused on one of these gaps:

1. Add longer point-in-time derivatives history for funding, premium-index,
   basis, open interest, long/short, and taker through official pagination
   where available and through a separately qualified historical source only if
   the free source path cannot cover the required window.
2. Redesign basis/funding candidates so they have enough observations across at
   least three months and three purged walk-forward splits before cost-aware
   filtering.
3. Replace snapshot-only DeFi/DEX watchlist usage with point-in-time historical
   regime data, or keep those candidates permanently watchlist-only.
4. Keep cost-aware v2 gates strict: no one-split promotion, no pre-cost-only
   profitability, and no paper/backtest handoff while feasible count is zero.

## Verification

- Focused Round 25 plus related LLM/planner suite:
  `uv run --extra dev pytest tests/test_binance_usdm_derivatives_ingestion.py tests/test_cli_ingest.py tests/test_evidence_universe.py tests/test_candidate_screens.py tests/test_multi_hypothesis_feasibility.py tests/test_cli_evidence_universe_lab.py tests/test_source_probe.py tests/test_llm_configured_client.py tests/test_ai_experiment_planner.py -q`
  passed with 176 tests.
- Local non-LLM suite:
  `uv run --extra dev pytest -m "not llm_integration" -q`
  passed with 1247 tests and 10 deselected real LLM integration tests.
- Unrestricted full suite:
  `uv run --extra dev pytest -q`
  passed with 1257 tests.
- Documentation contract suite:
  `uv run --extra dev pytest tests/test_documentation_contract.py -q`
  passed with 12 tests.
- Static checks:
  `uv run --extra dev ruff check .`
  returned `All checks passed!`.
- Workspace whitespace check:
  `git diff --check`
  returned no whitespace errors.
- Staged whitespace check:
  `git diff --cached --check`
  returned no whitespace errors.
- Staged secret scan:
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  returned `[]`.
