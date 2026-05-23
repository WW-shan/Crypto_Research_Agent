# Phase 12 Profit Evidence Review And Portfolio Governance Completion Report

## Summary

- Phase: Phase 12 Profit Evidence Review And Portfolio Governance
- Date: 2026-05-24
- Commit: `e89e008 feat: add profit governance report`
- Owner objective: turn accumulated evidence into explicit profit/no-profit
  governance decisions without live capital.
- Work type: implementation, tests, documentation, and review.

Phase 12 adds a deterministic `governance-report` command and
`pipeline/governance_reports.py`. The report reads existing local evidence and
produces a weekly family scoreboard, profit review, stopped-family ledger,
paper-only portfolio selector, and monthly owner review. It keeps
`uses_real_capital=false` and `live_order_routing=false`.

## Smart Search Evidence

Commands and evidence:

- `smart-search doctor --format json`: configuration returned `ok=true`.
- `smart-search deep "Low-capital crypto strategy governance scorecard metrics profit review stopped-family ledger portfolio selector monthly owner review decision records" --format json`:
  generated the deep-research plan.
- `smart-search search "trading strategy performance metrics expectancy hit rate max drawdown walk-forward robustness" --validation balanced --extra-sources 3 --format json --output "/tmp/smart-search-evidence/20260524-phase12-governance/01-search.json"`:
  supported expectancy, hit rate, max drawdown, walk-forward stability, and
  robustness as strategy review metrics.
- `smart-search search "portfolio review decision record stop continue add data drawdown strategy scorecard" --validation balanced --extra-sources 3 --format json --output "/tmp/smart-search-evidence/20260524-phase12-governance/02-search.json"`:
  supported scorecards, decision records, and stop/continue review patterns.

Fetch attempts for several candidate URLs returned empty extraction through the
configured fetch provider. Those external findings were used only as design
context; the product behavior is based on local evidence and tests.

## Local Feasibility

Files and seams inspected:

- `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- `src/crypto_alpha_agent/evidence/paper.py`
- `src/crypto_alpha_agent/evidence/models.py`
- `src/crypto_alpha_agent/evidence/ledger.py`
- `src/crypto_alpha_agent/evidence/validation_ledger.py`
- `src/crypto_alpha_agent/data/quality.py`
- `src/crypto_alpha_agent/memory/store.py`
- `src/crypto_alpha_agent/strategy/registry.py`
- `src/crypto_alpha_agent/pipeline/markdown.py`
- `src/crypto_alpha_agent/cli.py`
- `tests/test_evidence_reports.py`
- `tests/test_complete_evidence_system.py`
- `tests/test_documentation_contract.py`

Feasibility result:

- Validation evidence, paper outcomes, source-health records, memory, and
  registered default families were already available locally.
- Paper packages already exposed net PnL, gross PnL, fees, slippage, stale
  signal count, fill counts, hit rate, failure rate, and drawdown summaries.
- Source-health quality could be derived from `build_data_quality_report()`.
- Stopped-family state could reuse memory records without a new SQLite schema.
- Monthly owner review could be deterministic without changing the LLM summary
  contract.

## Substep Validation

- Baseline test before implementation:
  `uv run --extra dev pytest tests/test_evidence_reports.py -q` passed with
  15 tests.
- TDD red check:
  `uv run --extra dev pytest tests/test_governance_reports.py tests/test_documentation_contract.py -q`
  failed first because `crypto_alpha_agent.pipeline.governance_reports` did
  not exist.
- Focused regression after implementation and review fixes:
  `uv run --extra dev pytest tests/test_governance_reports.py tests/test_evidence_reports.py tests/test_documentation_contract.py tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system -q`
  passed with 28 tests.
- Changed-file lint:
  `uv run ruff check src/crypto_alpha_agent/pipeline/governance_reports.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_governance_reports.py tests/test_complete_evidence_system.py tests/test_documentation_contract.py`
  passed.

Rejected candidates:

- No new SQLite governance ledger was added. Memory-backed stopped-family
  records already support the current stopped-family enforcement path.
- No LLM monthly-summary mode was added. The Phase 12 governance artifact is
  deterministic and must not advance a family because of narrative text.
- No live execution, wallet access, exchange order routing, or real-capital
  portfolio allocation was added.

## Files Changed

- Added `src/crypto_alpha_agent/pipeline/governance_reports.py`
- Added `tests/test_governance_reports.py`
- Added `docs/superpowers/specs/2026-05-24-phase-12-profit-evidence-review-governance-design.md`
- Added `docs/superpowers/plans/2026-05-24-phase-12-profit-evidence-review-governance.md`
- Added this phase report
- Modified `src/crypto_alpha_agent/pipeline/markdown.py`
- Modified `src/crypto_alpha_agent/cli.py`
- Modified `tests/test_complete_evidence_system.py`
- Modified `tests/test_documentation_contract.py`
- Modified `README.md`
- Modified `docs/runbook.md`
- Modified `docs/roadmap.md`
- Modified `docs/project-asset-assessment.md`
- Modified `docs/goals/project-completion-state.md`

## Subagents

- Sartre: read-only codebase audit for Phase 12 seams. Recommended a new
  `pipeline/governance_reports.py` module, Markdown rendering in
  `pipeline/markdown.py`, and CLI wiring in `cli.py`.
- Fermat: read-only spec compliance review. Found Important gaps for state
  sync, registered no-evidence families, and fresh stop decisions missing
  ledger rows.
- Copernicus: read-only code quality and safety review. Found Important gaps
  for paper portfolio notional caps and fresh stop decisions missing ledger
  rows.

All Critical or Important review findings were addressed with regression tests.
Re-review reported no Critical or Important findings remaining.

## Review Findings And Fixes

Important findings fixed:

- Registered default families with no accumulated evidence were omitted.
  Fix: `build_profit_governance_report()` now includes every family from
  `default_strategy_registry()`, so no-evidence families get `add_data`.
- Current negative evidence could return `stop` without a stopped-family ledger
  row.
  Fix: stopped-family ledger rows are now derived from both memory markers and
  current scoreboard stop decisions.
- Paper portfolio notional was capped per selected family instead of across the
  paper-only selector.
  Fix: the selector splits `min(25, current_capital_usd)` across selected
  families.
- Governance state and phase report were missing while the roadmap marked
  Phase 12 complete.
  Fix: this report and the project completion state were added.

Minor finding noted:

- The selector currently shows exclusion fields only on selected rows. This is
  acceptable for Phase 12 because excluded families remain visible in the
  scoreboard and profit review with their governance actions and reason codes.

## Verification Status

Current verified commands:

- `uv run --extra dev pytest tests/test_governance_reports.py tests/test_evidence_reports.py tests/test_documentation_contract.py tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system -q`
  passed with 28 tests.
- `uv run ruff check src/crypto_alpha_agent/pipeline/governance_reports.py src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_governance_reports.py tests/test_complete_evidence_system.py tests/test_documentation_contract.py`
  passed.

Final verification:

- `uv run --extra dev pytest -q` passed with 898 tests, 4 skipped, and 2
  dependency warnings.
- `uv run ruff check` passed.
- `git diff --check` passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --path src --path tests --path docs --path README.md --fail-on-empty-with-untracked`
  returned `[]`.

Pending before completion:

- Commit and push.

## Secret Safety

No `.env`, database, memory, report artifact, cache, local Smart Search evidence
file, or generated local artifact should be staged. The path secret scan over
`src`, `tests`, `docs`, and `README.md` returned `[]`.
