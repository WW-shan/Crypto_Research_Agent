# Phase 2 Connect LLM Research Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Phase 1 OpenAI-compatible Responses adapter into the existing research loop, experiment planner, and evidence report flows while preserving research-only authority, strict schemas, and metadata-only memory.

**Architecture:** Keep Phase 2 as an integration slice. Reuse `build_configured_llm(...)` and existing injected LLM seams instead of creating a second client, add CLI LLM mode resolution, add a small evidence-report summarizer contract, and keep deterministic report metrics as the source of truth. Real LLM output is accepted only after Pydantic/schema and charter checks; rejected output stores only response metadata.

**Tech Stack:** Python 3.12, argparse, Pydantic v2, existing OpenAI-compatible Responses adapter, existing LangGraph research graph, pytest, ruff, Smart Search evidence.

---

## External Evidence

Smart Search evidence for this phase is stored under `/tmp/smart-search-evidence/2026-05-23-phase2/`.

- `00-doctor.json`: Smart Search was available; Exa was not configured.
- `01-deep-plan.json`: deep-research plan for safe LLM research-loop integration.
- `02-broad-search.json`: broad discovery found the same safe pattern this codebase already follows: schema-first outputs, metadata-only persistence, human review, and durable graph state.
- `03-openai-responses-create.md`: fetched OpenAI Responses API reference. It confirms Responses requests use `model` plus `input`, and outputs include text/JSON response items.
- `07-langgraph-persistence.md`: fetched LangGraph persistence docs. It confirms checkpointing saves graph state, supports human-in-the-loop, memory, debugging, and fault tolerance; `thread_id` is required to persist/resume graph state.
- `08-langgraph-interrupts.md`: fetched LangGraph interrupts docs. It confirms interrupts pause graph execution, save state through persistence, return JSON-serializable payloads, and are the pattern for review/edit/approval before critical actions.

Implementation consequence: use the existing injected callable and graph seams; do not add execution tools, exchange order routing, or wallet access.

## Local Feasibility

Current repo state already has the key seams:

- `src/crypto_alpha_agent/config.py`: `build_configured_llm(...)` returns the Phase 1 configured adapter and routes `planning`/`research`/`validator_design` to the strong model, `summary`/`report` to the fast model.
- `src/crypto_alpha_agent/pipeline/experiment_planner.py`: `plan_next_experiments(..., llm=None)` already parses LLM output through `ExperimentProposal`, runs the charter guard, rejects unsafe output, and persists only raw-response metadata.
- `src/crypto_alpha_agent/agents/llm_researcher.py`: `run_llm_research_node(report, llm, ...)` already parses strict `HypothesisProposal`.
- `src/crypto_alpha_agent/orchestrator.py`: `build_llm_research_graph(llm, ...)` already strips raw response text before state/memory persistence.
- `src/crypto_alpha_agent/pipeline/evidence_reports.py` and `src/crypto_alpha_agent/pipeline/markdown.py`: evidence reports are deterministic and need an additive optional narrative field only.
- `src/crypto_alpha_agent/cli.py`: `plan-experiments`, `research-loop`, and `evidence-report` are the missing wiring layer.

Feasible changes are additive and confined to CLI wiring, prompts/schema hints, evidence-summary helper code, focused tests, docs, and phase state/report files.

## File Map

- Modify `src/crypto_alpha_agent/llm/responses.py`: add task-specific schema hints to the adapter prompt so real LLM calls can reliably return strict JSON for planner, hypothesis, and evidence-summary tasks.
- Create `src/crypto_alpha_agent/agents/report_summarizer.py`: define strict report-summary task/result models and parse metadata-only LLM narrative summaries.
- Modify `src/crypto_alpha_agent/pipeline/evidence_reports.py`: add optional LLM summary fields to daily/weekly report models without changing deterministic counts or decisions.
- Modify `src/crypto_alpha_agent/pipeline/markdown.py`: render the optional LLM narrative summary in a separate section.
- Modify `src/crypto_alpha_agent/cli.py`: add three-state LLM mode resolution and wire configured LLMs into `plan-experiments`, `research-loop`, and `evidence-report`.
- Modify tests:
  - `tests/test_llm_configured_client.py`
  - `tests/test_ai_experiment_planner.py`
  - `tests/test_cli_research_loop.py`
  - `tests/test_evidence_reports.py`
  - deterministic CLI tests that must stay offline.
