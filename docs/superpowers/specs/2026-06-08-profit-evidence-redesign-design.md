# Profit Evidence Redesign Design

## Objective

Resolve the current profit-evidence blocker without weakening the charter:
find a new evidence-first path from public, slow, low-capital data to
validation and paper outcomes after all executable funding families were
stopped by governance.

This design does not authorize live execution, wallet access, exchange order
routing, private RPC, premium infrastructure, MEV, speed edges, or automatic
promotion from research to capital deployment.

## Current Evidence Baseline

Current git state at design time:

- Branch: `main`
- Remote state: `main...origin/main`
- Latest pushed closeout: `319456b docs: finalize evidence recovery status`
- Existing Goal tool state: previous goal is complete; this thread cannot open
  a second goal with the available goal tool, so this design records the new
  owner-directed execution loop in docs and local plan files.

Current local ledgers in `var/research.sqlite`:

| Evidence item | Current actual state | Required or expected state |
| --- | --- | --- |
| Validation rows | 5 total | enough approved rows to justify paper collection |
| Approved validation | 0 | at least one approved strategy-family validation |
| Paper outcomes | 5 total | at least 30 observations for rollout-review relevance |
| Closed paper outcomes | 0 | closed observations with cost-adjusted PnL |
| Blocked paper outcomes | 5 | failure rate no more than 10% for rollout gates |
| Net paper PnL | 0 | positive cost-adjusted expectancy |
| Paper portfolio candidate | none | at least one candidate before owner review |
| Executable funding families | all stopped | at least one active executable family |
| Live execution | false | must remain false |

The stopped executable families are:

- `funding_extremity_price_confirmation`
- `funding_mean_reversion_after_extreme`
- `funding_open_interest_crowding`

The shared blocker reasons are:

- `no_extreme_funding`
- `insufficient_trades`
- `non_positive_expectancy`
- `non_positive_net_return`
- `unstable_walk_forward_performance`

This means the project is operationally healthy enough to collect evidence, but
the current executable strategy set has no viable profit candidate.

## Deep Research Evidence

Evidence directory:

`var/smart-search-evidence/2026-06-08-profit-evidence-redesign/`

Smart Search commands and artifacts:

- `smart-search doctor --format json`: provider profile was usable. Exa,
  Firecrawl, and Zhipu were not configured; xAI Responses, Tavily fetch/search,
  and Context7 were available.
- `smart-search deep "Crypto Research Agent profit-evidence blocker: find
  charter-compliant low-capital public-data crypto strategy redesign solutions
  after funding strategies stopped; need slow public data, no live execution,
  no MEV, no premium infrastructure, evidence-first validation, paper
  simulation, walk-forward, 30/60/90 out-of-sample plan" --budget deep
  --format json`: produced a deep-research plan requiring broad discovery,
  docs/API evidence, cross-validation, and fetch-before-claim.
- `01-broad-strategy-search.json`: broad strategy discovery.
- `02-binance-market-data-search.json`: Binance official derivatives market
  data discovery.
- `03-crypto-momentum-paper-search.json`: academic momentum/reversal discovery.
- `04-defi-dex-source-search.json`: DeFiLlama and DexScreener source discovery.
- `05-binance-open-interest-statistics.md`
- `06-binance-long-short-ratio.md`
- `07-binance-taker-buy-sell-volume.md`
- `08-binance-premium-index-kline.md`
- `09-binance-basis.md`
- `11-dexscreener-api.md`
- `12-binance-public-data.md`
- `13-defillama-faq.md`
- `14-crypto-momentum-reversal-hse.md`
- `15-size-volume-momentum-reversal.md`
- `16-sklearn-time-series-split.md`

Fetch limitations:

- `10-defillama-api.md` fetch returned nonzero and no usable page body. The
  design uses the successfully fetched DeFiLlama FAQ/methodology page instead.
- Exa and Zhipu were unavailable in local Smart Search configuration, so this
  design treats broad search results as discovery and relies on fetched
  official pages or paper PDFs for claim-level evidence.

## External Findings Used

