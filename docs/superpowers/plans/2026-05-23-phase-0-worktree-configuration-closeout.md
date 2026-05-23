# Phase 0 Worktree Configuration Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Immediate Phase 0 / merged Phase 6 so Phase 1 can start from a clean, deliberate, secret-safe worktree.

**Architecture:** This is a repository hygiene and documentation gate. It commits only shared ignore rules, operator documentation, state/roadmap synchronization, and a Phase completion report; it deletes an untracked Phase 1 draft test so LLM adapter implementation can start later under its own TDD plan. It does not add runtime LLM code, live trading, wallet handling, order routing, MEV, premium RPC, or capital execution.

**Tech Stack:** Git, Markdown, `.gitignore`, pytest documentation/CLI smoke tests, ruff, Smart Search CLI evidence files, Superpowers review workflow.

---

## Scope And Evidence

**Selected Phase:** Immediate Phase 0 / merged Phase 6: worktree and configuration closeout.

**Smart Search evidence gathered before planning:**

- Deep plan:
  `/tmp/smart-search-evidence/2026-05-23-phase0/01-deep-plan.json`
- Fetched GitHub ignore guidance:
  `/tmp/smart-search-evidence/2026-05-23-phase0/02-github-ignoring-files.md`
- Fetched GitHub secret scanning guidance:
  `/tmp/smart-search-evidence/2026-05-23-phase0/03-github-secret-scanning.md`

**External findings applied:**

- Shared repository ignore behavior belongs in committed `.gitignore`; purely local-only rules can live in `.git/info/exclude`.
- Hardcoded credentials in repositories create unauthorized-access risk and should be detected before they are committed.

**Local feasibility findings:**

- `git status --short --branch --untracked-files=all` shows only `.agents/`, `.claude/`, and `tests/test_llm_configured_client.py` are currently untracked.
- `.env` is ignored by `.gitignore:3:.env`; `.env.example` is tracked.
- `.agents/` and `.claude/` contain duplicate local `smart-search-cli` skill files and are not product runtime code.
- `tests/test_llm_configured_client.py` fails because `crypto_alpha_agent.llm.configured` does not exist yet; this is a Phase 1 draft, not a Phase 0 deliverable.
- `docs/roadmap.md` and `docs/goals/project-completion-state.md` require Phase 0 to settle `.agents/`, `.claude/`, `.env`, and the draft LLM test before Phase 1.

**Subagent boundary:**

- A read-only explorer subagent audits the same Phase 0 blockers and reports before final implementation review. It must not modify files or print `.env` values.

## File Structure

- Modify `.gitignore`
  - Add `.agents/` and `.claude/` as shared ignore rules for local AI-tool installs.
- Modify `tests/test_cli_smoke.py`
  - Extend existing ignore-contract test to assert `.agents/` and `.claude/` are ignored.
- Delete `tests/test_llm_configured_client.py`
  - Remove the untracked failing Phase 1 draft. Phase 1 will recreate this intentionally under a Real LLM Adapter TDD plan.
- Modify `docs/runbook.md`
  - Add an operator baseline checklist for clean worktree state, local-only tool directories, ignored artifacts, and secret-safe local configuration.
- Modify `docs/roadmap.md`
  - Mark Immediate Phase 0 / merged Phase 6 as complete after this round and identify Immediate Phase 1 as next.
- Modify `docs/goals/project-completion-state.md`
  - Add the Phase 0 round record, evidence paths, verification results, and report link.
- Create `docs/goals/phase-reports/2026-05-23-phase-0-worktree-configuration-closeout-completion-report.md`
  - Record what happened, what was verified, reviews, secret-safety, and next Phase.

## Task 1: Ignore Local AI Tool Directories

**Files:**

- Modify: `.gitignore`
- Modify: `tests/test_cli_smoke.py`

- [ ] **Step 1: Update `.gitignore`**

Add these lines after `.env` rules and before cache/runtime ignores:

```gitignore
.agents/
.claude/
```

- [ ] **Step 2: Extend the existing ignore-contract test**

In `tests/test_cli_smoke.py`, update `test_repo_ignores_local_macos_and_cache_artifacts` so it includes:

```python
    assert ".agents/" in ignore_text
    assert ".claude/" in ignore_text
```

- [ ] **Step 3: Run focused test**

Run:

```bash
uv run --extra dev pytest tests/test_cli_smoke.py::test_repo_ignores_local_macos_and_cache_artifacts -q
```

Expected: one test passes.

- [ ] **Step 4: Verify ignore behavior**

Run:

```bash
git check-ignore -v .env .agents .claude
git status --short --ignored .env .agents .claude
```

Expected: `.env`, `.agents/`, and `.claude/` are ignored; none are staged.

## Task 2: Remove Premature Phase 1 Test Draft

**Files:**

- Delete: `tests/test_llm_configured_client.py`

- [ ] **Step 1: Delete the untracked failing draft**

Delete `tests/test_llm_configured_client.py`. This file belongs to Immediate Phase 1 and currently fails with:

```text
ModuleNotFoundError: No module named 'crypto_alpha_agent.llm'
```

- [ ] **Step 2: Verify it is gone**

Run:

```bash
test ! -e tests/test_llm_configured_client.py
git status --short tests/test_llm_configured_client.py
```

Expected: the `test ! -e` command exits 0 and `git status` prints no entry for that file.

## Task 3: Complete Operator Baseline Docs

**Files:**

- Modify: `docs/runbook.md`

- [ ] **Step 1: Add operator baseline checklist**

Add a section after the `Environment` section with these commitments:

