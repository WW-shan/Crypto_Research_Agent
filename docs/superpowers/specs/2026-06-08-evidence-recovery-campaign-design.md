# Evidence Recovery Campaign Design

## Summary

The next approved line of work is an evidence recovery campaign, not another
framework expansion. The project already has the charter-compliant research
factory, LLM-native runtime, evidence-run pipeline, strategy registry,
governance reporting, historical bootstrap tooling, VPS operations layer, and
creation-cycle autonomy scaffolding. The current gap is that the latest
successful public-data run restored source collection but did not produce new
validation evidence or paper outcomes for an active strategy family.

The campaign will recover the validation-to-paper path for active,
charter-compliant families, starting with `funding_open_interest_crowding` and
`funding_mean_reversion_after_extreme`. It will not revive a stopped family by
override, add live execution, touch wallets, route orders, use premium data, or
claim tiny-live readiness from historical or narrative evidence.

## Owner Approval

The owner approved the recommended direction on 2026-06-08 after reviewing the
three options:

1. Evidence-first paper path.
2. Broad data-source expansion.
3. Operations automation hardening.

The approved route is option 1: use the existing public-data and strategy
infrastructure to restore active-family validation evidence and paper outcomes
before adding breadth.

## Current State

- `main` is aligned with `origin/main` before this design round.
- Phase 0 through Phase 17 are implemented according to
  `docs/goals/project-completion-state.md`.
- The latest verified public-data run is
  `proxy-fixed-20260607T142806Z`.
- That run completed with `network_route=proxy` and no source-health failures
  for the configured public sources:
  - CCXT OHLCV: 200 records.
  - CCXT funding history: 200 records.
  - DexScreener pairs: 30 records.
  - DefiLlama yield pools: 15940 records.
  - Dune and TheGraph skipped as not configured.
- The same run wrote `validation_evidence_written=0` and
  `paper_outcomes_written=0`.
- The old default family, `funding_extremity_price_confirmation`, is stopped
  by governance memory and was skipped. It must not be used to make progress
  unless a separate owner review explicitly approves a stopped-family override.
- Governance reports classify every non-stopped family as `add_data` with no
  paper portfolio candidate.
- The rollout gates still require at least 30 paper observations, at least 3
  walk-forward splits, positive cost-adjusted expectancy, acceptable failure
  rate, and preserved evidence packages before tiny-live review can be
  considered.

## External Evidence

Smart Search evidence is saved under:

`var/smart-search-evidence/2026-06-08-completion-roadmap/`

Evidence used for this design:

- `02-binance-funding.md`: Binance USD-M funding history documents
  `GET /fapi/v1/fundingRate`, optional `symbol`, `startTime`, `endTime`, and
  `limit`, with `limit` default 100 and maximum 1000. The endpoint shares a
  documented 500 requests per 5 minutes per IP limit with funding-info calls.
- `03-binance-open-interest.md`: Binance USD-M current open-interest endpoint
  `GET /fapi/v1/openInterest` is public, requires `symbol`, has request weight
  1, and returns `openInterest`, `symbol`, and `time`.
- `05-dexscreener-api.md`: DexScreener's public API reference documents pair
  discovery/search endpoints and rate limits. These remain discovery/watchlist
  inputs unless enough local snapshots exist for historical evidence.
- `04-ccxt-docs.md`: the CCXT docs fetch failed and produced an empty local
  artifact. Any CCXT open-interest-history support claim must therefore be
  proven by local source-probe or ingestion output before it is treated as
  qualified evidence.

Design implication: current public API evidence supports funding and
open-interest reachability as a source-probe and ingestion target, but the
campaign must prove the exact CCXT exchange method and symbol mapping in the
local environment before relying on it for validation.

## Local Feasibility

The repository already has the main building blocks needed for the recovery
campaign:

- `src/crypto_alpha_agent/pipeline/evidence_runner.py` runs CCXT OHLCV and
  funding ingestion, then conditionally runs CCXT open-interest ingestion when
  an active strategy family declares `open_interest` as a required record type.
- `src/crypto_alpha_agent/strategy/registry.py` declares
  `funding_open_interest_crowding` as requiring `market_candle`,
  `funding_rate`, and `open_interest`.
- `src/crypto_alpha_agent/data/ingestion.py` has
  `ingest_ccxt_open_interest_history()`.
- `src/crypto_alpha_agent/data/source_probe.py` has probe targets for public
  open-interest sources, including `binance_usdm_open_interest_history`.
- `src/crypto_alpha_agent/strategy/funding_oi_crowding.py` validates funding
  plus open-interest crowding and fails closed for missing, duplicate, stale,
  unsupported, or non-expanding open-interest evidence.
- `docs/runbook.md` already documents that `funding_open_interest_crowding`
  requires OHLCV candles, funding-rate history, and open-interest history.
- `var/reports/weekly/2026-W22-governance.md` and
  `var/reports/monthly/2026-06-governance.md` show the current active-family
  gap as `add_data`, not as owner-decision readiness.

