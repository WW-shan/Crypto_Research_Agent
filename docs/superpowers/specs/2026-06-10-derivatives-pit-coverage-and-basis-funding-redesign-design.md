# Derivatives PIT Coverage And Basis/Funding Redesign Design

Date: 2026-06-10

## Purpose

Round 25 continues the evidence-first route after Round 24 completed candidate
quality and cost-aware feasibility controls but produced zero
`feasibility_passed` candidates.

The next blocker is not event-driven backtest. The real blocker is upstream
source and hypothesis quality:

1. execution-history candles from `binance_public` and `ccxt` overlap for the
   same symbol/timeframe/timestamp and are counted as duplicate timestamps;
2. derivatives feeds are shallow and partially missing from first-party USD-M
   ingestion;
3. derivatives candidate screens can emit context signals, but feasibility does
   not yet turn derivatives time series into historical observations;
4. endpoint limits are too coarse in current source coverage, so recent-window
   feeds and pageable feeds are not distinguished precisely.

Round 25 therefore adds canonical point-in-time source handling and a
read-only basis/funding/crowding observation layer before another feasibility
v2 run. It does not register strategies, open event-driven backtest, open
paper collection, touch live capital, access wallets, or route orders.

## Baseline From Round 24

Round 24 final artifacts are under:

`var/reports/evidence-universe-lab/round-24-cost-aware-main/`

The final Round 24 lab reported:

- data-depth readiness: `ready`;
- candidates evaluated: 11;
- feasible candidates: 0;
- blocked candidates: 11;
- eligible for backtest: `false`;
- reason codes: `insufficient_universe_coverage`,
  `non_positive_cost_adjusted_expectancy`,
  `unstable_walk_forward_performance`, `cost_sensitivity_fragile`, and
  `watchlist_only_source`.

The new local audit found a more specific explanation for part of
`insufficient_universe_coverage`: BTC/USDT, ETH/USDT, and SOL/USDT have
`ccxt` and `binance_public` candles at the same timestamps. Binance Public Data
itself has no duplicate rows for the eight Round 24 symbols, but the universe
builder currently mixes execution-history sources before duplicate checks.

## Research Findings

Round 25 Smart Search evidence is stored locally at:

`var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/`

Key fetched findings:

- Binance Public Data provides downloadable daily/monthly public market data;
  USD-M futures `klines` files come from `/fapi/v1/klines`.
- Binance long/short and taker buy/sell endpoints explicitly state that only
  the latest 30 days are available, with `limit` default 30 and max 500.
- Binance premium-index klines have `limit` default 500 and max 1500.
- Binance funding-rate history has `limit` default 100 and max 1000, and uses
  `startTime`/`endTime` pagination.
- Binance open-interest statistics has `period`, `limit` default 30 and max
  500, and `startTime`/`endTime` fields.
- Binance basis has `period`, `limit` default 30 and max 500, and
  `startTime`/`endTime` fields, but the fetched official page does not include
  the same explicit latest-30-days sentence as long/short and taker.
- Tardis documents longer historical Binance USDS-M futures channels, including
  generated long/short and taker ratio channels, but that is a third-party
  historical-data dependency and is not the default Round 25 path.
- Time-series validation must keep chronological train/test ordering and use a
  purge/gap where needed.
- Lookahead checks and transaction-cost assumptions remain mandatory before any
  backtest/paper promotion.

## Design Decision

Use the official/free source path first. Round 25 adds source canonicalization,
endpoint metadata, first-party USD-M funding/open-interest ingestion, and
read-only derivatives observation builders. It records third-party historical
sources as a future source-qualification option, not as a default dependency.

The implementation order is deliberate:

1. fix canonical execution-history coverage so duplicate-source overlap stops
   blocking valid market history;
2. add endpoint-level derivatives metadata so recent-window context is not
   confused with long-history proof;
3. add Binance USD-M funding and open-interest statistics ingestion;
4. include funding/open-interest in source coverage roles;
5. add derivatives temporal observations in feasibility;
6. rerun the lab and persist actual pass/block results.

## Architecture

### Canonical Execution History

Add a canonicalization helper in the evidence universe layer. For
`market_candle` execution history, records are keyed by
`(exchange_symbol, timeframe, observed_at)`. If multiple qualified sources
provide the same key, the canonical record is selected by deterministic source
priority:

1. `binance_public`
2. `ccxt`
3. any other qualified source in lexical order

The report should distinguish true duplicate timestamps within a canonical
source from overlap between redundant sources. Redundant overlap should not
create `duplicate_timestamps`, but it should be visible as a warning or
coverage note so operators know the canonical source choice.

