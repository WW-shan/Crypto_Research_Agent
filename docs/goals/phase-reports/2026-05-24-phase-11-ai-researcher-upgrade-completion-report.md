# Phase 11 AI Researcher Upgrade Completion Report

Date: 2026-05-24

Commit reference: Phase 11 completion commit
`feat: upgrade ai researcher evidence guards`.

## Objective

Complete Phase 11 by making AI-generated research proposals evidence-grounded,
strictly schema checked, duplicate aware, and unable to invent paper outcomes,
route orders, use live capital, request wallet keys, require MEV/private RPC, or
bypass deterministic validators.

## External Evidence

Smart Search deep research was run before design and planning. Evidence files
were kept under ignored
`var/smart-search-evidence/phase-11-ai-researcher-upgrade/`.

Source-backed findings used:

- OpenAI Structured Outputs documentation supports JSON Schema adherence but
  warns structured outputs can still contain mistakes:
  <https://developers.openai.com/api/docs/guides/structured-outputs>
- OpenAI hallucination guardrail guidance checks model outputs against
  source-of-truth knowledge and flags unsubstantiated claims:
  <https://developers.openai.com/cookbook/examples/developing_hallucination_guardrails>
- OWASP LLM01 Prompt Injection documents direct and indirect prompt injection
  risks:
  <https://genai.owasp.org/llmrisk/llm01-prompt-injection/>
- OWASP LLM06 Excessive Agency recommends minimizing permissions,
  functionality, and autonomy:
  <https://genai.owasp.org/llmrisk/llm06-excessive-agency/>
- OWASP LLM08 Vector and Embedding Weaknesses recommends source validation,
  access control, monitoring, and logging for RAG-style systems:
  <https://genai.owasp.org/llmrisk/llm08-vector-and-embedding-weaknesses/>
- OWASP LLM09 Misinformation recommends verified retrieval, cross-checking,
  human oversight, and automatic validation:
  <https://genai.owasp.org/llmrisk/llm09-misinformation/>
- Context7 Pydantic docs confirmed strict validation, `extra='forbid'`, and
  JSON-schema support patterns.

## Local Feasibility

- Baseline verification in the isolated Phase 11 worktree passed with
  `881 passed, 4 skipped, 2 warnings`.
- Existing ledgers already exposed validation evidence, paper outcomes, source
  records, and memory needed for AI context.
- `ResearchDataStore` plus `build_data_quality_report` could normalize source
  health without a new table.
- `StrategyRegistry` already exposed validator names, required record types,
  notional limits, paper support, and execution roles.
- `MemoryStore` is schema-light JSONL, so rejected and template proposal memory
  could be additive and backward compatible.

## Implemented

- Added `pipeline/ai_research_context.py` with strict DTOs for validation
  evidence, paper evidence, source health, stopped families, blocked
  parameters, available data fields, evidence refs, and registered validators.
- Tightened `pipeline/experiment_planner.py`:
  - registered LLM experiment proposals now require evidence refs, parameter
    changes, expected edge mechanism, disconfirmation tests, stop conditions,
    required data fields, and selected validator;
  - sparse LLM proposals, nonexistent evidence refs, unsupported data fields,
    unsupported validators, direct paper-outcome payloads, execution requests,
    private RPC, MEV, wallet-key, and over-capital proposals are rejected;
  - duplicate detection canonicalizes parameter payloads and blocks rejected or
    blocked parameter sets from memory;
  - supported data gaps are explicit, not arbitrary string prefixes;
  - mixed valid and invalid LLM batches persist separate partial-rejected
    memory while keeping valid proposals accepted.
- Added design-only `StrategyTemplateProposal` output. Template proposals are
  persisted as requiring deterministic tests and human review, and they cannot
  create paper outcomes or route execution.
- Added `pipeline/ai_research_memo.py` plus `ai-research-memo` CLI and Markdown
  rendering. The memo explains what changed, what failed, what should stop,
  and which experiment is next.
- Upgraded `agents/llm_researcher.py` with optional db/memory context injection
  while preserving existing graph behavior.
- Updated README, runbook, roadmap, project asset assessment, documentation
  contracts, project state, and this report.

## Subagents And Review

- Planck performed a read-only feasibility audit before implementation. It
  identified the missing Phase 11 boundaries: source-health context, stricter
  schema, duplicate/citation guards, design-only templates, and weekly memo.
- Archimedes performed a read-only code review after implementation. It found
  two Important issues:
  - mixed valid and invalid LLM batches were not persisting rejected memory;
  - broad `data-gap:*` and `gap:supported_*` evidence refs were too permissive.
- Both review findings were fixed with regression tests. Re-review by focused
  tests and full suite passed.

## Verification

- Focused Phase 11 plus end-to-end regression:
  `uv run --extra dev pytest tests/test_ai_research_context.py tests/test_ai_experiment_planner.py tests/test_ai_strategy_template_proposals.py tests/test_ai_research_memo.py tests/test_llm_researcher_adapter.py tests/test_llm_graph_routing.py tests/test_documentation_contract.py tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system -q`
  passed with 53 tests.
- `uv run ruff check` passed.
- Full verification:
  `uv run --extra dev pytest -q` passed with 893 tests and 4 skipped.

## Safety

- `uses_real_capital=false`
- `live_order_routing=false`
- No live execution, wallet keys, wallet-key access, exchange order routing,
  real capital, MEV, mempool, private RPC, premium RPC, speed-edge execution,
  or AI-created paper outcomes were added.
- Unsafe or unverifiable full LLM outputs are persisted as rejected memory.
  Partially invalid LLM batches now persist separate partial-rejected memory.

## Remaining Gaps

- Phase 12 must add profit evidence review and portfolio governance scoring.
- Phase 7 historical bootstrap and future out-of-sample paper collection should
  only start after Phases 8 through 12 are complete.
- Tiny-live review remains blocked by the current charter and by the absence of
  sufficient future paper observations.

## Next Phase

Phase 12 is the next phase. It was not started during this round.
