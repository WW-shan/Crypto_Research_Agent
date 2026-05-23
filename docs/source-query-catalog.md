# Source Query Catalog

This query catalog records slow research questions for optional Dune and The
Graph sources. It is a planning and qualification artifact, not a live trading
or order-routing surface. Queries must run through local operator
configuration, redact credentials, and persist only research-safe snapshots or
source-health rows.

## Dune Queries

| Query ID | Research Question | Expected Columns | Credential | Blocked Reason Without Credential | Safety Notes |
| --- | --- | --- | --- | --- | --- |
| `stablecoin_net_flow_by_chain` | Are stablecoin balances expanding or contracting on chains tied to watchlist assets? | `day`, `chain`, `token_symbol`, `net_flow_usd`, `supply_usd` | required API key | `credential_required` | slow regime context only; no bridge race or private RPC dependency |
| `dex_volume_liquidity_shift` | Is DEX volume migrating between venues or chains for a watched pair? | `day`, `chain`, `dex`, `base_symbol`, `quote_symbol`, `volume_usd`, `liquidity_usd` | required API key | `credential_required` | watchlist signal; no direct DEX execution quote |
| `protocol_revenue_trend` | Are fees or revenue improving for protocols connected to a sector thesis? | `day`, `protocol`, `fees_usd`, `revenue_usd`, `active_users` | required API key | `credential_required` | slow fundamentals only |
| `exchange_flow_regime` | Are exchange inflow/outflow style slow metrics changing for a major asset? | `day`, `asset`, `inflow_usd`, `outflow_usd`, `netflow_usd` | required API key | `credential_required` | use only if methodology is documented and reproducible |

Dune query results must include row metadata and a query identifier. The
operator may record a redacted local credential marker with
`source-probe --credential-configured`; no real API key belongs in git, docs,
logs, reports, screenshots, memory, or tests.

## The Graph Queries

| Query Name | Research Question | Expected Schema | Credential | Blocked Reason Without Endpoint | Safety Notes |
| --- | --- | --- | --- | --- | --- |
| `pool_snapshot` | Is liquidity deep enough and changing slowly enough for a pair to remain on a watchlist? | `data.pools[].id`, `liquidity`, `volumeUSD`, `token0`, `token1`, `_meta.hasIndexingErrors` | optional API key or gateway config | `missing_config` | source-probe target `thegraph_pool_snapshot` checks parseability before use |
| `reserve_change` | Are reserves moving in a way that supports or rejects a liquidity migration hypothesis? | `data.pairs[].id`, `reserve0`, `reserve1`, `reserveUSD`, `trackedReserveETH`, `_meta` | optional API key or gateway config | `missing_config` | not a live execution signal |
| `protocol_pool_fees` | Are fee and volume trends strengthening for a protocol-specific thesis? | `data.pools[].id`, `feesUSD`, `volumeUSD`, `totalValueLockedUSD`, `_meta` | optional API key or gateway config | `missing_config` | slow fundamentals only |

Every GraphQL query must request `_meta` when the subgraph supports it so the
operator can inspect indexing errors. Query text, variables, endpoint URLs with
embedded credentials, and provider headers must be redacted from failure
surfaces.

## Promotion Rule

A catalog entry can support a validator only after:

1. Smart Search or official docs confirm the source shape.
2. `source-probe` reaches `ResearchUsable` on the required route.
3. The project adds a typed model and data-quality checks for fields used by a
   validator, or explicitly keeps the source watchlist-only.
4. Repeated canary runs show fresh, nonzero, non-duplicated, non-skewed rows.
5. The source remains inside the charter: no wallet keys, no live order
   routing, no live execution, no premium RPC, no speed edge, and no live
   capital.