Official Binance USD-M evidence:

- `GET /futures/data/openInterestHist` returns historical open-interest
  statistics with `sumOpenInterest`, `sumOpenInterestValue`, `timestamp`,
  `symbol`, required `symbol` and `period`, and max `limit=500`.
- `GET /futures/data/globalLongShortAccountRatio` returns public long/short
  account ratio fields, but the docs state the latest 30 days only.
- `GET /futures/data/takerlongshortRatio` returns taker buy/sell volume ratio
  fields, also latest 30 days only.
- `GET /fapi/v1/premiumIndexKlines` returns premium-index kline bars with
  `startTime`, `endTime`, and max `limit=1500`.
- `GET /futures/data/basis` returns `basis`, `basisRate`, `futuresPrice`,
  `indexPrice`, and `timestamp` for a pair and contract type.
- Binance Public Data provides daily and monthly public market data files for
  spot and futures klines/trades/aggregate trades; USD-M futures kline files
  map to `/fapi/v1/klines`.

DeFiLlama and DexScreener evidence:

- DeFiLlama reports that TVL, stablecoin supply, CEX assets, yields, DEX
  volume/fees/revenue style metrics update hourly or daily depending on metric
  class, and its API is public and free to use.
- DexScreener official docs expose pair search and pair lookup endpoints with
  liquidity, volume, price-change, transaction, FDV, market-cap, and pair
  metadata fields. These are better suited for discovery/watchlists unless the
  project persists enough snapshots to build historical evidence.

Academic/methodology evidence:

- Dobrynskaya's cryptocurrency momentum/reversal paper reports short-horizon
  momentum up to roughly 2-4 weeks and longer-horizon reversal in broad
  cryptocurrency samples, with strong caution that sample choice and period
  matter.
- Ficura's size/volume paper reports that previously observed short-term
  reversal is mainly a small/illiquid-coin effect, while large/liquid coins
  exhibit short-term momentum; it also warns that low-volume reversal may be
  hard to trade at observed closes and that shorting liquid winners can be
  practically challenging.
- scikit-learn TimeSeriesSplit documentation confirms that ordinary
  cross-validation is inappropriate for time-ordered data because it can train
  on future data and evaluate on the past; this supports the existing
  walk-forward/fail-closed validation stance.

## Local Feasibility Findings

Already present:

- `src/crypto_alpha_agent/data/source_probe.py` has source-probe targets for
  `binance_usdm_open_interest_history`,
  `binance_usdm_premium_index_klines`, `binance_usdm_basis`, and
  `binance_usdm_global_long_short_account_ratio`.
- Proxy-routed probes executed during this design for premium index klines,
  basis, and global long/short account ratio all exited 0 with HTTP 200,
  `parse_status=parsed`, `typed_record_count=1`,
  `provider_status=ResearchUsable`, `network_route=proxy`,
  `uses_real_capital=false`, and `live_order_routing=false`.
- `src/crypto_alpha_agent/data/ingestion.py` already writes typed records for
  CCXT OHLCV, CCXT funding history, CCXT open-interest history, DexScreener
  pairs, and DeFiLlama yield pools.
- `src/crypto_alpha_agent/data/models.py` currently supports record types:
  `market_candle`, `funding_rate`, `open_interest`, `dex_pair`,
  `defi_yield`, `research_snapshot`, and `source_health`.
- Strategy registry supports executable funding families and research-only
  watchlists for DeFi, DEX, and volatility compression/expansion.

Not yet present:

- No typed records for Binance USD-M `basis`, `premium_index_kline`,
  `global_long_short_account_ratio`, or `taker_buy_sell_volume`.
- No source-probe target for `takerlongshortRatio`.
- No product ingestion path for Binance USD-M derivatives factors outside CCXT.
- No active executable non-funding strategy family.
- Current watchlists do not support paper simulation by design.
- Current evidence-run default still centers on funding-family records; new
  strategy/data campaigns need explicit family-specific ingestion and
  validation.

## Design Decision

Use an evidence-first redesign path with three nested gates:

