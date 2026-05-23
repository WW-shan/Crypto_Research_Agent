# Phase 11 AI Researcher Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI researcher useful for proposing evidence-grounded experiments while preventing it from inventing data, bypassing deterministic validators, creating paper outcomes, or requesting live/private/high-capital execution paths.

**Architecture:** Add a reusable AI research context builder that turns local validation evidence, paper evidence, source health, stopped-family memory, blocked parameters, available data fields, evidence refs, and registered validators into strict DTOs. Feed that context to the experiment planner and LLM researcher. Tighten planner LLM acceptance so registered experiment proposals must cite existing evidence or request supported data collection, must select a registered validator, and must require only available data fields. Add design-only strategy template proposals and a deterministic weekly AI research memo.

**Tech Stack:** Python 3.12, Pydantic strict models, SQLite source/evidence ledgers, JSONL memory store, existing strategy registry, pytest, ruff.

---

## Binding Scope

Implement exactly Phase 11 from `docs/roadmap.md`:

- Evidence retrieval context summarizing recent validation evidence, paper outcomes, source health, stopped families, and blocked parameter sets.
- Stricter experiment proposal schema requiring evidence references, parameter changes, expected edge mechanism, disconfirmation tests, stop conditions, required data fields, and selected validator.
- Strategy-template proposal mode where AI may propose a new validator design, but implementation still requires deterministic tests and human review.
- Duplicate experiment detection for rejected assumptions, stopped parameter sets, and previously accepted proposals.
- Hallucination guard rejecting unavailable data fields, unsupported sources, live execution, private RPC, MEV, wallet keys, or capital above owner profile.
- Weekly AI research memo explaining what changed, what failed, what should stop, and the next experiment.

Keep the project charter intact: no live trading, no exchange order routing, no wallet/private-key access, no real capital, no private RPC, no MEV, and no speed-edge infrastructure.

## External Evidence

Smart Search deep research was run before this plan. Evidence files are intentionally kept under ignored `var/smart-search-evidence/phase-11-ai-researcher-upgrade/` in the worktree, not committed.

Key source-backed implementation constraints:

- OpenAI Structured Outputs documentation says schemas can make model output adhere to JSON Schema and are stronger than JSON mode, but also warns structured outputs can still contain mistakes and need application handling: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI's hallucination guardrail example treats model output checking as an output guardrail that compares generated claims to source-of-truth knowledge and flags unsubstantiated claims: https://developers.openai.com/cookbook/examples/developing_hallucination_guardrails
- OWASP LLM01 Prompt Injection notes direct and indirect prompt injection can alter model behavior and affect critical decisions, so external/context text cannot be trusted as instructions: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP LLM06 Excessive Agency identifies excessive functionality, permissions, and autonomy as root causes and recommends minimizing extensions, least privilege, human approval, and complete mediation: https://genai.owasp.org/llmrisk/llm06-excessive-agency/
- OWASP LLM08 Vector and Embedding Weaknesses recommends source validation, access controls, review/classification, monitoring, and logging for RAG-style context stores: https://genai.owasp.org/llmrisk/llm08-vector-and-embedding-weaknesses/
- OWASP LLM09 Misinformation recommends retrieval from verified sources, cross-verification, human oversight, and automatic validation for high-stakes outputs: https://genai.owasp.org/llmrisk/llm09-misinformation/
- Context7 Pydantic docs confirm `extra='forbid'`, strict validation, and JSON-schema generation patterns are supported for local schema enforcement.

## Local Feasibility

Baseline worktree verification:

- `git worktree add .worktrees/phase-11-ai-researcher-upgrade -b phase-11-ai-researcher-upgrade`
- `uv run --extra dev pytest -q`: `881 passed, 4 skipped, 2 warnings in 79.97s`

Existing seams:

- `pipeline.experiment_planner` already loads validation evidence, paper outcomes, degraded/stopped families, and blocked parameter sets; Phase 11 should enrich this rather than replace it.
- `PaperOutcomeLedger`, `ValidationEvidenceLedger`, and `ResearchDataStore` expose all source data needed for context. Source health can be normalized with `data.quality.build_data_quality_report`.
- `StrategyRegistry` exposes registered families, required record types, symbols, validator names, notional limits, execution roles, and paper support.
- `MemoryStore` is schema-light JSONL. New duplicate and rejected-output memory should be additive and tolerate older records.
- Weekly evidence reports already aggregate family actions and rejected reasons. The AI research memo can build from the weekly report and planner context without mutating weekly report metrics.

Read-only subagent audit confirmed the primary gaps: source-health context, explicit recent evidence refs, required fields/selected validator, stricter LLM parsing, canonical duplicate detection, citation/data-field guards, design-only template proposals, and weekly memo rendering.

## File Structure

- Create `src/crypto_alpha_agent/pipeline/ai_research_context.py`
  - Own strict DTOs for evidence refs, validation summaries, paper summaries, source health, blocked parameter sets, stopped families, available data fields, and registered validators.
  - Provide `build_ai_research_context(db_path, memory_path, strategy_family=None, current_capital_usd=300.0, recent_limit=10)`.
- Modify `src/crypto_alpha_agent/pipeline/experiment_planner.py`
  - Add required Phase 11 proposal fields, selected-validator checks, required-data-field checks, evidence citation checks, canonical duplicate detection, template proposal parsing, paper-outcome hallucination rejection, and richer planner task context.
- Modify `src/crypto_alpha_agent/agents/llm_contracts.py`
  - Add strict strategy-template proposal contract fields if shared with the researcher.
- Modify `src/crypto_alpha_agent/agents/llm_researcher.py`
  - Accept optional `db_path` and `memory_path`, add AI research context to prompt context, and keep unsafe memory/source text sanitized.
