# Phase 14 Completion Report: LLM-Native Autonomous Iteration Controller

Date: 2026-05-29

## Scope

Phase 14 adds the first safe autonomy increment for the owner's broader target:
an LLM-native command that turns current project evidence into guarded next-step
candidates.

The new command is `iteration-cycle`. It requires the real LLM runtime gate,
passes an evidence context to the configured planning LLM, parses strict
`IterationCandidate` JSON, and then applies deterministic constraints before
writing Markdown and JSON artifacts.

## Delivered

- Added `src/crypto_alpha_agent/pipeline/iteration_controller.py`.
- Added strict `IterationCandidate`, batch, task, and report models.
- Added evidence-ref validation for AI research context refs plus the owner
  autonomy target refs.
- Added deterministic rejection for live capital, live order routing, direct
  code-write authorization, missing required tests, missing code target files,
  missing source discovery queries, missing source probe targets, and charter
  guard violations.
- Added `render_iteration_cycle_markdown`.
- Added the `iteration-cycle` CLI command with fixed planning LLM role,
  Markdown output, JSON output, and real-runtime metadata.
- Added tests for accepted safe candidates, unsafe candidate rejection, Markdown
  rendering, CLI output, and documented parser examples.
- Updated roadmap, runbook, and project completion state.

## Boundary

This phase does not make the tool self-coding.

- `auto_executes_changes=false`.
- autonomous code-writing loop remains proposal-only.
- autonomous new data source discovery remains probe-gated.
- Accepted candidates require human review and separate TDD implementation.
- The command never runs generated code, starts scheduler jobs, promotes a
  `ProductionResearchSource`, places orders, reads wallet keys, or deploys
  live capital.

Deterministic modules remain inside the LLM-native flow as constraints:
schema validation, evidence refs, source quality facts, strategy registry facts,
paper/governance facts, risk guard checks, and secret-safe artifact writing.
They cannot create a successful product run without the real LLM runtime gate.

## Smart Search Evidence

Research evidence was collected before implementation under:

`/tmp/smart-search-evidence/20260529-phase14-autonomous-iteration/`

Included evidence covered structured LLM outputs, AI agent guardrails,
prompt-injection risk, GitHub Actions hardening, and agent evaluation guidance.
One OpenAI guardrails URL fetch failed, so the design relied on the available
OpenAI, OWASP, and GitHub sources already captured in that evidence directory.

## Verification

Verification completed during implementation:

- Baseline worktree full suite: `uv run --extra dev pytest -q` -> 958 passed.
- Controller focused tests: `uv run --extra dev pytest tests/test_iteration_controller.py -q` -> 5 passed.
- CLI parser tests:
  `uv run --extra dev pytest tests/test_iteration_cycle_cli.py tests/test_documentation_contract.py::test_documented_representative_cli_examples_parse -q`
  -> 2 passed.
- Documentation contract tests:
  `uv run --extra dev pytest tests/test_documentation_contract.py -q` -> 10 passed.
- Focused Phase 14 tests:
  `uv run --extra dev pytest tests/test_iteration_controller.py tests/test_iteration_cycle_cli.py tests/test_documentation_contract.py -q`
  -> 16 passed.
- Full suite: `uv run --extra dev pytest -q` -> 965 passed.
- Lint: `uv run --extra dev ruff check .` -> passed.
- Diff whitespace check: `git diff --check` -> passed.

Final staged review and secret scan are required immediately before the commit:
`git diff --cached --check`, `git diff --cached --name-only`,
`git diff --cached --no-ext-diff --unified=0`, and
`uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`.

## Remaining Gaps

Phase 14 starts the auto-iteration loop but does not complete the full owner
autonomy target.

- Autonomous code-writing remains proposal-only.
- Autonomous new data source discovery remains source-probe gated.
- Repeated evidence-driven implementation loops still need a future controller
  that can take an accepted candidate, open a separate TDD implementation plan,
  run verification, and return the result to the evidence ledger without
  bypassing human review.
- The 30/60/90 out-of-sample evidence campaign still needs real operation over
  time.
- Live execution remains blocked by the current charter.
