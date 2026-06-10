# Source Coverage Matrix

Phase 8 uses this source coverage matrix to separate qualified research inputs
from candidates that still need canary evidence. The matrix covers public
research data only. It does not grant wallet access, exchange trading keys,
order submission, no live order routing, or live capital authority.

## Qualification States

`source-probe` records provider status transitions as source-health evidence:

- `Candidate`: listed in the catalog but not usable yet.
- `Reachable`: the direct route returned a 2xx HTTP response.
- `ReachableViaProxy`: the local proxy route returned a 2xx HTTP response.
- `Parseable`: the response parsed as JSON for the expected response family.
- `ResearchUsable`: the response parsed and produced nonzero typed records or
  typed candidate rows.
- `ProductionResearchSource`: reserved for sources that pass repeated canary
  runs, write source health, produce nonzero typed records for validator fields,
  and keep missing, stale, duplicate, skew, and failure rates inside operator
  thresholds.

A single successful probe can reach `ResearchUsable`; it must not promote a
source to `ProductionResearchSource`. Dune and The Graph remain optional and
credential-aware. Missing credentials are recorded as a blocked reason, not as
a product failure.

## Matrix

| Provider | Fields | Endpoint Family | Limit Assumption | Credential | Route Notes | Core | Local Status | Typed Persistence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance Public Data | OHLCV archive candles | public monthly archives | archive download cadence | none | direct or local proxy by operator | yes | implemented before Phase 8 | `market_candle` |
| CCXT Binance/OKX/Bybit | OHLCV, funding-rate history | exchange public market data | exchange-specific CCXT limits | none | explicit `--allow-network`; source health records failures | yes | implemented before Phase 8 | `market_candle`, `funding_rate` |
| CCXT open-interest history | open interest, open-interest value | `fetchOpenInterestHistory` | exchange support varies | none | route through ordinary public APIs only | yes | implemented in Phase 8 | `open_interest` |
| Binance USD-M | funding-rate history | `GET /fapi/v1/fundingRate` | max 1000 rows; start/end pagination | none | `source-probe` target `binance_usdm_funding_rate_history` | yes | typed persistence implemented in Round 25 | `funding_rate`, source health |
| Binance USD-M | open-interest history | `GET /futures/data/openInterestHist` | max 500 rows; period plus start/end pagination | none | `source-probe` target `binance_usdm_open_interest_history` | yes | typed persistence implemented in Round 25 | `open_interest`, source health |
| Binance USD-M | premium-index klines | `GET /fapi/v1/premiumIndexKlines` | max 1500 rows; start/end pagination | none | `source-probe` target `binance_usdm_premium_index_klines` | yes | typed persistence implemented before Round 25 | `premium_index_kline`, source health |
| Binance USD-M | basis | `GET /futures/data/basis` | max 500 rows; period plus start/end pagination | none | `source-probe` target `binance_usdm_basis` | yes | typed persistence implemented before Round 25 | `basis`, source health |
| Binance USD-M | global account long/short ratio | `GET /futures/data/globalLongShortAccountRatio` | latest 30 days; max 500 rows | none | `source-probe` target `binance_usdm_global_long_short_account_ratio` | yes | typed persistence implemented before Round 25 | `long_short_account_ratio`, source health |
| Binance USD-M | taker buy/sell volume | `GET /futures/data/takerlongshortRatio` | latest 30 days; max 500 rows | none | `source-probe` target `binance_usdm_taker_buy_sell_volume` | yes | typed persistence implemented before Round 25 | `taker_buy_sell_volume`, source health |
| Bybit V5 | open-interest history | `GET /v5/market/open-interest` | public V5 market-data limits | none | `source-probe` target `bybit_open_interest_history` | yes | probe candidate | source health only |
| OKX V5 | open interest | `GET /api/v5/public/open-interest` | public-data request limits | none | `source-probe` target `okx_open_interest` | yes | probe candidate | source health only |
| DexScreener | pair price, liquidity, volume, token metadata | `GET /latest/dex/search` and pair/token families | pair endpoints documented at 300 requests per minute | none | local snapshots are watchlist inputs until history exists | yes | pair snapshots implemented; probe candidate | `dex_pair`, source health |
| DefiLlama yields | pool TVL and APY | `GET /pools` | public reasonable-use limits | none | slow fundamentals only | yes | yield snapshots implemented; probe candidate | `defi_yield`, source health |
| DefiLlama fundamentals | protocol TVL and fundamentals | `GET /protocols` | public reasonable-use limits | none | candidate for Phase 9/11 evidence context | yes | probe candidate | source health only |
| Dune | named query result rows and metadata | `GET /v1/query/{query_id}/results` | credentialed API limits | required API key | key marker only; no key values in docs, logs, reports, memory, or tests | optional | blocked unless credential configured | generic research snapshot and source health |
| The Graph | pool liquidity, volume, reserves, `_meta` | POST GraphQL subgraph query | gateway and subgraph dependent | optional API key | endpoint and query text must be redacted in failure surfaces | optional | probe candidate | generic research snapshot and source health |

## Source-Health Fields

Phase 8 source-health rows may include:

- `network_route`: `direct`, `proxy`, `blocked`, `unavailable`, or
  `not_applicable` depending on command family.
- `provider_status`: `Candidate`, `Reachable`, `ReachableViaProxy`,
  `Parseable`, `ResearchUsable`, or `ProductionResearchSource`.
- `http_status`, `parse_status`, `typed_record_count`, `endpoint_family`,
  `url_family`, `schema_version`, and `blocked_reason`.

Data-quality reports consume these rows along with typed records. Open-interest
history can now report non-positive values, missing intervals, stale rows,
timestamp skew, duplicate semantic records, and source failures. A missing
optional source remains visible but does not imply live execution or capital
authority.