- Modify docs:
  - `docs/runbook.md`
  - `docs/roadmap.md`
  - `docs/goals/project-completion-state.md`
  - Create `docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`

## Task 1: Adapter Schema Hints

**Files:**
- Modify: `src/crypto_alpha_agent/llm/responses.py`
- Test: `tests/test_llm_configured_client.py`

- [ ] **Step 1: Write failing tests for task-specific prompt hints**

Add tests that call `OpenAIResponsesAdapter` with a fake session and assert:

```python
def test_responses_adapter_includes_hypothesis_schema_hint_for_research_task():
    # Build a ResearchTask, call adapter, inspect fake session JSON payload.
    # Expected prompt contains HypothesisProposal field names:
    # proposal_id, thesis, hypothesis, assumptions, evidence,
    # disconfirmation, data_needed, capital_required_usd,
    # speed_dependency, rpc_dependency, action_mode.
```

```python
def test_responses_adapter_includes_experiment_schema_hint_for_planner_task(tmp_path):
    # Build an ExperimentPlannerTask through planner fixture or minimal model.
    # Expected prompt contains ExperimentProposal field names:
    # strategy_family, parameter_changes, why_it_might_improve_edge,
    # disconfirmation_tests, stop_conditions, uses_real_capital=false,
    # live_order_routing=false.
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_responses_adapter_includes_hypothesis_schema_hint_for_research_task tests/test_llm_configured_client.py::test_responses_adapter_includes_experiment_schema_hint_for_planner_task -q
```

Expected: FAIL because the adapter prompt currently has only a generic schema instruction.

- [ ] **Step 3: Implement schema hints**

Add `_schema_hint_for_task(task: Any) -> str` to `src/crypto_alpha_agent/llm/responses.py` and include it in `_render_input(...)`.

Rules:

- `ResearchTask` hint must request exactly one `HypothesisProposal` JSON object.
- `ExperimentPlannerTask` hint must request a JSON object with a `proposals` list or one proposal object accepted by existing parser.
- `EvidenceReportSummaryTask` hint must request an evidence-summary JSON object.
- Hints must say no markdown fences and no prohibited authority.

- [ ] **Step 4: Run GREEN tests**

Run the focused tests above and confirm PASS.

## Task 2: Evidence Report Summary Contract

**Files:**
- Create: `src/crypto_alpha_agent/agents/report_summarizer.py`
- Modify: `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Test: `tests/test_evidence_reports.py`

- [ ] **Step 1: Write failing tests for optional summaries**

Add tests asserting:

```python
def test_daily_evidence_report_can_render_llm_summary_without_changing_metrics(tmp_path):
    report = build_daily_evidence_report(...)
    original_counts = report.model_dump(mode="json")
    summary_result = summarize_evidence_report(report, report_type="daily", llm=fake_llm)
    enriched = report.model_copy(update={
        "llm_summary": summary_result.summary,
        "llm_summary_metadata": summary_result.llm_response_metadata,
    })
    assert enriched.validation_evidence_count == original_counts["validation_evidence_count"]
    assert enriched.paper_outcome_count == original_counts["paper_outcome_count"]
    assert "## LLM Narrative Summary" in render_daily_evidence_report_markdown(enriched)
```

```python
def test_report_summarizer_rejects_invalid_or_unsafe_output_without_raw_text(tmp_path):
    # fake LLM returns invalid JSON containing unsafe text.
    # Expected result.accepted is False, raw_response_omitted is True,
    # raw unsafe text is absent from result.model_dump_json().
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_evidence_reports.py::test_daily_evidence_report_can_render_llm_summary_without_changing_metrics tests/test_evidence_reports.py::test_report_summarizer_rejects_invalid_or_unsafe_output_without_raw_text -q
```

Expected: FAIL because summary models/helper/markdown section do not exist.

- [ ] **Step 3: Implement summary models and markdown**

Create `EvidenceReportSummaryTask`, `EvidenceReportNarrativeSummary`, `EvidenceReportSummaryResult`, and `summarize_evidence_report(...)`.

Implementation rules:

- Accept `DailyEvidenceReport` or `WeeklyEvidenceReport`.
- Pass only deterministic report `model_dump(mode="json")` to the LLM task.
- Parse JSON with `json.loads(..., parse_constant=reject)`.
- Validate `uses_real_capital=False` and `live_order_routing=False`.
- Reject invalid/unsafe output with reason codes and metadata only.
- Store no raw provider text in the result.
- Add optional `llm_summary`, `llm_summary_rejected_reason_codes`, and `llm_summary_metadata` fields to daily/weekly report models.
- Render `## LLM Narrative Summary` only when `llm_summary` exists.

