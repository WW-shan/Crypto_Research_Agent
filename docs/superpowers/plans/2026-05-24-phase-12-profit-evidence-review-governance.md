# Phase 12 Profit Evidence Review And Portfolio Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic profit/no-profit governance artifacts that rank, stop, or continue strategy families from accumulated local evidence.

**Architecture:** Add a focused `pipeline/governance_reports.py` module that reads existing validation, paper, source-health, and memory evidence and produces one strict `ProfitGovernanceReport`. Render it in `pipeline/markdown.py` and expose it through a new `governance-report` CLI command. Keep existing `evidence-report` behavior intact.

**Tech Stack:** Python 3.12, Pydantic strict models, SQLite ledgers, JSONL memory, argparse CLI, pytest, Ruff.

---

## Evidence And Feasibility

Smart Search evidence:

- `smart-search doctor --format json`: configuration OK.
- `smart-search deep "Low-capital crypto strategy governance scorecard metrics profit review stopped-family ledger portfolio selector monthly owner review decision records" --format json`: deep-research plan generated.
- `/tmp/smart-search-evidence/20260524-phase12-governance/01-search.json`: supports expectancy, hit rate, maximum drawdown, walk-forward stability, and robustness as strategy metrics.
- `/tmp/smart-search-evidence/20260524-phase12-governance/02-search.json`: supports scorecards, decision records, and stop/continue review patterns.
- Fetch attempts for external pages returned `network_error` with empty extraction; no product code will depend on those pages.

Local feasibility:

- Baseline command `uv run --extra dev pytest tests/test_evidence_reports.py -q` passed with 15 tests.
- Existing seams:
  - `src/crypto_alpha_agent/pipeline/evidence_reports.py` already aggregates daily/weekly evidence and persists degradation markers.
  - `src/crypto_alpha_agent/evidence/paper.py` already exposes cost, stale-signal, fill, and paper PnL package metrics.
  - `src/crypto_alpha_agent/evidence/models.py` has validation walk-forward and paper execution-realism fields.
  - `src/crypto_alpha_agent/data/quality.py` can derive source-health quality.
  - `src/crypto_alpha_agent/memory/store.py` preserves stopped and rejected-family records.
  - `src/crypto_alpha_agent/cli.py` has established report command patterns.

## File Structure

- Create `src/crypto_alpha_agent/pipeline/governance_reports.py`: strict report models and deterministic builders.
- Modify `src/crypto_alpha_agent/pipeline/markdown.py`: add `render_profit_governance_report_markdown()`.
- Modify `src/crypto_alpha_agent/cli.py`: add `governance-report --db --memory --out --current-capital-usd`.
- Create `tests/test_governance_reports.py`: focused tests for report models, metrics, Markdown, and CLI.
- Modify `tests/test_documentation_contract.py`: add CLI example and required documentation terms.
- Modify `README.md` and `docs/runbook.md`: document the governance command and review workflow.
- Modify `docs/roadmap.md`, `docs/project-asset-assessment.md`, `docs/goals/project-completion-state.md`: mark Phase 12 state.
- Create `docs/goals/phase-reports/2026-05-24-phase-12-profit-evidence-review-governance-completion-report.md`: final report after verification.

## Task 1: Governance Tests

**Files:**
- Create: `tests/test_governance_reports.py`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing tests for the report builder and CLI**

Create `tests/test_governance_reports.py` with fixtures that seed:

