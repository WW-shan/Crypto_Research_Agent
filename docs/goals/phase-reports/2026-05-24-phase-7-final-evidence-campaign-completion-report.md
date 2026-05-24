# Phase 7 Final Evidence Campaign Completion Report

## Summary

- Phase: Phase 7 Final Evidence Campaign After Factory Buildout
- Date: 2026-05-24
- Commit: `feat: add historical bootstrap campaign`
- Owner objective: bootstrap historical evidence after Phases 8-12, then set
  future out-of-sample paper evidence targets without enabling live trading.
- Work type: implementation, tests, documentation, and review.

Phase 7 adds a safe `historical-bootstrap` command and
`pipeline/historical_bootstrap.py`. The command evaluates historical
date-windowed records, renders a historical bootstrap report, writes JSON and
manifest artifacts, records source collection/probe status, and sets forward
30/60/90 evidence targets. Historical validation and paper outcomes are
report-local in this path; they do not mutate the forward validation ledger,
forward paper outcome ledger, or stopped-family memory.
Re-review found no remaining Critical or Important issues after the fixes.

## Smart Search Evidence

Evidence path:

- `/tmp/smart-search-evidence/20260524-phase7-evidence-campaign/`

Commands and artifacts:

- `smart-search doctor --format json`: configuration returned `ok=true`.
- `smart-search deep "Phase 7 historical bootstrap out-of-sample paper trading evidence campaign crypto strategy validation public data"`:
  generated `00-deep-plan.json`.
- `01-search.json`: public-data and methodology search evidence.
- Fetched source notes:
  - `02-fetch-binance-public-data.md`
  - `03-fetch-binance-funding-rate-history.md`
  - `04-fetch-binance-open-interest-statistics.md`
  - `05-fetch-out-of-sample-testing.md`
  - `06-fetch-binance-basis.md`
  - `07-fetch-binance-long-short-ratio.md`
  - `08-fetch-binance-kline.md`
  - `09-fetch-paper-trading-forward-testing.md`

External findings used:

- Binance Public Data supports reproducible public historical files and
  checksums for candles and trades.
- Binance USD-M funding history, open-interest history, basis, and long/short
  ratio endpoints are public research inputs, with endpoint-specific history
  and limit constraints.
- Out-of-sample and forward paper testing reduce overfit risk but do not prove
  future profit by themselves.
- Forward evidence targets must remain separate from historical bootstrap
  results.

## Local Feasibility

Files and seams inspected:

- `src/crypto_alpha_agent/data/store.py`
- `src/crypto_alpha_agent/data/ingestion.py`
- `src/crypto_alpha_agent/data/source_probe.py`
- `src/crypto_alpha_agent/pipeline/research_loop.py`
- `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- `src/crypto_alpha_agent/pipeline/governance_reports.py`
- `src/crypto_alpha_agent/pipeline/markdown.py`
- `src/crypto_alpha_agent/cli.py`
- `src/crypto_alpha_agent/strategy/registry.py`
- evidence and validation ledger modules
- docs and documentation contract tests

Feasibility result:

- The repository already had safe daily `evidence-run` operations, manifests,
  failed markers, source-health rows, governance classification, three
  paper-capable families, and three research-only watchlists.
- The main blocker was the lack of first-class historical bootstrap workflow
  and date-window filtering for stored validation and paper simulation.
- Bootstrap needed to avoid contaminating the forward evidence ledgers and
  stopped-family memory because future out-of-sample observations are a
  separate evidence target.

## Substep Validation

Baseline before implementation:

- `uv run --extra dev pytest tests/test_evidence_runner.py::test_evidence_runner_executes_complete_research_milestone tests/test_governance_reports.py::test_governance_report_marks_registered_no_evidence_families_add_data tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q`
  passed with 3 tests.

TDD red/green:

- Date-window tests were added for store loading, research-loop validation, and
  paper simulation. They first failed on missing `observed_at_start` and
  `observed_at_end` support, then passed after implementation.
- Historical bootstrap tests were added. They first failed because
  `crypto_alpha_agent.pipeline.historical_bootstrap` did not exist, then passed
  after the builder, Markdown renderer, CLI, and source-probe target were
  implemented.
- Review fixes added tests for non-persisted paper reports, non-mutating
  historical bootstrap, network-enabled source failure status, strict
  date-window parsing, unknown strategy families, and ingestion window
  filtering.

Rejected or blocked candidates:

- No live execution, wallet access, order routing, MEV, premium RPC, or
  real-capital path was added.
- Historical bootstrap does not write historical outcomes to the forward paper
  ledger. The report still shows historical paper outcomes, but forward
  30/60/90 targets count only existing forward ledger observations.
- Historical bootstrap does not persist degradation decisions to memory.
- Historical source collection over monthly public archives filters records to
  the requested UTC window before writing to SQLite.

## Files Changed

- Added `src/crypto_alpha_agent/pipeline/historical_bootstrap.py`
- Added `tests/test_historical_bootstrap.py`
- Added `docs/goals/phase-reports/2026-05-24-phase-7-final-evidence-campaign-completion-report.md`
- Added `docs/superpowers/plans/2026-05-24-phase-7-final-evidence-campaign.md`
- Modified `src/crypto_alpha_agent/cli.py`
- Modified `src/crypto_alpha_agent/data/ingestion.py`
- Modified `src/crypto_alpha_agent/data/source_probe.py`
- Modified `src/crypto_alpha_agent/data/store.py`
- Modified `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- Modified `src/crypto_alpha_agent/pipeline/markdown.py`
- Modified `src/crypto_alpha_agent/pipeline/paper_sim_loop.py`
- Modified `src/crypto_alpha_agent/pipeline/research_loop.py`
- Modified tests for store, ingestion, paper simulation, source probes, and
  documentation contracts.
