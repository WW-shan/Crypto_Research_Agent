# Phase 8 Data Depth And Quality Expansion Completion Report

Date: 2026-05-24

Commit reference: Phase 8 completion commit
`feat: add source qualification workflow`.

## Objective

Complete Phase 8 by adding public source qualification, proxy-aware
source-health evidence, typed open-interest depth, symbol normalization, and
data-quality checks before Phase 9 validator expansion. The round must preserve
no wallet keys, no live order routing, no live execution, no wallet-key access,
no order routing, no live capital, and `live_execution_enabled=false`.

## External Evidence

Smart Search evidence was written to the phase-specific
`SMART_SEARCH_EVIDENCE_DIR` local evidence workspace during execution.

Source-backed findings used:

- Binance USD-M open-interest history is public at
  `GET /futures/data/openInterestHist`, has periods from `5m` through `1d`,
  and is limited to recent history.
- Binance premium-index klines, basis, and long/short ratio endpoints are
  public market-data candidates but remain source-probe targets until typed
  persistence and quality checks are added.
- Bybit V5 exposes public open-interest history and funding history.
- OKX V5 exposes public open-interest and funding surfaces.
- DexScreener documents pair and token endpoints with documented public rate
  limits.
- DefiLlama exposes free TVL/protocol/yield surfaces, while broader
  fundamentals may need source-specific qualification.
- Dune query result and execution APIs require a local API key and return rows
  plus metadata.
- The Graph is read-only GraphQL querying against subgraph schemas; `_meta`
  and schema checks belong in query qualification.
- CCXT documents `fetchOpenInterestHistory` where an exchange supports it.

## Local Feasibility

- `SourceRecord` and the SQLite store could persist a new typed
  `open_interest` record without migration.
- Existing CCXT collector and ingestion patterns could add one public market
  data feed while preserving `uses_real_capital=false` and
  `live_order_routing=false`.
- Existing data-quality reports could be extended with open-interest semantic
  keys, continuity checks, stale checks, value checks, and timestamp-skew
  checks.
- Existing source-health payloads could add route, provider status, parse
  status, HTTP status, typed record count, schema version, and blocked reason.
- Existing documentation contract tests could enforce source-probe examples,
  the source coverage matrix, the query catalog, and hard safety boundaries.

## Implemented

- Added `src/crypto_alpha_agent/data/symbols.py` with conservative exchange
  and DEX identifier normalization.
- Added `OpenInterestRecord` and the `open_interest` record type.
- Added data-quality reason codes and checks for open-interest gaps,
  non-positive values, stale rows, timestamp skew, and duplicate semantic rows.
- Added `CcxtResearchCollector.fetch_open_interest_history`.
- Added `ingest_ccxt_open_interest_history` and CLI routing for
  `--ccxt-feed open-interest-history`.
- Added `src/crypto_alpha_agent/data/source_probe.py` and the `source-probe`
  CLI with direct, proxy, blocked, and unavailable route evidence.
- Added source-health parsing compatibility for route/status fields and
  malformed source-health payloads.
- Added `docs/source-coverage-matrix.md` and `docs/source-query-catalog.md`.
- Updated README, runbook, asset assessment, roadmap, documentation contracts,
  project state, and this report.

## Rejected Or Blocked Candidates

- Binance premium-index klines, basis, long/short ratio, Bybit direct open
  interest, OKX open interest, DefiLlama fundamentals, Dune, and The Graph are
  probe-qualified candidates only in this phase. They do not get typed
  validator evidence until a future plan adds typed models and quality checks.
- Dune remains blocked with `credential_required` unless a local redacted
  credential marker is configured. Real keys must remain outside git and
  outside docs.
- A one-shot probe may reach `ResearchUsable`; it cannot assign
  `ProductionResearchSource` without repeated canary evidence.

## Subagents

- Documentation audit explorer: checked roadmap, state, runbook, completion
  report, source matrix/catalog, and documentation contract risks.
- Code audit explorer: checked low-risk implementation seams for source-probe,
  open-interest storage, route-aware source health, and compatibility.
- Implementation worker: implemented symbol normalization and its focused
  tests.
- Review pass 1: found Important source-probe, proxy-route, malformed
  source-health, and local-path issues; all were fixed and re-reviewed.
- Review pass 2: found Important research-loop record-type and malformed
  open-interest timestamp issues; all were fixed and re-reviewed with no
  Critical or Important findings remaining.

## Verification

- Focused pre-review verification:
  `uv run --extra dev pytest tests/test_source_probe.py tests/test_symbol_normalization.py tests/test_ccxt_collector.py tests/test_ccxt_ingestion_service.py tests/test_data_quality_reports.py tests/test_data_models_store.py tests/test_documentation_contract.py tests/test_expansion_preparation.py -q`
  passed with 61 tests.
- Full verification:
  `uv run --extra dev pytest -q` passed with 832 tests.
- `uv run --extra dev ruff check .` passed.
- `git diff --check` passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests`
  returned `[]`.
- `git diff --cached --check` passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  returned `[]`.
- Final commit message: `feat: add source qualification workflow`.

## Safety

- `uses_real_capital=false`
- `live_order_routing=false`
- `live_execution_enabled=false`
- No wallet keys, exchange live order routing, MEV, premium RPC, speed-edge
  execution, wallet-key access, order routing, live execution, live capital, or
  real-capital deployment were added.

## Next Phase

Phase 9 should expand deterministic strategy validators only after each
candidate maps required fields to Phase 8 typed records or qualified source
coverage. Missing fields should produce stable blocked reasons, not validator
promotion.
