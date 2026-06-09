# Candidate Quality And Cost-Aware Evidence Expansion Design

Date: 2026-06-09

## Purpose

Round 24 optimizes the evidence universe lab after Round 23 completed the
read-only data-depth and multi-hypothesis feasibility automation but produced
zero `feasibility_passed` candidates.

The failure pattern is specific: market-history candidates produced samples but
their gross edge was too small, turnover was high, and cost-adjusted expectancy
turned negative. Derivatives, DeFi, and DEX candidates remained blocked by
insufficient point-in-time coverage or watchlist-only source status.

Round 24 therefore focuses on candidate quality before any event-driven
backtest. It adds cost-aware execution filters, turnover gates, a reusable
liquid-universe preset for wider data campaigns, and richer economic
diagnostics. It does not register strategies, open paper collection, touch live
capital, or add order routing.

## Current Baseline

Round 23 delivered:

- `evidence-universe-lab`, which runs data-depth collection plus feasibility v2.
- Binance Public Data USD-M futures monthly kline collection.
- Source-qualified DefiLlama and DexScreener discovery routes.
- Read-only candidate screens.
- Multi-hypothesis feasibility with cost sensitivity and purged splits.
- Candidate-state memory.

Round 23 actual result:

- 25 of 25 bounded monthly kline jobs succeeded in the main workspace run.
- 11 candidates were evaluated.
- 0 candidates were feasible.
- Market-history candidates were negative after costs and unstable across
  splits.
- Derivatives and DeFi/DEX candidates were blocked by coverage or watchlist
  status.

## Design Decision

Round 24 keeps the same upstream read-only boundary but changes how candidates
are converted into observations:

1. Add a liquid USD-M universe preset so operators can expand beyond BTC, ETH,
   SOL, BNB, and XRP without hand-maintaining every campaign symbol.
2. Add cost-aware execution filtering so observations are retained only when
   the signal magnitude is large enough to justify the configured cost
   threshold.
3. Add an optional turnover cap so high-frequency weak signals fail explicitly
   as `excessive_turnover` rather than only through negative expectancy.
4. Add diagnostics that report raw sample count, cost-aware sample count, cost
   threshold, filter multiplier, turnover cap, and per-cost filtered metrics.
5. Preserve feasibility gates: positive net expectancy, stable walk-forward
   splits, sufficient asset/month coverage, and non-fragile cost sensitivity.

## Architecture

### Liquid Universe Preset

Add a small module for read-only universe presets. The first preset is
`liquid-usdm-top20`, a conservative set of large, liquid Binance USD-M symbols.
It is used only to expand CLI symbol lists for data campaigns and lab runs.

The preset must:

- Return slash-form symbols.
- Dedupe explicit and preset symbols by exchange symbol.
- Support `--max-symbols` so operators can bound network collection.
- Avoid live exchange metadata calls by default.

### Cost-Aware Observation Filter

Extend multi-hypothesis observations with `signal_score`. For price-action
candidates this is the absolute lookback return used to trigger the signal. For
cross-asset ranking it is the selected symbol's rank score.

When cost-aware execution is enabled, retain an observation only if:

`signal_score >= cost_bps / 10000 * min_edge_over_cost_multiplier`

Cost sensitivity should apply the filter separately for each cost level. The
baseline candidate metric should use the baseline cost in the configured grid.

### Turnover Gate

Add an optional `max_turnover` validation policy field. When set, candidates
whose filtered observation turnover exceeds the cap are blocked with
`excessive_turnover`.

Turnover is measured over timestamp-level selected-symbol sets. Multiple
symbols selected at the same timestamp are treated as parallel fanout, not as
sequential symbol churn.

This does not attempt to simulate fills. It is a feasibility-stage gate that
blocks obviously overactive candidates before event-driven backtest design.

### CLI Surface

Add shared flags to `strategy-feasibility --mode multi-hypothesis-lab` and
`evidence-universe-lab`:

- `--cost-aware-execution`
- `--min-edge-over-cost-multiplier`
- `--max-turnover`
- `--universe-preset liquid-usdm-top20`
- `--max-symbols`

`data-depth-campaign` also accepts `--universe-preset` and `--max-symbols`.

All commands remain read-only unless existing `--collect --allow-network` is
provided for data-depth collection.

## Data Flow

1. Operator chooses explicit symbols, a universe preset, or both.
2. CLI resolves and dedupes symbols before building the data-depth campaign.
3. Data-depth campaign plans or collects market candles with existing safety
   gates.
4. Feasibility v2 builds observations with signal scores.
5. Optional cost-aware filtering removes low-edge observations.
6. Optional turnover cap blocks overactive candidates.
7. Reports record raw and filtered sample counts plus filter settings.
8. Candidate-state memory records pass/block/redesign outcomes.

## Success Criteria

Round 24 is complete when:

- Design, plan, path map, project state, roadmap, and phase report are
  persisted.
- A liquid universe preset can expand CLI symbols deterministically.
- Cost-aware execution filtering is tested and visible in feasibility reports.
- Turnover caps are tested and visible in feasibility reports.
- `strategy-feasibility` and `evidence-universe-lab` expose the new options.
- A bounded Round 24 lab run writes artifacts.
- Backtest, paper, live, wallet, order routing, and real-capital paths remain
  blocked unless a candidate actually reaches `feasibility_passed`.

## Non-Goals

- No strategy registry changes.
- No event-driven backtest unless feasibility produces a real passed candidate.
- No paper queue opening.
- No live execution.
- No wallet access.
- No exchange order routing or order submission.
- No real capital.
- No MEV, bridge races, flash loans, premium RPC, private order flow,
  colocation, or speed-edge assumptions.
- No use of DexScreener latest/trending data as historical execution evidence.

## Research Evidence

The Round 24 route is backed by:

- `var/smart-search-evidence/2026-06-09-next-optimization-research/`

Key references:

- Binance Public Data: <https://github.com/binance/binance-public-data>
- Binance long/short 30-day limit:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio>
- Binance taker buy/sell 30-day limit:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Taker-BuySell-Volume>
- Binance funding history:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History>
- Binance basis:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Basis>
- DefiLlama docs: <https://docs.llama.fi/>
- DexScreener API: <https://docs.dexscreener.com/api/reference>
- scikit-learn `TimeSeriesSplit`:
  <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
- Freqtrade lookahead analysis:
  <https://www.freqtrade.io/en/stable/lookahead-analysis/>
- QuantStart transaction costs:
  <https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/>
- Perpetual futures research:
  <https://arxiv.org/html/2212.06888v5>
- BTC walk-forward under transaction costs:
  <https://arxiv.org/html/2606.00060v1>

## Review Notes

Round 24 may still produce zero feasible candidates. That remains a valid
outcome if the stricter candidate-quality gates reject weak evidence honestly.
