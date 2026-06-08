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

The data path now works, but no new strategy family was registered. The new
`strategy-feasibility` command blocked the large-liquid momentum regime because
the local database contains 434 `BTC/USDT` 1h candles but no `ETH/USDT` or
`SOL/USDT` 1h market candles, so multi-symbol aligned history is zero.

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

## Feasibility Result

Command:

```bash
uv run --extra dev crypto-alpha-agent strategy-feasibility --db var/research.sqlite --mode large-liquid-momentum-regime --symbol BTC/USDT --symbol ETH/USDT --symbol SOL/USDT --timeframe 1h --out var/reports/strategy-feasibility/latest.md --json-out var/reports/strategy-feasibility/latest.json --current-capital-usd 300
```

Result:

- readiness: `blocked`
- reason code: `insufficient_aligned_history`
- BTC/USDT 1h records: 434
- ETH/USDT 1h records: 0
- SOL/USDT 1h records: 0
- aligned records: 0
- derivatives context counts: 24 rows per new Binance USD-M feed

## Decision

No strategy validator, paper runner, or registry entry was added. The blocked
feasibility result is the correct outcome because registering a family without
multi-symbol aligned history would repeat the prior failure mode: plausible
strategy code with weak or missing evidence.

## Next Smallest Useful Step

Collect aligned 1h market candles for BTC/USDT, ETH/USDT, and SOL/USDT over
the same window, then rerun `strategy-feasibility`. Only if the report produces
enough walk-forward splits with positive cost-adjusted expectancy should a new
strategy-registration plan be written.

The CLI LLM readiness gate also needs bounded-timeout investigation before
`ingest` can be used as the smoke driver for this data path.