- [ ] **Step 4: Run GREEN tests**

Run the focused evidence report tests and confirm PASS.

## Task 3: CLI LLM Mode Wiring

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_ai_experiment_planner.py`
- Test: `tests/test_cli_research_loop.py`
- Test: `tests/test_evidence_reports.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests proving:

```python
def test_plan_experiments_auto_uses_configured_planning_llm(monkeypatch, capsys, tmp_path):
    # monkeypatch crypto_alpha_agent.cli.build_configured_llm to return a fake callable.
    # Run without --offline-only.
    # Expected payload["llm_used"] is True and fake task is ExperimentPlannerTask.
```

```python
def test_plan_experiments_offline_only_skips_configured_llm(monkeypatch, capsys, tmp_path):
    # monkeypatch build_configured_llm to raise if called.
    # Run with --offline-only.
    # Expected payload["llm_used"] is False and deterministic proposal appears.
```

```python
def test_research_loop_can_run_configured_llm_and_persist_metadata_only(monkeypatch, capsys, tmp_path):
    # monkeypatch build_configured_llm to return fake HypothesisProposal JSON.
    # Run research-loop without --offline-only and with --memory.
    # Expected payload has llm_research_result.raw_response_metadata,
    # no raw_response field, and memory stores only metadata.
```

```python
def test_evidence_report_can_use_fast_summary_llm(monkeypatch, capsys, tmp_path):
    # monkeypatch build_configured_llm and assert role == "summary".
    # Run evidence-report without --offline-only.
    # Expected markdown has LLM Narrative Summary and deterministic counts remain.
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --extra dev pytest tests/test_ai_experiment_planner.py::test_plan_experiments_auto_uses_configured_planning_llm tests/test_ai_experiment_planner.py::test_plan_experiments_offline_only_skips_configured_llm tests/test_cli_research_loop.py::test_research_loop_can_run_configured_llm_and_persist_metadata_only tests/test_evidence_reports.py::test_evidence_report_can_use_fast_summary_llm -q
```

Expected: FAIL because the CLI does not resolve or pass configured LLMs.

- [ ] **Step 3: Implement CLI resolver and wiring**

Add helper functions in `src/crypto_alpha_agent/cli.py`:

```python
def _add_offline_only_llm_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--offline-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Omitted: use configured real LLM when local credentials exist. "
            "--offline-only: deterministic local mode. "
            "--no-offline-only: require configured real LLM."
        ),
    )
```

```python
def _resolve_llm_for_cli(args: argparse.Namespace, *, role: LLMRole) -> tuple[Any | None, dict[str, Any]]:
    # True: never build LLM.
    # False: build_configured_llm(required=True) and fail closed.
    # None: build_configured_llm(required=False); if no config, deterministic fallback.
```

Wire:

- `plan-experiments`: role `planning`, pass `llm`, set `offline_only` based on whether an LLM was used, include safe LLM metadata in JSON payload, catch `LLMProviderError` with redacted parser error.
- `research-loop`: role `research`, invoke `build_llm_research_graph(...)` after deterministic report/memory work, include `llm_research_result` without `raw_response`, and let graph write metadata-only memory when `--memory` is present.
- `evidence-report`: role `summary`, call `summarize_evidence_report(...)` before rendering markdown and include safe summary status in payload.

Do not wire `evidence-run` to LLM in Phase 2.

- [ ] **Step 4: Run GREEN tests**

Run focused CLI tests and confirm PASS.

## Task 4: Deterministic Test Isolation And Real Smoke Tests