1. Data gate: upgrade already-proven public Binance derivatives sources from
   source-probe-only to typed persisted records.
2. Feasibility gate: run a report-local feasibility scan over available
   records before registering any new paper-simulated strategy.
3. Strategy gate: add exactly one new executable family only if the feasibility
   scan has enough observations, clean timestamp alignment, positive
   cost-adjusted historical evidence, and stable walk-forward behavior.

The recommended first candidate is a large/liquid momentum regime family, not
a stopped funding-family variant.

Reasoning:

- The stopped funding families failed because they found no extreme funding,
  no trades, no positive expectancy, and unstable walk-forward behavior.
- Binance public derivatives fields can enrich regime filters, but long/short
  and taker buy/sell history is capped to recent windows, so those feeds should
  not be treated as instant long historical proof.
- Academic evidence points toward large/liquid short-horizon momentum as a more
  plausible low-capital public-data candidate than small/illiquid reversal.
- Small/illiquid DEX reversal is intentionally not the first executable path
  because the literature and the project cost model both warn about fill
  quality, stale quotes, and execution realism.

## Candidate Paths

### Path A: Derivatives Factor Ingestion Plus Large/Liquid Momentum

Recommended first path.

Build typed Binance USD-M derivatives factor ingestion:

- `premium_index_kline`
- `basis`
- `global_long_short_account_ratio`
- `taker_buy_sell_volume`

Then build a report-local feasibility scan for a large/liquid universe such as
BTC/USDT, ETH/USDT, and SOL/USDT. Only after feasibility passes should a new
paper-simulated family be added.

Pros:

- Uses official public APIs and already-proven proxy route.
- Matches existing source-probe/source-health architecture.
- Lets derivatives sentiment act as a filter instead of the primary edge.
- Avoids reviving stopped families.

Cons:

- Some Binance sentiment fields are latest-30-days only.
- Multi-symbol validation will require extending runner assumptions.
- No profit proof exists yet.

### Path B: DEX/DeFi Watchlist Deepening

Keep DeFiLlama and DexScreener as research/watchlist paths until enough
snapshots accumulate.

Pros:

- Public, broad coverage.
- Useful for discovery and regime context.

Cons:

- Current data is snapshot-heavy, not long historical evidence.
- DEX small-token opportunities are likely to be fill-sensitive.
- Paper simulation would be easy to overstate without historical snapshots.

### Path C: Stopped-Family Review

Do not use by default.

This would require explicit owner approval and fresh positive validation
evidence before using `--allow-stopped-family`.

Reason for rejection:

- Governance already stopped all executable funding families.
- Repeating the same family set does not produce progress unless the validator
  design or evidence universe changes materially.

### Path D: ML Strategy Expansion

Reject for now.

Reason for rejection:

- It increases overfit risk before basic public factor coverage and
  feasibility reports are complete.
- It would not solve the missing paper evidence problem faster than a simpler
  deterministic candidate.

## Proposed Architecture

### Data Layer

Add a small Binance USD-M derivatives client rather than extending CCXT for
fields CCXT may not expose uniformly.

New module:

- `src/crypto_alpha_agent/data/binance_usdm_derivatives.py`

Responsibilities:

- Public REST GET only.
- Explicit `allow_network` at ingestion boundary, not inside model parsing.
- Proxy support using the existing local proxy environment pattern.
- Parse official Binance payloads into strict models.
- Never log keys, proxy values, or raw headers.

Extend:

- `src/crypto_alpha_agent/data/models.py`
- `src/crypto_alpha_agent/data/ingestion.py`
- `src/crypto_alpha_agent/cli.py`
- `src/crypto_alpha_agent/data/source_probe.py`

New record types:

- `premium_index_kline`
- `basis`
- `long_short_account_ratio`
- `taker_buy_sell_volume`

### Feasibility Layer

Add a report-local feasibility command before registering a new family.

Working name:

- `strategy-feasibility`

First mode:

- `large-liquid-momentum-regime`

Inputs:

- SQLite store.
- Symbol list.
- Timeframe.
- Required record types.
- Minimum aligned observations.
- Walk-forward parameters.
- Fee and slippage assumptions.