```python
ValidationEvidenceLedger(db_path).upsert_evidence([
    _validation(
        "funding_extremity_price_confirmation",
        run_id="validation-good",
        trade_count=32,
        fee_adjusted_expectancy=0.012,
        slippage_adjusted_expectancy=0.009,
        max_drawdown=0.08,
        walk_forward_split_count=4,
        walk_forward_pass_rate=0.75,
        approved=True,
    ),
    _validation(
        "funding_mean_reversion_after_extreme",
        run_id="validation-weak",
        trade_count=12,
        fee_adjusted_expectancy=-0.003,
        slippage_adjusted_expectancy=-0.004,
        max_drawdown=0.24,
        walk_forward_split_count=2,
        walk_forward_pass_rate=0.25,
        approved=False,
        blocked_reasons=("insufficient_walk_forward",),
    ),
])
PaperOutcomeLedger(db_path).upsert_outcomes([
    _paper("funding_extremity_price_confirmation", "paper-good-1", status="closed", net_pnl_usd=2.5, gross_pnl_usd=3.5, fees_usd=0.5, slippage_usd=0.5),
    _paper("funding_extremity_price_confirmation", "paper-good-2", status="closed", net_pnl_usd=1.5, gross_pnl_usd=2.0, fees_usd=0.3, slippage_usd=0.2),
    _paper("funding_mean_reversion_after_extreme", "paper-weak-1", status="blocked", net_pnl_usd=0.0, failure_reasons=("stale_signal",)),
])
MemoryStore(memory_path).upsert(
    MemoryRecord(
        record_id="degraded:funding_mean_reversion_after_extreme",
        opportunity={"strategy_family": "funding_mean_reversion_after_extreme"},
        rejected_reasons=["degraded_expectancy"],
        tags=["funding_mean_reversion_after_extreme", "degraded_expectancy"],
    )
)
```

Assert that:

```python
report = build_profit_governance_report(
    db_path=db_path,
    memory_path=memory_path,
    current_capital_usd=300.0,
)
rows = {row.strategy_family: row for row in report.family_scoreboard}
assert rows["funding_extremity_price_confirmation"].net_pnl_usd == 4.0
assert rows["funding_extremity_price_confirmation"].cost_adjusted_expectancy_usd == 2.0
assert rows["funding_extremity_price_confirmation"].walk_forward_stability == 0.75
assert rows["funding_extremity_price_confirmation"].governance_action in {"keep_collecting", "owner_decision_review"}
assert rows["funding_mean_reversion_after_extreme"].governance_action == "stop"
assert report.stopped_family_ledger[0].strategy_family == "funding_mean_reversion_after_extreme"
assert report.paper_only_portfolio[0].strategy_family == "funding_extremity_price_confirmation"
assert report.monthly_owner_review.best_paper_strategy == "funding_extremity_price_confirmation"
assert report.uses_real_capital is False
assert report.live_order_routing is False
```

Add a CLI test that runs:

```python
main([
    "governance-report",
    "--db", str(db_path),
    "--memory", str(memory_path),
    "--out", str(out),
    "--current-capital-usd", "300",
])
```

and asserts JSON payload command, Markdown header, safety flags, `## Weekly Family Scoreboard`, `## Profit Review`, `## Stopped-Family Ledger`, `## Paper-Only Portfolio Selector`, and `## Monthly Owner Review`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --extra dev pytest tests/test_governance_reports.py tests/test_documentation_contract.py -q
```

Expected: failures for missing `crypto_alpha_agent.pipeline.governance_reports`, missing renderer, missing `governance-report` command, and missing documentation terms.

## Task 2: Governance Report Module

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/governance_reports.py`
- Test: `tests/test_governance_reports.py`

- [ ] **Step 1: Implement strict report models**

Add Pydantic models:

```python
GovernanceAction = Literal["keep_collecting", "stop", "redesign_validator", "add_data", "owner_decision_review"]

class FamilyScoreboardRow(BaseModel):
    strategy_family: str
    sample_size: int
    net_pnl_usd: float
    cost_adjusted_expectancy_usd: float
    max_drawdown_usd: float
    hit_rate: float
    failure_rate: float
    source_health_quality: float
    stale_signal_rate: float
    walk_forward_stability: float
    governance_action: GovernanceAction
    reason_codes: list[str]
```

Add companion models for `ProfitReviewRow`, `StoppedFamilyLedgerRow`, `PaperOnlyPortfolioSelection`, `MonthlyOwnerReview`, and `ProfitGovernanceReport`.

