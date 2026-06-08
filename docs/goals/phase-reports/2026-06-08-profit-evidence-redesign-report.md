# Profit Evidence Redesign Report

- Date: 2026-06-08
- Status: Completed as a data/feasibility slice; strategy registration blocked
- Design:
  `docs/superpowers/specs/2026-06-08-profit-evidence-redesign-design.md`
- Plan:
  `docs/superpowers/plans/2026-06-08-profit-evidence-redesign.md`
- Feasibility artifact:
  `var/reports/strategy-feasibility/latest.json`

## Summary

This slice followed the evidence-first path after all executable funding
families were stopped by governance. Deep source research and local probes
identified public Binance USD-M derivatives feeds as the next useful data
upgrade. The implementation added typed public ingestion for premium-index
klines, basis, global long/short account ratio, and taker buy/sell volume.

The data path now works, but no new strategy family was registered. The first
`strategy-feasibility` run blocked the large-liquid momentum regime because the
local database contained 434 `BTC/USDT` 1h candles but no `ETH/USDT` or
`SOL/USDT` 1h market candles. A follow-up data collection filled that gap with
1000 aligned 1h candles for each symbol. The second feasibility run then
blocked for the stronger reason: `non_positive_cost_adjusted_expectancy`.

## What Changed

- Added Binance USD-M taker buy/sell volume to `source-probe`.
- Added strict data models for:
  - `premium_index_kline`
  - `basis`
  - `long_short_account_ratio`
  - `taker_buy_sell_volume`
- Added a public requests-based Binance USD-M derivatives client.
- Added safe ingestion functions and `ingest --source binance-usdm` CLI support.
- Added source-health writes for each Binance USD-M derivatives ingestion.
- Added the read-only `strategy-feasibility` CLI and report builder for
  `large-liquid-momentum-regime`.
- Kept all new paths at `uses_real_capital=false` and
  `live_order_routing=false`.

## Search And Source Evidence

Deep research artifacts were saved under:

`var/smart-search-evidence/2026-06-08-profit-evidence-redesign/`

Key source conclusions:

- Binance USD-M open interest, basis, premium index klines, global long/short
  ratio, and taker buy/sell volume are public market-data endpoints.
- Binance long/short and taker buy/sell statistics have recent-history limits,
  so they are useful for current context and paper observation, not full
  long-horizon historical proof by themselves.
- DexScreener and DeFiLlama remain useful research context sources but still
  need historical snapshot depth before they can drive execution-realistic
  paper evidence.
- Academic momentum/reversal evidence supports testing liquid large-cap
  momentum separately from small illiquid reversal effects.

## Live Smoke Results

The original `crypto-alpha-agent ingest` smoke command reached the real LLM
readiness gate and produced no output for more than 90 seconds. That process
was terminated and recorded as a CLI gate follow-up. Direct calls to the new
ingestion functions were then used to isolate the public-data path.

Direct ingestion succeeded:

- `premium_index_kline`: 24 fetched, 24 written
- `basis`: 24 fetched, 24 written
- `long_short_account_ratio`: 24 fetched, 24 written
- `taker_buy_sell_volume`: 24 fetched, 24 written

SQLite also contains successful source-health rows for all four feeds.

Follow-up CLI gate diagnostics later reran `llm-health-check`,
`ingest --offline-check`, and `ingest --source binance-usdm` with a bounded
120-second subprocess timeout. All three commands exited 0 in roughly 9 to 10
seconds. That makes the earlier stall a transient provider-latency observation,
not a reproduced CLI routing or Binance ingestion bug.

## Feasibility Result

Command:

```bash
uv run --extra dev crypto-alpha-agent strategy-feasibility --db var/research.sqlite --mode large-liquid-momentum-regime --symbol BTC/USDT --symbol ETH/USDT --symbol SOL/USDT --timeframe 1h --out var/reports/strategy-feasibility/latest.md --json-out var/reports/strategy-feasibility/latest.json --current-capital-usd 300
```

Initial result:

- readiness: `blocked`
- reason code: `insufficient_aligned_history`
- BTC/USDT 1h records: 434
- ETH/USDT 1h records: 0
- SOL/USDT 1h records: 0
- aligned records: 0
- derivatives context counts: 24 rows per new Binance USD-M feed

Follow-up data collection:

- BTC/USDT 1h records: 1000
- ETH/USDT 1h records: 1000
- SOL/USDT 1h records: 1000
- aligned records: 1000

Follow-up feasibility result:

- readiness: `blocked`
- reason code: `non_positive_cost_adjusted_expectancy`
- split 1 cost-adjusted return mean: -0.0010583810470065262
- split 2 cost-adjusted return mean: -0.0014155221362016344
- split 3 cost-adjusted return mean: -0.0021886709892294295
- split win rate: 0.3575757575757576 for all three splits

## Decision

No strategy validator, paper runner, or registry entry was added. The final
blocked feasibility result is the correct outcome because the candidate does
not show positive cost-adjusted expectancy across the available walk-forward
splits.

## Next Smallest Useful Step

Do not register `large-liquid-momentum-regime` as implemented. The next useful
work is a new hypothesis/design step that changes the signal definition or
chooses another charter-compliant family, then runs the same feasibility gate
before any strategy code.
