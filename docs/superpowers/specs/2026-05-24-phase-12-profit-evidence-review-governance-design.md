# Phase 12 Profit Evidence Review And Portfolio Governance Design

## Goal

Turn accumulated validation, paper, source-health, cost, memory, and stopped-family evidence into explicit profit/no-profit governance artifacts without adding live execution, wallet access, exchange order routing, or real-capital allocation.

## Context

Phase 12 follows the roadmap deliverables for profit evidence review and portfolio governance. The existing project already has daily and weekly evidence reports, paper outcome ledgers, validation ledgers, memory-backed degradation markers, source-health records, execution-realism cost fields, and stopped-family enforcement in the planner, runner, research loop, and scheduler.

Smart Search evidence was collected under `/tmp/smart-search-evidence/20260524-phase12-governance/`:

- `smart-search doctor --format json` returned `ok=true`.
- `smart-search deep "Low-capital crypto strategy governance scorecard metrics profit review stopped-family ledger portfolio selector monthly owner review decision records" --format json` produced a deep-research plan.
- `01-search.json` supported using expectancy, hit rate, maximum drawdown, walk-forward stability, and robustness as strategy review metrics.
- `02-search.json` supported structured portfolio review through scorecards, decision records, and stop/continue actions.
- Fetch attempts for several candidate pages returned empty content from the fetch provider; fetched-page evidence is therefore unavailable for those claims and the implementation keeps the external findings as design context rather than product claims.

Local feasibility was verified with `uv run --extra dev pytest tests/test_evidence_reports.py -q`, which passed with 15 tests. A read-only explorer subagent confirmed that `src/crypto_alpha_agent/pipeline/governance_reports.py` should host the new governance models/builders, with rendering in `pipeline/markdown.py` and CLI wiring in `cli.py`.

## Approach

Use a new `pipeline/governance_reports.py` module for Phase 12. It will reuse `build_weekly_evidence_report()`, `ValidationEvidenceLedger`, `PaperOutcomeLedger`, `MemoryStore`, `ResearchDataStore`, `build_data_quality_report()`, and `aggregate_paper_evidence()` rather than expanding the existing evidence report module into a catch-all.

The module will produce one deterministic `ProfitGovernanceReport` with four artifact sections:

- Weekly family scoreboard: one row per active or stopped strategy family, with sample size, net PnL, cost-adjusted expectancy, max drawdown, hit rate, failure rate, source-health quality, stale-signal rate, walk-forward stability, and current governance action.
- Profit review: one row per family answering whether evidence is improving, whether more data is worthwhile, whether the family should stop, and whether it is near an owner decision point.
- Stopped-family ledger: memory-derived rows with reason, date, evidence refs, and revival conditions.
- Paper-only portfolio selector and monthly owner review: ranked future paper observation candidates plus a monthly owner-facing comparison against doing nothing, fees, opportunity cost, and the owner's low-capital constraints.

No LLM summary mode is added for this phase. The monthly owner review remains deterministic and source-backed by local evidence only.

## Governance Decisions

The report emits one of these actions per family:

- `keep_collecting`: evidence is non-degraded and still below a meaningful sample target.
- `stop`: stopped/degraded memory exists or evidence is negative after costs.
- `redesign_validator`: blocked outcomes, failed walk-forward evidence, or weak validation suggest the validator is not usable yet.
- `add_data`: data quality or source-health evidence is weak or missing.
- `owner_decision_review`: sample size, validation, and paper evidence are strong enough for owner review, while still carrying `uses_real_capital=false` and `live_order_routing=false`.

Actions are deterministic and based on explicit evidence gates. Narrative text cannot promote a family.

## Data Flow

1. Load validation evidence, paper outcomes, memory records, source records, and the existing weekly report.
2. Aggregate paper evidence into family packages and validation evidence into family stability metrics.
3. Build source-health quality from the local data-quality report.
4. Derive stopped-family ledger rows from memory records already used by `load_stopped_strategy_families()`.
5. Score and rank paper-only portfolio candidates; stopped families are excluded from the active portfolio selector and recorded with exclusion reasons.
6. Render a Markdown governance artifact and return the same data in CLI JSON.

## Error Handling And Safety

Missing ledgers produce empty sections rather than exceptions. Invalid finite values are rejected by strict Pydantic models. The report always exposes `uses_real_capital=false` and `live_order_routing=false`. Stopped families remain blocked by existing runner/planner enforcement; the governance layer only reports and ranks paper observations.

## Tests

Add focused tests in `tests/test_governance_reports.py` for:

- Scoreboard metrics from seeded validation, paper outcomes, source health, and memory.
- Profit review action classification.
- Stopped-family ledger date, reasons, evidence refs, and revival conditions.
- Paper-only portfolio ranking and exclusion of stopped families.
- Monthly owner review comparison against doing nothing, fees, opportunity cost, and owner capital constraints.
- CLI Markdown output and safety flags.

Update documentation contract tests so `governance-report`, `scoreboard`, `stopped-family ledger`, `paper-only portfolio selector`, and `monthly owner review` are documented.

## Scope Exclusions

This phase does not add live execution, wallet access, exchange order routing, strategy validators, new data sources, date-windowed SQL APIs, first-class SQLite governance tables, portfolio allocation of real capital, or LLM narrative promotion.

