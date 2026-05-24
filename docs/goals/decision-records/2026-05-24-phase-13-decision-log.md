# Phase 13 Decision Log - 2026-05-24

## Source Evidence

Committed review artifacts:

- `docs/goals/research-reviews/2026-05-24-daily-quick-scan.md`
- `docs/goals/research-reviews/2026-05-24-weekly-effectiveness-review.md`
- `docs/goals/research-reviews/2026-05-24-monthly-owner-review.md`

Ignored local generated artifacts:

- `var/reports/phase13/daily-empty-ledger.md`
- `var/reports/phase13/weekly-empty-ledger.md`
- `var/reports/phase13/governance-empty-ledger.md`
- `var/reports/phase13/ai-research-memo-empty-ledger.md`
- `var/reports/phase13/historical-bootstrap-empty-ledger.md`
- `var/reports/phase13/historical-bootstrap-empty-ledger.json`
- `var/run-manifests/phase13/historical-bootstrap-empty-ledger.manifest.json`

Safety references:

- `src/crypto_alpha_agent/risk/guardian.py` keeps
  `live_execution_allowed=false`.
- `src/crypto_alpha_agent/evidence/live_readiness.py` keeps
  `live_execution_enabled=false`.
- Report artifacts reviewed in Phase 13 keep `uses_real_capital=false` and
  `live_order_routing=false`.

## Family Decisions

| Strategy family | Decision | Owner-facing status | Reason codes | Evidence refs | Next review trigger |
| --- | --- | --- | --- | --- | --- |
| `defi_yield_regime_watchlist` | `add_data` | Add DeFi yield records before judging usefulness. | `missing_evidence`, `source_health_missing`, `paper_simulation_not_supported` | `governance-empty-ledger.md`; `historical-bootstrap-empty-ledger.md` | DefiLlama/fundamental records are ingested and a watchlist report changes. |
| `dex_liquidity_volume_watchlist` | `add_data` | Add DEX pair/liquidity records before judging usefulness. | `missing_evidence`, `source_health_missing`, `paper_simulation_not_supported` | `governance-empty-ledger.md`; `historical-bootstrap-empty-ledger.md` | DEX liquidity/volume records are ingested and source health is non-empty. |
| `funding_extremity_price_confirmation` | `add_data` | Add market candles and funding records, then validate and collect paper observations. | `missing_evidence`, `sample_below_target`, `missing_validation_evidence`, `source_health_missing` | `daily-empty-ledger.md`; `governance-empty-ledger.md`; `ai-research-memo-empty-ledger.md` | First new validation or paper outcome appears in the forward ledger. |
| `funding_mean_reversion_after_extreme` | `add_data` | Add market candles and funding records, then validate the bounded mean-reversion family. | `missing_evidence`, `sample_below_target`, `missing_validation_evidence`, `source_health_missing` | `daily-empty-ledger.md`; `governance-empty-ledger.md`; `ai-research-memo-empty-ledger.md` | First new validation or paper outcome appears in the forward ledger. |
| `funding_open_interest_crowding` | `add_data` | Add market candles, funding records, and open-interest records before validation can mean anything. | `missing_evidence`, `missing_open_interest_records`, `sample_below_target`, `source_health_missing` | `governance-empty-ledger.md`; `historical-bootstrap-empty-ledger.md` | Qualified open-interest records are ingested and validation no longer blocks on missing OI. |
| `volatility_compression_expansion_watchlist` | `add_data` | Add market-candle history for watchlist analysis before judging usefulness. | `missing_evidence`, `missing_market_candle_records`, `paper_simulation_not_supported` | `governance-empty-ledger.md`; `historical-bootstrap-empty-ledger.md` | Market-candle records exist and a volatility watchlist report changes. |

## Major Cycle Decisions

| Cycle | Decision | Evidence refs | Rationale | Revisit when |
| --- | --- | --- | --- | --- |
| Forward evidence campaign | `add_data` | Phase 7 report; `historical-bootstrap-empty-ledger.md`; monthly review | Historical bootstrap and 30/60/90 targets exist, but no forward paper evidence exists in the local review sample. | Daily/weekly reports show non-zero forward observations. |
| AI research loop | `keep_collecting` | `ai-research-memo-empty-ledger.md`; weekly review | AI proposals are bounded, registered, and safe, but still depend on `gap:supported_registered_baseline`. | AI proposals start repeating despite new evidence or propose invalid data/validators. |
| Data source retirement | no action | daily quick scan; historical bootstrap source steps | Network collection was blocked by local policy, not by source uselessness. No source is retired today. | Source-health rows repeatedly show stale, unusable, expensive, or decision-irrelevant data. |
| Live execution and tiny-live work | `pause_project_line` | monthly review; rollout/tiny-live safety docs | No family has enough evidence for owner decision review, and the charter blocks real capital. | Only after a future explicit charter revision plus rollout gates. |

## Decision Summary

- `keep_collecting`: AI research loop only, as a proposal queue subordinate to
  evidence.
- `stop_family`: none today.
- `redesign_validator`: none today; there is not enough data to distinguish a
  validator flaw from missing inputs.
- `add_data`: every registered strategy family and the forward evidence
  campaign.
- `retire_data_source`: none today.
- `pause_project_line`: live execution and tiny-live work under the current
  charter.