**Files:**
- Modify deterministic CLI tests that execute `research-loop`, `plan-experiments`, or `evidence-report`.
- Modify: `tests/test_llm_configured_client.py`

- [ ] **Step 1: Add `--offline-only` to deterministic command executions**

Update existing tests that execute these CLIs for deterministic assertions:

- `tests/test_complete_evidence_system.py`
- `tests/test_cli_research_loop.py`
- `tests/test_research_loop_memory_cli.py`
- `tests/test_research_loop_strategy_validation.py`
- `tests/test_research_loop_paper_evidence.py`
- `tests/test_research_loop_validation_summary.py`
- `tests/test_evidence_degradation.py`
- `tests/test_evidence_reports.py`

Only add the flag to commands whose purpose is not real LLM integration.

- [ ] **Step 2: Add real Phase 2 integration tests**

In `tests/test_llm_configured_client.py`, add integration-marked tests that skip in CI unless explicitly enabled and skip when credentials are absent:

```python
def test_real_plan_experiments_cli_smoke_uses_configured_llm_without_secret_leaks(...):
    # Run plan-experiments --no-offline-only with seeded validation evidence.
    # Assert JSON parses, llm_used is True, no key/base URL in stdout/stderr/memory.
```

```python
def test_real_evidence_report_summary_smoke_without_secret_leaks(...):
    # Run evidence-report --no-offline-only.
    # Assert markdown has deterministic metrics plus LLM Narrative Summary,
    # and no key/base URL in stdout/stderr/report.
```

- [ ] **Step 3: Run focused deterministic and integration tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py tests/test_ai_experiment_planner.py tests/test_cli_research_loop.py tests/test_evidence_reports.py -q
```

Expected: PASS, including real LLM tests locally when credentials are configured.

## Task 5: Docs, State, Phase Report

**Files:**
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-23-phase-2-connect-llm-research-loop-completion-report.md`

- [ ] **Step 1: Update runbook**

Document:

- default real LLM behavior when local credentials are configured;
- `--offline-only` deterministic mode;
- `--no-offline-only` fail-closed real LLM mode;
- model routing: planning/research/validator-design use strong model; report summary uses fast model;
- raw responses are not stored by default.

- [ ] **Step 2: Update roadmap/state**

Record Phase 2 completion and set next round to Immediate Phase 3 only after verification.

- [ ] **Step 3: Write completion report**

Include:

- Smart Search evidence paths and provider gaps;
- local feasibility findings;
- files changed;
- tests and review passes;
- secret-safety checks;
- remaining Phase 3 scope.

## Task 6: Review, Verification, Commit, Push

**Files:**
- All Phase 2 changes.

- [ ] **Step 1: Review pass 1**

Use a subagent/read-only review for spec compliance:

- Does Phase 2 meet each roadmap bullet?
- Are raw LLM responses absent from memory/reports?
- Does no live/wallet/order path appear?

Fix every Critical/Important finding and re-review until clean.

- [ ] **Step 2: Review pass 2**

Use a subagent/read-only code-quality review:

- Is CLI mode behavior clear and fail-closed?
- Are deterministic tests isolated from real LLM calls?
- Are summaries additive and not decision sources?

Fix every Critical/Important finding and re-review until clean.

- [ ] **Step 3: Final verification**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short --branch --untracked-files=all
git diff --cached --check
```

Run a staged secret scan after staging without printing local secret values.

- [ ] **Step 4: Commit and push**

Commit only Phase 2 files:

```bash
git add <phase-2-files>
git commit -m "feat: connect llm to research loop"
git push
```

Do not start Phase 3 in this round.

## Self-Review

- Spec coverage: all Phase 2 integration points are covered: planner, research loop, evidence report summaries, schema parsing, metadata-only persistence, docs/state/report, review and verification gates.
- Placeholder scan: no TBD/TODO placeholders remain in this plan.
- Type consistency: the plan uses existing `build_configured_llm`, `ExperimentPlannerTask`, `HypothesisProposal`, `build_llm_research_graph`, and planned `EvidenceReportSummaryTask` consistently.
- Scope control: `evidence-run`, live execution, wallet keys, order routing, MEV, premium RPC, and Phase 3 policy expansion remain outside Phase 2.