### Endpoint Limit Metadata

Add endpoint-level metadata for derivatives record types. The metadata must
track:

- source;
- record type;
- feed;
- endpoint family;
- role;
- max limit;
- whether the official docs state latest-30-days only;
- whether start/end pagination exists;
- whether the feed is execution-eligible or context-only.

This replaces broad assumptions such as treating all derivatives as equivalent
recent-window feeds. Long/short and taker are recent-window context. Funding,
premium-index, basis, and open-interest statistics may be pageable but still
must pass empirical coverage checks before being used as historical proof.

### Binance USD-M Funding And Open Interest

Extend first-party Binance USD-M ingestion with:

- `GET /fapi/v1/fundingRate` as `funding_rate` records with source
  `binance_usdm`;
- `GET /futures/data/openInterestHist` as `open_interest` records with source
  `binance_usdm`.

The CLI keeps the existing explicit `--source binance-usdm --allow-network`
safety gate. The new feeds use the same read-only ingestion path as existing
premium/basis/long-short/taker feeds.

### Source Coverage

Update `EvidenceUniverseReport.source_coverage` to include `funding_rate` and
`open_interest` as `recent_derivatives_context`. Source-health requirements
must map to their exact feed names:

- `funding_rate_history`;
- `open_interest_history`;
- `premium_index_klines`;
- `basis`;
- `global_long_short_account_ratio`;
- `taker_buy_sell_volume`.

Coverage must report endpoint metadata flags so downstream feasibility can
explain why a candidate is blocked by short-window context or by missing
historical proof.

### Derivatives Temporal Observations

Add read-only feasibility observation builders for these candidates:

- `perp_spot_basis_funding_deviation`;
- `funding_basis_convergence_liquidity_filter`;
- `derivatives_crowding_price_action`;
- `derivatives_crowding_recent_window_price_action`.

The builders must use only records observed at or before the signal timestamp,
then evaluate the next available market candle return. They remain long-only or
research-directional at feasibility stage; they do not create orders.

Required alignment rules:

- build per-symbol timestamp maps from canonical market candles;
- join derivatives records to the latest available market timestamp at or
  before the derivative timestamp;
- require the next market candle to compute `gross_return`;
- compute `signal_score` from absolute basis/funding/crowding deviation;
- keep existing cost-aware filtering and walk-forward gates;
- block with existing reasons when samples, splits, months, assets, cost
  sensitivity, or universe coverage remain insufficient.

### Reporting And Memory

Round 25 writes a new phase report and updates project memory with:

- canonical overlap counts;
- endpoint metadata coverage;
- Binance USD-M funding/open-interest counts if collected;
- derivatives candidate sample counts;
- final feasibility pass/block reasons;
- explicit backtest eligibility.

## Success Criteria

Round 25 is complete when:

- the design, implementation plan, path map, evidence index, project state, and
  roadmap are persisted;
- market candle duplicate checks no longer treat qualified redundant source
  overlap as true duplicate timestamps;
- Binance USD-M funding-rate history and open-interest history are available as
  first-party ingestion feeds and CLI choices;
- source coverage includes `funding_rate` and `open_interest` with exact
  source-health feed mapping;
- endpoint metadata distinguishes latest-30-days-only context from pageable
  feeds;
- derivatives candidates can produce historical feasibility observations when
  aligned data exists;
- a bounded Round 25 lab rerun writes artifacts and persists candidate-state
  memory;
- backtest, paper, live, wallet, order routing, and real capital remain blocked
  unless a candidate actually reaches `feasibility_passed`.

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
- No default dependency on paid third-party historical derivatives data.
- No use of latest DEX/trending/watchlist sources as historical execution
  evidence.

## Evidence References

- Binance funding-rate history:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History>
- Binance open interest:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest>
- Binance open-interest statistics:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics>
- Binance long/short ratio:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio>
- Binance taker buy/sell volume:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Taker-BuySell-Volume>
- Binance basis:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Basis>
- Binance premium-index klines:
  <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Premium-Index-Kline-Data>
- Binance Public Data:
  <https://github.com/binance/binance-public-data>
- Tardis Binance futures historical data:
  <https://docs.tardis.dev/historical-data-details/binance-futures>
- Perpetual futures research:
  <https://arxiv.org/html/2212.06888v5>
- TimeSeriesSplit:
  <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
- Freqtrade lookahead analysis:
  <https://www.freqtrade.io/en/stable/lookahead-analysis/>
- QuantStart transaction costs:
  <https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/>
