# Phase 14 LLM-Native Autonomous Iteration Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first LLM-native auto-iteration command that turns current evidence into guarded next-step candidates without executing code, trades, or source promotion.

**Architecture:** Add a focused `iteration_controller` pipeline that reuses `AIResearchContext`, `expansion-prep`, and governance facts. The CLI command will pass through the existing real-LLM gate, call the controller with `runtime.llm`, validate strict Pydantic output, render Markdown/JSON artifacts, and fail closed on unsafe or uncited output.

**Tech Stack:** Python 3.12, Pydantic v2 strict models, existing CLI runtime gate, SQLite evidence stores, JSON/Markdown artifacts, pytest, ruff.

---

## Files

- Create: `src/crypto_alpha_agent/pipeline/iteration_controller.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Modify: `tests/test_documentation_contract.py`
- Create: `tests/test_iteration_controller.py`
- Create: `tests/test_iteration_cycle_cli.py`
- Modify: `docs/roadmap.md`
- Modify: `docs/runbook.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-29-phase-14-llm-native-autonomous-iteration-controller-completion-report.md`

## Task 1: Pipeline Models And Guards

**Files:**
- Create: `tests/test_iteration_controller.py`
- Create: `src/crypto_alpha_agent/pipeline/iteration_controller.py`

- [ ] **Step 1: Write failing model and LLM acceptance tests**

Create tests that import `build_iteration_cycle_report` and assert:

```python
result = build_iteration_cycle_report(
    db_path=tmp_path / "research.sqlite",
    memory_path=tmp_path / "memory.jsonl",
    llm=lambda task: json.dumps({
        "candidates": [{
            "kind": "code_change_request",
            "title": "Add source probe fixture",
            "rationale": "Current evidence needs a repeatable source probe.",
            "evidence_refs": ["goal:owner_autonomy_target"],
            "expected_value": "Improves source qualification.",
            "risk_level": "medium",
            "next_actions": ["Write failing tests first."],
            "required_tests": ["pytest tests/test_source_probe.py -q"],
            "required_data_fields": ["source_health"],
            "source_discovery_queries": [],
            "source_probe_targets": [],
            "strategy_family": None,
            "target_files": ["src/crypto_alpha_agent/data/source_probe.py"],
            "human_review_required": True,
            "direct_code_write_authorized": False,
            "uses_real_capital": False,
            "live_order_routing": False
        }],
        "rejected_reason_codes": [],
        "uses_real_capital": False,
        "live_order_routing": False
    }),
    current_capital_usd=300,
)
assert result.accepted is True
assert result.candidates[0].kind == "code_change_request"
assert result.candidates[0].direct_code_write_authorized is False
```

Also add tests for unknown evidence refs, direct-code-write authorization, and
`new_data_source` without discovery queries or probe targets.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_iteration_controller.py -q
```

Expected: import failure for missing `iteration_controller`.

- [ ] **Step 3: Implement strict models and controller**

Implement strict Pydantic models with `extra="forbid"`, `strict=True`, and
`allow_inf_nan=False`. Build context with `build_ai_research_context`,
`build_expansion_preparation_report`, and `build_profit_governance_report`.
Reject:

- unknown evidence refs;
- live capital or live order routing;
- direct code write authorization;
- code-change requests without target files;
- candidates without required tests;
- new data sources without discovery queries or probe targets;
- unsafe charter-guard output.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_iteration_controller.py -q
```

Expected: all tests pass.

## Task 2: Markdown Rendering

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `tests/test_iteration_controller.py`

- [ ] **Step 1: Write failing Markdown render test**

Assert `render_iteration_cycle_markdown(report)` includes:

- `# Iteration Cycle Report`
- safety flags;
- candidate kind, title, evidence refs, required tests;
- `Direct code write authorized: false`.

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_iteration_controller.py -q
```

Expected: missing renderer import or attribute failure.

- [ ] **Step 3: Implement renderer**

Add a compact renderer to `markdown.py` that uses existing `_escape_text`,
`_escape_table_cell`, and `_bool_text` helpers.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_iteration_controller.py -q
```