Outputs:

- Markdown report under `var/reports/strategy-feasibility/`.
- JSON payload.
- No validation ledger mutation.
- No paper outcome mutation.

Pass conditions:

- At least 3 symbols with sufficient aligned OHLCV observations.
- No stale or duplicate primary candle series.
- Feasibility report has at least 3 walk-forward splits.
- Strategy prototype has positive cost-adjusted expectancy under pessimistic
  fees/slippage.
- Failure reasons are explicit when blocked.

### Strategy Layer

Only after the feasibility report passes, register a new executable family.

Working family:

- `large_liquid_momentum_regime`

Initial behavior:

- Long-only or paper-only directional simulation over large/liquid symbols.
- Rank by 1-2 week return or high-momentum distance to recent high.
- Require liquidity/volume threshold from market candle data.
- Use derivatives factors as filters, not as the primary reason for entry.
- Enforce min trades, walk-forward pass rate, cost-adjusted expectancy, stale
  source checks, notional feasibility, and drawdown limits.

Explicitly excluded:

- Small/illiquid reversal as an executable strategy.
- Shorting as a required live capability.
- Any leverage or live futures routing.

### Reporting And Governance

Extend governance only after the new family can write validation and paper
outcomes.

Until then, governance should keep returning no portfolio candidate.

## Execution Sequence

1. Add missing taker buy/sell source-probe target and tests.
2. Add Binance USD-M derivatives models and typed parser tests.
3. Add derivatives ingestion functions and source-health tests.
4. Add CLI ingestion flags for `--source binance-usdm` and
   `--binance-usdm-feed`.
5. Run proxy-routed smoke ingestion for the new feeds and verify SQLite records.
6. Add report-local strategy feasibility command.
7. Run feasibility on BTC/ETH/SOL data.
8. If blocked, document exact blocker and stop.
9. If passed, plan and implement the new executable strategy family with TDD.
10. Run evidence-run/paper-sim/governance for the new family.
11. Update state, roadmap, and phase report.
12. Commit and push only tracked docs/code/tests; keep `.env`, `var/`, caches,
    databases, and reports unstaged.

## Acceptance Criteria

The redesign phase is successful if one of these is true:

1. A new strategy/data path produces approved validation and at least one
   non-blocked paper outcome, with all safety flags false; or
2. The phase documents a new blocker with fetched source evidence, local source
   qualification, code feasibility, exact failed commands or metrics, and a
   next safe recommendation.

The phase is not successful if it only repeats stopped funding-family runs.

## Safety Review

- Live execution remains blocked.
- Real-capital execution remains blocked.
- Wallet keys remain blocked.
- Order routing remains blocked.
- Private RPC, premium RPC, and speed-edge strategies remain blocked.
- New sources must be public or optional read-only only.
- Local proxy remains operator configuration and must not be logged or
  committed.
- Runtime artifacts under `var/` must remain unstaged.

## Sources

- Binance Open Interest Statistics:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics
- Binance Long/Short Ratio:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio
- Binance Taker Buy/Sell Volume:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Taker-BuySell-Volume
- Binance Premium Index Kline Data:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Premium-Index-Kline-Data
- Binance Basis:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Basis
- Binance Public Data:
  https://github.com/binance/binance-public-data
- DexScreener API reference:
  https://docs.dexscreener.com/api/reference
- DeFiLlama FAQ/methodology:
  https://docs.llama.fi/faqs/frequently-asked-questions
- Cryptocurrency Momentum and Reversal:
  https://conference.hse.ru/files/download_file_ex?hash=FAE0AB2DC7A67656E89A0B1CB27D8C7D&id=3B5EE9A5-0B18-458A-9458-B4ED0F6C6664
- Impact of size and volume on cryptocurrency momentum and reversal:
  https://quantitative.cz/wp-content/uploads/2023/09/impact_of_size_and_volume_on_cryptocurrency_momentum_and_reversal.pdf
- scikit-learn TimeSeriesSplit:
  https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