- Create `src/crypto_alpha_agent/pipeline/ai_research_memo.py`
  - Build a deterministic weekly memo with what changed, what failed, what should stop, next experiment, evidence refs, and safety flags.
- Modify `src/crypto_alpha_agent/pipeline/markdown.py`
  - Render weekly AI research memos.
- Modify `src/crypto_alpha_agent/cli.py`
  - Add `ai-research-memo` command and include strategy-template proposals in `plan-experiments` JSON.
- Modify focused tests:
  - `tests/test_ai_research_context.py`
  - `tests/test_ai_experiment_planner.py`
  - `tests/test_ai_research_memo.py`
  - `tests/test_llm_researcher_adapter.py`
  - `tests/test_documentation_contract.py`
- Modify docs:
  - `README.md`
  - `docs/runbook.md`
  - `docs/roadmap.md`
  - `docs/project-asset-assessment.md`
  - `docs/goals/project-completion-state.md`
  - Create `docs/goals/phase-reports/2026-05-24-phase-11-ai-researcher-upgrade-completion-report.md`

---

### Task 1: AI Research Context Builder

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/ai_research_context.py`
- Test: `tests/test_ai_research_context.py`

- [x] Write failing tests proving context includes bounded recent validation evidence, paper evidence cost-model fields, source-health summaries, stopped families, blocked parameter sets, available data fields, registered validators, and evidence refs.
- [x] Implement strict context DTOs with `extra="forbid"`, `strict=True`, `allow_inf_nan=False`.
- [x] Use `ValidationEvidenceLedger`, `PaperOutcomeLedger`, `ResearchDataStore`, `build_data_quality_report`, `MemoryStore`, and `default_strategy_registry`.
- [x] Sanitize context values through the existing charter guard style, omitting unsafe text.
- [x] Run `uv run --extra dev pytest tests/test_ai_research_context.py -q`.

### Task 2: Stricter Experiment Planner Schema And Guards

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- Test: `tests/test_ai_experiment_planner.py`

- [x] Add failing tests for LLM rejection when `selected_validator`, `required_data_fields`, `expected_edge_mechanism`, or evidence refs are missing.
- [x] Add failing tests for nonexistent evidence refs, unavailable data fields, unsupported sources, direct paper outcome payloads, and capital/live/private-RPC/MEV/wallet violations.
- [x] Add failing tests for canonical duplicate parameters from prior accepted proposals and rejected memory.
- [x] Add failing tests proving deterministic fallback remains backward compatible and still emits safe proposals with the new fields filled.
- [x] Implement stricter LLM proposal parsing while keeping deterministic fallback behavior stable.
- [x] Add canonical parameter signatures and duplicate reason code `duplicate_experiment`.
- [x] Use the new AI research context for planner task fields and guard decisions.
- [x] Run `uv run --extra dev pytest tests/test_ai_experiment_planner.py -q`.

### Task 3: Strategy Template Proposal Mode

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- Optionally modify: `src/crypto_alpha_agent/agents/llm_contracts.py`
- Test: `tests/test_ai_strategy_template_proposals.py`

- [x] Write failing tests for accepting a design-only validator template proposal with evidence refs, required data fields, expected mechanism, disconfirmation tests, stop conditions, deterministic test requirements, and human review requirement.
- [x] Write failing tests proving template proposals cannot create paper outcomes, run validators, authorize execution, or bypass review.
- [x] Implement `StrategyTemplateProposal` and expose `strategy_template_proposals` on `ExperimentPlannerResult`.
- [x] Persist accepted template proposals as memory tagged `strategy-template-proposal` and rejected unsafe template outputs as rejected memory.
- [x] Run `uv run --extra dev pytest tests/test_ai_strategy_template_proposals.py tests/test_ai_experiment_planner.py -q`.

### Task 4: LLM Researcher Context Upgrade

**Files:**
- Modify: `src/crypto_alpha_agent/agents/llm_researcher.py`
- Test: `tests/test_llm_researcher_adapter.py`

- [x] Write failing test proving optional db/memory paths add paper evidence, source health, stopped families, blocked parameters, and registered validators to `ResearchTask.context`.
- [x] Preserve existing tests by making the new context optional.
- [x] Implement optional context injection using `build_ai_research_context`.
- [x] Run `uv run --extra dev pytest tests/test_llm_researcher_adapter.py tests/test_llm_graph_routing.py -q`.

### Task 5: Weekly AI Research Memo

**Files:**
- Create: `src/crypto_alpha_agent/pipeline/ai_research_memo.py`
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_ai_research_memo.py`

- [x] Write failing tests for memo content: what changed, what failed, what should stop, next experiment, evidence refs, rejected reason codes, template proposals, and safety flags.
- [x] Write failing CLI test for `ai-research-memo --db --memory --out`.
- [x] Implement deterministic memo builder from weekly report plus planner context/result.
- [x] Implement markdown renderer and CLI payload.
- [x] Run `uv run --extra dev pytest tests/test_ai_research_memo.py tests/test_evidence_reports.py -q`.

### Task 6: Documentation And Completion Artifacts

**Files:**
- Modify: `README.md`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-asset-assessment.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-24-phase-11-ai-researcher-upgrade-completion-report.md`
- Test: documentation contract tests

- [x] Update docs with Phase 11 command surfaces, AI researcher constraints, memo workflow, and completion status.
- [x] Ensure docs state AI cannot create paper outcomes or execute trades.
- [x] Run `uv run --extra dev pytest tests/test_documentation_contract.py -q`.

### Task 7: Final Verification

- [x] Run focused Phase 11 tests.
- [x] Run `uv run ruff check`.
- [x] Run `uv run --extra dev pytest -q`.
- [ ] Inspect `git diff --stat` and `git status --short`.
- [ ] Commit and push only Phase 11 changes.