Expected: all tests pass.

## Task 3: CLI Command

**Files:**
- Modify: `src/crypto_alpha_agent/cli.py`
- Create: `tests/test_iteration_cycle_cli.py`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests that monkeypatch `build_required_real_llm_runtime` with the existing
test runtime pattern and assert:

```python
exit_code = main([
    "iteration-cycle",
    "--db", str(db_path),
    "--memory", str(memory_path),
    "--out", str(markdown_path),
    "--json-out", str(json_path),
    "--current-capital-usd", "300",
    "--max-candidates", "3",
])
assert exit_code == 0
assert payload["command"] == "iteration-cycle"
assert payload["llm_required"] is True
assert payload["auto_executes_changes"] is False
assert markdown_path.exists()
assert json_path.exists()
```

Update documentation parser examples so `iteration-cycle` parses.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_iteration_cycle_cli.py tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q
```

Expected: CLI rejects unknown command.

- [ ] **Step 3: Implement CLI parser and handler**

Add parser args:

- `--db`
- `--memory`
- `--out`
- `--json-out`
- `--strategy-family`
- `--current-capital-usd`
- `--max-candidates`

Add `_handle_iteration_cycle` that calls `build_iteration_cycle_report(...,
llm=runtime.llm)`, writes Markdown and JSON, includes runtime metadata, and
uses `args.parser.error(...)` on LLM/provider/runtime validation failures.

Update `_llm_role_for_command()` so `iteration-cycle` uses `planning`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_iteration_cycle_cli.py tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q
```

Expected: all tests pass.

## Task 4: Docs, State, And Phase Report

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/runbook.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-29-phase-14-llm-native-autonomous-iteration-controller-completion-report.md`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Write failing documentation contract**

Add required terms:

- `iteration-cycle`
- `IterationCandidate`
- `autonomous code-writing loop remains proposal-only`
- `autonomous new data source discovery remains probe-gated`
- `auto_executes_changes=false`

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: missing documentation terms.

- [ ] **Step 3: Update docs and phase report**

Document that Phase 14 completes the first safe autonomy increment, not full
self-coding. Record Smart Search evidence path, files changed, tests, real LLM
policy, secret-safety, and remaining gaps.

- [ ] **Step 4: Run documentation tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: all tests pass.

## Task 5: Final Verification And Commit

**Files:** all changed files.

- [ ] **Step 1: Run focused tests**

```bash
uv run --extra dev pytest tests/test_iteration_controller.py tests/test_iteration_cycle_cli.py tests/test_documentation_contract.py -q
```

- [ ] **Step 2: Run full verification**

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
```

- [ ] **Step 3: Secret-safety review**

```bash
git diff --cached --check
git diff --cached --name-only
git diff --cached --no-ext-diff --unified=0
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

- [ ] **Step 4: Commit**

```bash
git add src/crypto_alpha_agent/pipeline/iteration_controller.py \
  src/crypto_alpha_agent/pipeline/markdown.py \
  src/crypto_alpha_agent/cli.py \
  tests/test_iteration_controller.py \
  tests/test_iteration_cycle_cli.py \
  tests/test_documentation_contract.py \
  docs/roadmap.md \
  docs/runbook.md \
  docs/goals/project-completion-state.md \
  docs/goals/phase-reports/2026-05-29-phase-14-llm-native-autonomous-iteration-controller-completion-report.md \
  docs/superpowers/specs/2026-05-29-phase-14-llm-native-autonomous-iteration-controller-design.md \
  docs/superpowers/plans/2026-05-29-phase-14-llm-native-autonomous-iteration-controller.md
git commit -m "feat: add llm iteration controller"
```

## Self-Review

- Spec coverage: covers LLM-required candidate generation, strict schemas,
  evidence refs, safety gates, CLI artifact output, docs, and verification.
- Placeholder scan: no TBD/TODO placeholders are present.
- Type consistency: command name is `iteration-cycle`; model name is
  `IterationCandidate`; command output uses `auto_executes_changes=false`.
