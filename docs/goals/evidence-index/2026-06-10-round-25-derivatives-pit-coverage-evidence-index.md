# Round 25 Smart Search Evidence Index

Date: 2026-06-10

This index makes the ignored local Smart Search evidence auditable from the
repository without committing raw `var/` files. Raw Smart Search files remain
local runtime artifacts under `var/smart-search-evidence/` by policy.

## Evidence Directory

- `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/`

## Summary

- Indexed files: 24.
- Empty files: 3 markdown fetch attempts for long/short, taker, and basis are
  empty and must not be cited; JSON fetches for the same pages succeeded.
- Purpose: support Round 25 canonical execution-history, derivatives endpoint
  metadata, first-party Binance USD-M funding/open-interest ingestion, and
  basis/funding/crowding observation redesign.
- Repo-level persistence: this index plus the Round 25 design, plan, path map,
  project state, roadmap, and phase report.
- Raw evidence persistence: ignored local `var/` only.
- Safety: no secrets, no wallet access, no live order routing, no real capital.

## Source Themes

- Binance Public Data long-history USD-M futures market candles.
- Binance USD-M endpoint-specific derivatives limits and pagination.
- Third-party historical derivatives source qualification as a future option,
  not the default Round 25 dependency.
- Perpetual futures funding/basis theory and empirical risk.
- Chronological validation, purge/gap split discipline, lookahead checks, and
  transaction-cost modeling.

## File Hashes

| SHA-256 | Local path |
| --- | --- |
| `96c337fa920c37e529c71918281ea7576113ab10f8009134cb1cf9599cc49bbe` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/00-deep-plan.json` |
| `1f7197614acc3cb68bf648bc012960cf6133a069064ed26f18cec40b1d0cf976` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/01-broad-binance-derivatives.json` |
| `09e474f9ae326225833f734455318f4de20b1436a9d5ae242b22da157a691b37` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/02-broad-perp-signal-research.json` |
| `1ff021743e7cad04f0dd2f20df89a281c85906d052e85984c74cbe4418e8a2f5` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/03-broad-point-in-time-validation.json` |
| `79a098236bd486fa386ac38c86ce3514cdcf30595b809e08408338b0d650ef70` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/10-fetch-binance-funding-rate-history.md` |
| `0a0940e0e5da59221cf557f290cd146b2cb7b58830d19878ac3d28c89831581a` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/11-fetch-binance-open-interest.md` |
| `4efc1126a735a8d4d5a713ad98ccda7f5c2e013c27cada7d2e9f44d187f39742` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/12-fetch-binance-open-interest-statistics.md` |
| `1f67f371ece1a9775e294f086ee62eb4f443747e1bfb9e879aca3c8d775afd5f` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/13-fetch-binance-long-short-ratio.json` |
| `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/13-fetch-binance-long-short-ratio.md` |
| `5c45b30e43bda59bd5e31d93f0d04d036363f74f6ad1863e0dfb60a9e7f071eb` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/14-fetch-binance-taker-buy-sell.json` |
| `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/14-fetch-binance-taker-buy-sell.md` |
| `7a263483e55c09fe46e796e3cb294ab371b4a020bb30231a77193cf5af3d254f` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/15-fetch-binance-basis.json` |
| `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/15-fetch-binance-basis.md` |
| `942d6ee956ba3019d2c1e9aac058a738f180871103814a95add474f38a279b64` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/16-fetch-binance-premium-index-kline.json` |
| `d12add019cb18e7325d630a98992b463f77e7b242d9334fb9ddd4790fe271440` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/17-fetch-binance-public-data.json` |
| `906e93a75a1368f678bdc2c61996c5924ee4e24ba7b1aee95cfc6b19d1cbacae` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/20-fetch-tardis-binance-futures.json` |
| `1882e0a5b89bf258466d84b84b2620ec9b90483505de0b05fd0b22629cb11889` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/30-fetch-arxiv-perpetual-futures.json` |
| `d3e0a137e2b1344cc15ac40ddd0bc59ccc0db4ed1d657af9c648e9f88c0ff822` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/31-fetch-arxiv-bitcoin-cost-aware.json` |
| `fba6416c1709dd35eadc719a0964c5449ae0037348cf08b893e219f878307999` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/32-fetch-arxiv-walk-forward-framework.json` |
| `ef9847e9706df1ee639251cb412502d7de9e5644484e2eddf44806b547120b73` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/33-fetch-sklearn-timeseriessplit.json` |
| `dae5c56721e13f675c546e6815ceb478ce1b28cc75bc3bd8c4ac2f89699eea95` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/34-fetch-freqtrade-lookahead-analysis.json` |
| `6e2b1521e68fef2700a7f321068c5f6fd2b49789297c53cadb1cad21d8d29bea` | `var/smart-search-evidence/2026-06-09-round25-derivatives-point-in-time-redesign/35-fetch-quantstart-costs.json` |

## Evidence Notes

- Cite JSON fetch files for long/short, taker, and basis because markdown fetch
  attempts for those pages are empty.
- Binance long/short and taker buy/sell docs support treating those feeds as
  latest-30-days-only recent derivatives context.
- Binance funding-rate history, premium-index klines, basis, and
  open-interest statistics support endpoint-specific pagination metadata, but
  actual local source coverage must still determine historical usability.
- Tardis evidence supports a future third-party historical-source qualification
  route, but Round 25 does not depend on it by default.
