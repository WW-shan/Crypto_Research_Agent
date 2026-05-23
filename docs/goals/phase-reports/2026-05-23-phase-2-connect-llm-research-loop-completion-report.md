# Phase 2 Connect LLM Research Loop Completion Report

## Scope

- Phase: Immediate Phase 2: Connect LLM To The Research Loop.
- Date: 2026-05-23.
- Commit: `ae3e601 feat: connect llm to research loop`.
- Objective: connect the Phase 1 configured LLM adapter to the existing
  research assistant surfaces without adding execution authority.
- Boundaries: no live trading, wallet access, exchange order routing, real
  capital, MEV, premium RPC, speed-edge dependency, or execution adapter was
  added.

## External Evidence

Smart Search evidence for this phase was stored under
`/tmp/smart-search-evidence/2026-05-23-phase2/`.

Commands and evidence:

```bash
smart-search doctor --format json
smart-search deep "safe LLM integration for a LangGraph crypto research loop with strict schemas, metadata-only memory, report summaries, and human review checkpoints" --format json --output /tmp/smart-search-evidence/2026-05-23-phase2/01-deep-plan.json
smart-search search "OpenAI Responses API JSON schema LangGraph persistence human review metadata only LLM memory" --validation balanced --extra-sources 3 --format json --output /tmp/smart-search-evidence/2026-05-23-phase2/02-broad-search.json
smart-search fetch "https://platform.openai.com/docs/api-reference/responses/create" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase2/03-openai-responses-create.md
smart-search fetch "https://docs.langchain.com/oss/python/langgraph/persistence" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase2/07-langgraph-persistence.md
smart-search fetch "https://docs.langchain.com/oss/python/langgraph/interrupts" --format markdown --output /tmp/smart-search-evidence/2026-05-23-phase2/08-langgraph-interrupts.md
```

Findings used:

- OpenAI Responses requests use `model` plus `input`, and response text can be
  extracted from `output_text` or nested `output` message items.
- LangGraph persistence/checkpointing is suitable for durable state, memory,
  fault recovery, and human-in-the-loop review.
- LangGraph interrupts support review/edit/approval patterns before critical
  actions.
- Exa official-doc search was unavailable because `EXA_API_KEY` was not
  configured; the phase used Smart Search broad search and fetched source pages.

## Local Feasibility

The existing repository already had the right seams:

- `build_configured_llm(...)` in `src/crypto_alpha_agent/config.py` returned the
  Phase 1 OpenAI-compatible Responses adapter and role-based model routing.
- `plan_next_experiments(..., llm=None)` already accepted an injected LLM,
  parsed strict `ExperimentProposal` output, applied charter guards, and wrote
  raw-response metadata only.
- `build_llm_research_graph(...)` already stripped raw LLM output before graph
  state and memory persistence.
- Evidence reports were deterministic and needed only an additive optional LLM
  narrative field.

## Implementation Summary

Files changed in commit `ae3e601`:

- `src/crypto_alpha_agent/llm/responses.py`
- `src/crypto_alpha_agent/agents/report_summarizer.py`
- `src/crypto_alpha_agent/pipeline/evidence_reports.py`
- `src/crypto_alpha_agent/pipeline/markdown.py`
- `src/crypto_alpha_agent/cli.py`
- `tests/test_llm_configured_client.py`
- `tests/test_ai_experiment_planner.py`
- `tests/test_cli_research_loop.py`
- `tests/test_evidence_reports.py`
- `docs/runbook.md`
- `docs/roadmap.md`
- `docs/goals/project-completion-state.md`
- `docs/superpowers/plans/2026-05-23-phase-2-connect-llm-research-loop.md`

Behavior added:

- Task-specific schema hints for research hypotheses, experiment-planner
  proposals, and evidence-report summaries.
- Strict report-summary task/result models with unsafe-text rejection, JSON
  parsing, and metadata-only response handling.
- Optional daily/weekly evidence-report LLM narrative summaries rendered in a
  separate `LLM Narrative Summary` section.
- CLI LLM mode resolution for `plan-experiments`, `research-loop`, and
  `evidence-report`.
- `--offline-only` deterministic mode and `--no-offline-only` fail-closed real
  LLM mode for the Phase 2 CLI surfaces.
- Pytest isolation so CLI real LLM paths remain deterministic in tests unless
  `CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1` is set.

## Verification

Focused TDD checks:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_responses_adapter_includes_hypothesis_schema_hint_for_research_task tests/test_llm_configured_client.py::test_responses_adapter_includes_experiment_schema_hint_for_planner_task -q
```

Result: failed before schema hints existed, then passed with 2 tests.

```bash
uv run --extra dev pytest tests/test_evidence_reports.py::test_daily_evidence_report_can_render_llm_summary_without_changing_metrics tests/test_evidence_reports.py::test_report_summarizer_rejects_invalid_or_unsafe_output_without_raw_text -q
```

Result: failed before `report_summarizer` existed, then passed with 2 tests.

```bash
uv run --extra dev pytest tests/test_ai_experiment_planner.py::test_plan_experiments_auto_uses_configured_planning_llm tests/test_ai_experiment_planner.py::test_plan_experiments_offline_only_skips_configured_llm tests/test_cli_research_loop.py::test_research_loop_can_run_configured_llm_and_persist_metadata_only tests/test_evidence_reports.py::test_evidence_report_can_use_fast_summary_llm -q
```

Result: failed before CLI LLM resolution existed, then passed with 4 tests.

Focused regressions:

```bash
uv run --extra dev pytest tests/test_ai_experiment_planner.py tests/test_cli_research_loop.py tests/test_evidence_reports.py tests/test_complete_evidence_system.py tests/test_research_loop_strategy_validation.py tests/test_research_loop_paper_evidence.py tests/test_research_loop_validation_summary.py -q
```

Result: 61 passed.

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py tests/test_llm_researcher_adapter.py tests/test_llm_graph_routing.py tests/test_llm_contracts.py -q
```

Result: passed after retrying a transient real-provider `504`.

Real LLM smoke:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks -q
```

Result: passed after the transient provider failure was rerun.

Final pre-commit verification:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git diff --cached --check
```

Result: 770 tests passed, ruff passed, and diff checks passed.

## Secret Safety

- `.env` was not staged.
- The staged secret scan checked API-key-like tokens, bearer tokens, GitHub
  tokens, private-key blocks, and actual configured sensitive values loaded
  from local `.env` or shell environment without printing those values.
- The staged secret scan passed.
- Raw provider headers and raw LLM responses were not persisted to memory,
  reports, or docs.

## Review Record

The Phase 2 plan required two review passes. The durable repository record for
those review passes was not committed with the original Phase 2 commit. This
report records the recovered implementation and verification evidence from the
state file and current code; Phase 3 treats the missing report itself as a
documentation-chain gap and repairs it here.

Phase 3 and later phases must preserve complete phase reports and review
records before marking a phase complete.

## Remaining Work

Immediate Phase 3 must formalize the real LLM test policy:

- real positive integration tests for `plan-experiments`, `research-loop`, and
  `evidence-report`;
- deterministic fake adversarial policy coverage;
- secret scanning over stdout, stderr, memory, reports, artifacts, manifests,
  and staged diffs;
- updated runbook, state, roadmap, and phase report records.