The implementation plan should therefore start with controlled operations and
verification over existing code. Product-code changes are allowed only if a
specific recovery step proves a repository defect that blocks the approved
campaign.

## Remaining Roadmap

### Phase A: Spec And Plan Closeout

Write this design spec, self-review it, commit it, and then write the
implementation plan after owner review. The plan must be specific enough to
execute one campaign round under the Goal contract, including source evidence,
local feasibility checks, verification commands, and state/report updates.

### Phase B: Open-Interest Source Qualification

Qualify the open-interest route before treating OI as strategy evidence:

- Run a proxy-aware source probe for `binance_usdm_open_interest_history`.
- Run a small CCXT open-interest-history ingestion for the same symbol shape
  the strategy family will use.
- Inspect stored records for record type `open_interest`, positive values,
  timestamps, symbol, venue, and duplicate/stale issues.
- If the source is unreachable, unsupported, or unparseable, record a
  documented blocker instead of changing strategy logic to ignore OI.

### Phase C: Active-Family Evidence Recovery

Run a controlled `evidence-run` for active families only:

- First target: `funding_open_interest_crowding`.
- Second target, if the first is blocked by data shape or no qualified trades:
  `funding_mean_reversion_after_extreme`.
- Do not include `funding_extremity_price_confirmation` unless the owner
  separately approves a stopped-family review and override.
- Require the run manifest, daily report, validation ledger, paper ledger,
  memory updates, and source-health records to agree.

The desired outcome is not "profitable" by assertion. The desired outcome is
one of these explicit evidence states:

- validation evidence written and paper outcomes written;
- validation evidence written but paper blocked with stable reason codes;
- source or data-quality blocker written with stable reason codes;
- strategy rejected or marked for redesign with evidence references.

### Phase D: Evidence Accumulation Or Redesign Decision

If an active family produces clean validation evidence and paper outcomes,
continue accumulating out-of-sample observations toward the 30/60/90 evidence
targets. If no active family produces usable evidence, stop the campaign round
and write a redesign decision instead of running repeated no-op evidence runs.

The decision boundary is:

- continue collecting only when new validation or paper evidence exists;
- add data when source coverage is the reason validation cannot run;
- redesign validator when data exists but validation/paper logic yields only
  blocked or structurally unusable outcomes;
- stop when repeated outcomes show degraded expectancy or excessive blocked
  runs;
- owner review only when rollout evidence actually reaches the documented
  thresholds.

### Phase E: Documentation, Reports, And Goal State

At the end of each campaign round:

- Update `docs/goals/project-completion-state.md` with exact current evidence,
  commands, blockers, and next action.
- Update `docs/roadmap.md` only when the public roadmap changes.
- Write a phase/campaign report under `docs/goals/phase-reports/`.
- Keep local generated artifacts under `var/` and out of git.
- Preserve `uses_real_capital=false` and `live_order_routing=false` in reports
  and artifacts.

## Success Criteria

The campaign is successful only if current-state evidence proves one of these
outcomes:

1. At least one active strategy family writes validation evidence and paper
   outcomes from qualified public data, with reports and governance updated.
2. A concrete blocker is documented with source-health, data-quality,
   validation, paper, or LLM-runtime evidence, and the next safe action is
   explicit.

Longer-term project completion remains stricter than this campaign. The project
does not satisfy tiny-live readiness until a narrow low-capital family has the
required paper sample size, walk-forward evidence, positive cost-adjusted
expectancy, acceptable failure rate, preserved evidence package, risk controls,
and human approval. This campaign can move the system toward that state, but it
cannot redefine completion around a single green command.

## Non-Goals

- No live execution.
- No wallet private keys, seed phrases, signing keys, or exchange live order
  routing.
- No automatic promotion from research or paper evidence to live execution.
- No MEV, mempool, bridge-race, flash-loan, sub-second arbitrage, premium RPC,
  private infrastructure, or high-capital strategy path.
- No stopped-family override for `funding_extremity_price_confirmation` in
  this campaign.
- No Dune or TheGraph dependency unless local credentials and source probes are
  deliberately configured outside git.
- No claim that historical bootstrap or LLM narrative is profit proof.

## Testing And Verification Strategy

The implementation plan must include fresh verification before any completion
claim:

- `git status --short --branch` before and after changes.
- Smart Search evidence path and any failed external fetches recorded.
- Open-interest source probe or ingestion output inspected before strategy use.
- Focused tests for any product-code defect fixed during the campaign.
- `uv run --extra dev pytest -q -m 'not llm_integration'` when product code is
  changed.
- Real LLM health or focused integration checks when product commands depend on
  the configured LLM route.
- `uv run --extra dev ruff check .` and `git diff --check` before commit when
  files are changed.
- Staged secret scan before every commit:
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`.

Generated runtime artifacts must not be staged. The only expected committed
artifacts for the initial design round are this spec and any later approved
plan/state/report documentation.