- run `git status --short` before and after local runs;
- keep `.env`, `.agents/`, `.claude/`, `var/`, caches, local reports, SQLite files, logs, and screenshots out of git;
- treat `.agents/` and `.claude/` as local AI-tool installs, not product deliverables;
- list only variable names for local LLM/proxy settings;
- never stage provider headers, raw keys, memory dumps, reports, databases, or generated artifacts.

- [ ] **Step 2: Run documentation contract**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py -q
```

Expected: all documentation contract tests pass.

## Task 4: Synchronize Roadmap, State, And Phase Report

**Files:**

- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-23-phase-0-worktree-configuration-closeout-completion-report.md`

- [ ] **Step 1: Update roadmap**

Add a completed status note to `Immediate Phase 0` / `Phase 6` stating:

- `.agents/` and `.claude/` are local-only ignored tool directories;
- `.env` remains local and ignored;
- the failing Phase 1 draft test was deleted;
- Phase 1 Real LLM Adapter is next.

- [ ] **Step 2: Update project completion state**

Add a new current round for Phase 0 and move the previous round into history or retain it as history. Record:

- Phase name and date;
- Smart Search evidence paths;
- local feasibility findings;
- subagent audit summary;
- files changed;
- focused and full verification commands;
- secret-safety status;
- next Phase.

- [ ] **Step 3: Write the completion report**

Create `docs/goals/phase-reports/2026-05-23-phase-0-worktree-configuration-closeout-completion-report.md` with these sections:

```markdown
# Phase 0 Worktree Configuration Closeout Completion Report

## Summary
## Smart Search Evidence
## Local Feasibility
## Substep Validation
## Files Changed
## Subagents
## Review Passes
## Verification
## Secret Safety
## Remaining Gaps And Next Phase
```

## Task 5: Review, Fix, And Re-Review

**Files:**

- Review all changed Phase 0 files.

- [ ] **Step 1: Specification review**

Check the diff against the Phase 0 requirements in `docs/roadmap.md` and `docs/goals/project-completion-goal.md`.

Required result:

- Phase 0 only; no LLM adapter implementation.
- `.agents/`, `.claude/`, `.env`, and the draft test are resolved.
- State, roadmap, and completion report agree.

- [ ] **Step 2: Code-quality and safety review**

Check:

- docs are not contradictory;
- `.gitignore` rules do not hide committed deliverables;
- tests only assert repository hygiene;
- no secret values, provider URLs with credentials, databases, reports, screenshots, or local generated artifacts are staged.

- [ ] **Step 3: Fix Critical or Important findings**

If either review finds Critical or Important issues, fix them and rerun:

```bash
uv run --extra dev pytest tests/test_cli_smoke.py::test_repo_ignores_local_macos_and_cache_artifacts tests/test_documentation_contract.py -q
git diff --check
```

Expected: focused tests and diff check pass after fixes.

## Task 6: Final Verification, Secret Safety, Commit, And Push

**Files:**

- Stage only deliberate Phase 0 files.

- [ ] **Step 1: Run required verification**

Run:

```bash
uv run --extra dev pytest tests/test_cli_smoke.py::test_repo_ignores_local_macos_and_cache_artifacts tests/test_documentation_contract.py -q
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short
```

Expected:

- Focused tests pass.
- Full tests pass.
- Ruff passes.
- Diff check passes.
- `git status --short` shows only deliberate tracked Phase 0 changes before staging, and `.agents/`, `.claude/`, `.env` are not untracked.

- [ ] **Step 2: Stage only Phase 0 files**

Run:

```bash
git add .gitignore tests/test_cli_smoke.py docs/runbook.md docs/roadmap.md docs/goals/project-completion-state.md docs/goals/phase-reports/2026-05-23-phase-0-worktree-configuration-closeout-completion-report.md docs/superpowers/plans/2026-05-23-phase-0-worktree-configuration-closeout.md
```

Do not stage `.env`, `.agents/`, `.claude/`, `var/`, caches, generated reports, databases, logs, screenshots, or Phase 1 implementation files.

- [ ] **Step 3: Run staged checks**

Run:

```bash
git diff --cached --check
git diff --cached --name-only
git diff --cached --no-ext-diff --unified=0
secret_pattern='sk-[A-Za-z0-9]{16,}|api[.]wwcloud[.]app|127[.]0[.]0[.]1:10808|OPENAI_API_KEY=sk-[A-Za-z0-9._-]+|OPENAI_BASE_URL=https://api[.]wwcloud[.]app|BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]+'
git diff --cached --no-ext-diff --unified=0 | rg -n "$secret_pattern" || true
```

Expected:

- Staged names match only deliberate Phase 0 files.
- Staged diff has no whitespace errors.
- Staged grep prints no real secret values, no configured provider URL, no local proxy value, and no bearer/private-key material.

- [ ] **Step 4: Commit and push**

Run:

```bash
git commit -m "docs: complete phase 0 closeout"
git push
```

Expected:

- Commit succeeds.
- Push succeeds to `origin/main`.

## Out Of Scope

- No `src/crypto_alpha_agent/llm/` code.
- No real LLM calls.
- No `plan-experiments`, `research-loop`, or `evidence-report` LLM integration.
- No data-source or strategy expansion.
- No live trading, wallet/private key handling, exchange order routing, real capital, MEV, mempool, bridge race, flash-loan race, speed edge, premium RPC, or private infrastructure dependency.

## Self-Review

- Spec coverage: Every Phase 0 / merged Phase 6 requirement is mapped to a task and verification command.
- Placeholder scan: No incomplete placeholders remain; all files and commands are explicit.
- Scope check: This plan is one coherent Phase and does not start Phase 1.
- Consistency check: The plan deletes the failing Phase 1 draft now and requires Phase 1 to recreate tests under its own TDD plan.