- Modified `README.md`, `docs/runbook.md`, `docs/roadmap.md`,
  `docs/project-asset-assessment.md`, `docs/source-coverage-matrix.md`,
  `docs/source-query-catalog.md`, and `docs/goals/project-completion-state.md`.

## Subagents

- Helmholtz: initial Phase 7 audit. Found that the safe evidence factory was
  mostly ready and identified the missing first-class historical bootstrap and
  date-window filtering.
- Socrates: code/safety review. Found Important issues for historical
  contamination of forward ledgers, stopped-family memory mutation, successful
  manifests despite failed network source steps, and incomplete window-bound
  source collection.
- Huygens: spec/docs review. Found Important issues for historical outcomes
  counted as out-of-sample progress, unsynchronized state/report docs, future
  example windows, and source catalog fields that overstated probe validation.

All initial Important findings were addressed with code, tests, or docs.
Re-review reported no remaining Critical or Important findings.

## Review Fixes

Important fixes:

- Added `persist_validation_evidence=False` support in `research-loop` and
  `persist_outcomes=False` support in `paper-sim-loop`, then used both from
  `historical-bootstrap`.
- Added `persist_degradation=False` support in weekly evidence report building
  and used it from `historical-bootstrap`.
- Changed Phase 7 report Markdown to label forward sample progress and forward
  30/60/90 targets separately from historical strategy results.
- Made network-enabled source failures mark the bootstrap manifest failed and
  the CLI exit nonzero.
- Added ingestion-level observed-window filtering for Binance Public Data,
  CCXT funding history, and CCXT open-interest history.
- Split network source collection into month segments for historical windows.
- Replaced future-ended example windows with fully past windows as of
  2026-05-24.
- Aligned `docs/source-query-catalog.md` expected fields with the implemented
  `source-probe` target contracts.

## Verification Status

Current verified commands:

- Focused pre-implementation baseline: 3 tests passed.
- Date-window focused tests: 6 tests passed.
- Historical bootstrap focused tests: 5 tests passed after review fixes.
- Ingestion/bootstrap/paper/documentation focused slice:
  `uv run --extra dev pytest tests/test_historical_bootstrap.py tests/test_binance_public_pipeline_ingestion.py tests/test_ccxt_ingestion_service.py tests/test_paper_sim_loop.py tests/test_research_loop_strategy_validation.py::test_research_loop_filters_validation_records_by_observed_window tests/test_documentation_contract.py -q`
  passed with 59 tests.
- Changed-file lint:
  `uv run ruff check src/crypto_alpha_agent/data/ingestion.py src/crypto_alpha_agent/pipeline/historical_bootstrap.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/pipeline/paper_sim_loop.py src/crypto_alpha_agent/pipeline/research_loop.py src/crypto_alpha_agent/cli.py tests/test_historical_bootstrap.py tests/test_binance_public_pipeline_ingestion.py tests/test_ccxt_ingestion_service.py tests/test_paper_sim_loop.py tests/test_documentation_contract.py`
  passed.
- Full verification:
  `uv run --extra dev pytest -q` passed with 912 tests, 4 skipped, and 2
  warnings.
  `uv run --extra dev ruff check .` passed.
  `git diff --check` passed.

Pending before completion:

- Commit and push.

## Secret Safety

No `.env`, database, memory, report artifact, cache, local Smart Search
evidence file, or generated local artifact should be staged. Phase 7 docs use
variable names and example artifact paths only. `git diff --cached --check`,
`git diff --cached --name-only`, and
`git diff --cached --no-ext-diff --unified=0` were inspected. The staged secret
scan command
`uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
returned `[]`.

## Remaining Gaps

Phase 7 creates the bootstrap/reporting workflow and keeps historical evidence
separate from future out-of-sample progress. The remaining roadmap gap is
Phase 13: continuous read-only review of generated reports, evidence packages,
AI memos, scoreboards, stopped-family ledgers, and decision records.