- [ ] **Step 2: Implement report builder**

Implement:

```python
def build_profit_governance_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    current_capital_usd: float = 300.0,
) -> ProfitGovernanceReport:
```

The builder must load validation evidence, paper outcomes, memory, source records, weekly report, paper packages, and data quality. It must derive family rows from the union of families in all those inputs, compute ratios with zero-safe helpers, and keep all safety flags false.

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_governance_reports.py -q
```

Expected after implementation: governance model tests pass; CLI tests still fail until Task 3.

## Task 3: Markdown And CLI

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_governance_reports.py`

- [ ] **Step 1: Add Markdown renderer**

Implement `render_profit_governance_report_markdown(report: ProfitGovernanceReport) -> str` with sections:

```markdown
# Profit Governance Report

## Safety
## Weekly Family Scoreboard
## Profit Review
## Stopped-Family Ledger
## Paper-Only Portfolio Selector
## Monthly Owner Review
```

Tables must include action, reason codes, evidence refs, fees, opportunity-cost estimate, current capital, and `false` safety flags.

- [ ] **Step 2: Wire CLI command**

Add parser:

```python
governance_parser = subparsers.add_parser(
    "governance-report",
    help="Generate deterministic profit governance and paper-only portfolio review.",
)
governance_parser.add_argument("--db", required=True, type=Path)
governance_parser.add_argument("--memory", required=True, type=Path)
governance_parser.add_argument("--out", required=True, type=Path)
governance_parser.add_argument("--current-capital-usd", type=_non_negative_finite_float, default=300.0)
governance_parser.set_defaults(handler=_handle_governance_report, parser=governance_parser)
```

Add handler that writes Markdown and returns JSON:

```python
return {
    "command": "governance-report",
    "governance_report_out": str(args.out),
    "report": report.model_dump(mode="json"),
    "uses_real_capital": False,
    "live_order_routing": False,
}
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_governance_reports.py -q
```

Expected: tests pass.

## Task 4: Documentation And Phase State

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-12-profit-evidence-review-governance-completion-report.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: Document operator workflow**

Add README and runbook examples:

```bash
uv run --extra dev crypto-alpha-agent governance-report \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/monthly/2026-05-governance.md \
  --current-capital-usd 300
```

Document that the report includes weekly family scoreboard, profit review, stopped-family ledger, paper-only portfolio selector, and monthly owner review.

- [ ] **Step 2: Update roadmap and state**

Mark Phase 12 complete only after code and verification are complete. In intermediate edits, describe the implemented governance layer and keep Phase 7 as next.

- [ ] **Step 3: Run documentation tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: pass.

## Task 5: Review And Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run focused regression**

Run:

```bash
uv run --extra dev pytest tests/test_governance_reports.py tests/test_evidence_reports.py tests/test_documentation_contract.py tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system -q
```

Expected: pass.

- [ ] **Step 2: Request two review passes**

Dispatch one spec-compliance reviewer for Phase 12 roadmap coverage and one code-quality/safety reviewer for the complete diff. Fix every Critical or Important issue and re-run focused tests.

- [ ] **Step 3: Run final verification**

Run:

```bash
uv run --extra dev pytest -q
uv run ruff check
git diff --check
uv run python -m crypto_alpha_agent.security.secret_scan --path src --path tests --path docs --fail-on-empty-with-untracked
```

Expected: pytest pass, ruff pass, diff check pass, and secret scan returns no findings.

- [ ] **Step 4: Commit and push**

Run:

```bash
git status --short
git add src tests docs README.md
git commit -m "feat: add profit governance report"
git push origin phase-12-profit-evidence-review-governance
git checkout main
git merge --ff-only phase-12-profit-evidence-review-governance
git push origin main
```

Expected: Phase 12 branch and `main` are updated, with Phase 7 remaining the next roadmap phase.

