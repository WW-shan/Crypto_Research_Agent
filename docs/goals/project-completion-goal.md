# Project Completion Goal

This document is the persistent Codex Goal contract for completing the Crypto
Alpha Agent project. Use it with the Codex `goals` feature as the long-running
outer loop for the repository.

## Goal Prompt

Start a Goal session from the repository root with:

```text
/goal Follow docs/goals/project-completion-goal.md until the project reaches the final definition of done. At the end of each round, update docs/goals/project-completion-state.md and docs/roadmap.md, then continue with the next gap.
```

## Mission

Continue improving the project until it fully satisfies the original design:
a low-capital crypto alpha research system that continuously ingests public
data, validates charter-compliant strategy families, accumulates paper evidence,
uses AI only for bounded research planning and critique, produces daily and
weekly operator decisions, and keeps live execution blocked unless a future
charter revision explicitly authorizes it.

The project is complete only when the final definition of done in this document
passes against the current code, tests, documentation, and local operator
workflow.

## Binding Sources

Read these at the start of every Goal round:

1. `docs/project-charter.md`
2. `docs/roadmap.md`
3. `docs/runbook.md`
4. `docs/rollout-gates.md`
5. `docs/project-asset-assessment.md`
6. `docs/tiny-live-readiness.md`
7. `docs/superpowers/plans/*.md`
8. `docs/goals/project-completion-state.md`
9. Current source and test tree under `src/` and `tests/`

When sources conflict, use this priority:

1. `docs/project-charter.md`
2. This Goal contract
3. `docs/roadmap.md`
4. `docs/project-asset-assessment.md`
5. Newer implementation plans
6. Older implementation plans
7. Existing implementation details

Older plans must be interpreted through the current charter. Do not revive speed
arbitrage, MEV, premium infrastructure, wallet access, or live execution paths
from older language.

## Hard Boundaries

Never implement or commit:

- Wallet private-key loading, seed phrase handling, unrestricted signing, or
  live on-chain transaction submission.
- Exchange live order routing or real-capital execution.
- MEV, mempool extraction, sandwiching, bridge races, flash-loan races, or
  sub-second CEX-DEX arbitrage.
- Dependencies that make paid data, premium RPC, colocation, private order flow,
  or large balance sheets required infrastructure.
- Automatic promotion from research or paper evidence to live execution.
- Secrets in git, logs, docs, reports, test fixtures, or screenshots.

If a task requires any forbidden path, stop that task, record the blocker in the
state file, and choose the next charter-compliant gap.

## Secret And LLM Test Policy

Real LLM credentials are local operator configuration only. They may exist in a
gitignored `.env`, but they must never be committed, printed, copied into docs,
or placed in test fixtures.

Use these environment variable names for Responses-compatible LLM tests and
operator runs:

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_API_TYPE=responses
OPENAI_MODEL=
OPENAI_RESEARCH_MODEL=
OPENAI_CODER_MODEL=
OPENAI_FAST_MODEL=
```

Use these environment variable names for local public-data proxy routing when
direct access to ordinary public crypto APIs is blocked, slow, or unreliable:

```env
HTTP_PROXY=
HTTPS_PROXY=
ALL_PROXY=
http_proxy=
https_proxy=
all_proxy=
NO_PROXY=
no_proxy=
CRYPTO_ALPHA_AGENT_PROXY=
```

The proxy is local operator configuration. It may be used for source probes,
historical data ingestion, and daily evidence runs, but it must not become a
speed edge, private RPC dependency, live-trading path, or secret-bearing
artifact. Source-health records must distinguish direct success, proxy success,
and provider/source failure.

The owner preference is to use the real configured LLM for positive integration
and smoke tests when credentials are available. Do not skip real LLM calls
merely to save token budget during local development after the owner has
requested real-model testing.

Keep fake or injected LLM tests only for deterministic adversarial cases that a
real model cannot be expected to produce reliably on demand, including invalid
JSON, schema violations, live-order requests, wallet/private-key requests, MEV
or premium-RPC requests, high-capital requests, and malicious text that must be
rejected by guards.

A real LLM integration test may run only when all of these are true:

- `.env` or the shell provides the required variables.
- The test is explicitly marked as an integration test.
- The command or local environment explicitly opts into integration tests when
  running in CI or other shared automation. Local owner-directed development may
  run real LLM smoke tests by default after credentials are configured.
- The test never prints the key or raw provider headers.
- The test verifies that the key and configured provider URL are not copied into
  stdout, stderr, memory, reports, generated artifacts, or staged diffs.
- Failure of the external provider is reported as an integration environment
  problem, not hidden as a product success.

## Per-Round Execution Protocol

Each Goal round must complete exactly one roadmap Phase or one explicitly named
Immediate Phase before moving on. Do not half-finish a plan and start another.
If a Phase is too large for one safe round, split it into named sub-slices in
the plan, but the round still owns only that Phase and must not begin the next
Phase until the current one passes all review and verification gates.

1. **Load context.** Read the binding sources and inspect the current code,
   tests, CLI commands, and git state.
2. **Run Smart Search before design.** Before starting any new design, plan, or
   implementation work for the round, run one Smart Search deep-research pass
   for the selected problem area or likely Phase. Save or cite the query,
   evidence path, and key external findings in the plan or state file. Use
   fetched/source-backed evidence for current API, data-source, library,
   workflow, or methodology claims. If Smart Search cannot reach a needed
   provider, record the failure and either fetch primary sources by another
   approved path or mark the external claim as unverified.
3. **Verify code feasibility.** After Smart Search and before Superpowers plan
   writing, inspect the local source, tests, CLI commands, schemas, docs, and
   current git state to decide whether the externally suggested approach fits
   the actual repository. Record the feasibility result, likely files, existing
   patterns to reuse, and blockers in the plan or state file.
4. **Apply the evidence-first substep gate.** For every meaningful substep that
   adds or changes a capability, repeat the same discipline at the substep
   level before implementation:
   external evidence first, then local data/code feasibility, then a small
   validation or prototype when practical, then formal project implementation.
   For data sources, prove the source is reachable and parseable before adding
   it as a dependency. For strategy validators, prove the required fields exist
   in qualified data and run a small historical feasibility check before adding
   the validator to the library. For LLM, report, memory, scheduler, or risk
   changes, prove the existing contracts and tests can support the change
   before editing product code. If the check fails, record the idea as rejected
   or blocked with reasons instead of implementing it.
5. **Audit gaps.** Compare the current repository against the final definition
   of done and the active roadmap. Record the material gaps in the state file.
6. **Select one Phase.** Choose the current roadmap Phase or Immediate Phase
   that should be completed next. Do not skip Immediate Phase 0 when the
   worktree, local configuration, or accidental draft files are not settled.
   Phase 6 is merged into the Immediate Phase 0 / Immediate Phase 1 entry
   gate. After the immediate LLM work, build Phases 8, 9, 10, 11, and 12
   before starting the formal Phase 7 evidence campaign. Phase 7 uses
   historical bootstrap plus future out-of-sample observations only after the
   data, validators, cost model, AI researcher, and governance layers are
   strong enough to make evidence meaningful. Phase 13 is the ongoing review of
   generated research reports and artifacts for practical effectiveness. It is
   read-only review and reporting, not code implementation or live-trading
   implementation.
7. **Use subagents.** Use at least one subagent every round for gap audit,
   implementation, or review. Use multiple subagents when the slice has
   independent parallelizable parts. Give each subagent a disjoint ownership
   boundary for implementation work. Do not let subagents revert unrelated work.
8. **Use Superpowers workflows.** Every process must follow the applicable
   Superpowers skill before taking action:
   brainstorming for design changes, writing-plans for multi-step plans,
   test-driven-development for features and bug fixes, subagent-driven
   development or executing-plans for implementation, requesting-code-review
   and receiving-code-review for review cycles, systematic-debugging for test
   failures or unexpected behavior, and verification-before-completion before
   any completion claim.
9. **Plan the Phase.** Write or update a concrete plan in
   `docs/superpowers/plans/` for the selected Phase before implementation. The
   plan must identify files, tests, verification commands, review gates,
   subagent boundaries, Smart Search evidence, code-feasibility findings,
   substep validation or prototype results, rejected or blocked candidates,
   real-LLM usage, and secret-safety checks. Do not execute the Phase until the
   plan is written and accepted by the owner when the owner asks for plan-first
   execution.
10. **Implement with tests.** Add focused failing tests first where practical,
   then implementation, then documentation updates. Real LLM positive
   integration tests should use the configured local LLM after the real LLM
   adapter exists; fake LLM tests remain for deterministic unsafe-output cases.
11. **Review repeatedly.** Run at least two review passes for every Phase: one
   specification/requirements review and one code-quality/safety review. Fix
   all Critical or Important issues. After any such fix, rerun focused tests and
   request re-review until reviewers report no Critical or Important issues.
12. **Synchronize state after partial completion.** Whenever a meaningful
   sub-slice of the Phase is completed, update
   `docs/goals/project-completion-state.md` with what changed, what was
   verified, what remains, and whether the Phase may continue. Also update
   `docs/roadmap.md` when the public roadmap has changed. State updates must be
   part of the round's final commit.
13. **Write a Phase completion report.** Before a Phase can be marked complete,
    create a Markdown report under `docs/goals/phase-reports/` named
    `YYYY-MM-DD-phase-<phase-or-immediate-phase>-completion-report.md`. The
    report must be complete enough for a future agent or owner to know what
    happened without rereading the whole conversation. Include:
    - Phase name, date, commit or pending commit reference, owner objective, and
      whether this was implementation, review-only, or documentation-only.
    - Smart Search query, evidence paths, fetched sources, and external
      findings used before design.
    - Local code/data feasibility findings, files inspected, existing patterns
      reused, and blockers found.
    - Substep validation or prototype results, including rejected or blocked
      candidates and exact blocked reasons.
    - Files changed, tests added or updated, docs changed, and artifacts
      produced.
    - Subagents used, their assignments, and how their findings were reviewed.
    - Review passes, Critical or Important findings, fixes, and re-review
      status.
    - Verification commands and exact pass/fail results.
    - Secret-safety result and confirmation that `.env`, keys, databases,
      reports, caches, and local artifacts were not staged.
    - Remaining gaps, next Phase recommendation, and any owner decisions
      required.
    Link this report from `docs/goals/project-completion-state.md` before the
    round's final commit.
14. **No next Phase until clean.** Do not enter the next Phase until the current
    Phase has passing focused tests, required full verification, completed
    review/fix/re-review cycles, clean secret-safety checks, updated state and
    roadmap docs, a linked Phase completion report, an intentional commit, a
    GitHub push, and no unresolved Critical or Important findings.
15. **Verify.** Run the required verification commands for the Phase and the
    full project commands listed below.
16. **Commit.** Commit the completed Phase, including state, roadmap, and Phase
    completion report updates, with an intentional message.
17. **Publish.** Push the commit to GitHub. Use the existing remote when present;
    otherwise create a public GitHub repository and push the branch.
18. **Continue or stop.** If the final definition of done still has unmet items,
    start the next round from the next roadmap Phase. Stop only when all final
    criteria pass or a hard blocker requires owner input.

## Required Verification

Before claiming a round is complete, run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
git diff --check
git status --short
git diff --cached --name-only
```

Also run any focused tests named by the active implementation plan.

Before committing, run a concrete secret-safety check over staged files:

```bash
git diff --cached --check
git diff --cached --name-only
git diff --cached --no-ext-diff --unified=0
```

Read the staged diff and verify that it does not contain API keys, bearer
tokens, private keys, seed phrases, `.env` contents, local database dumps, or
generated report artifacts. If a secret-scanning tool is installed locally, run
it as well and record the command in the state file.

If an external integration test is needed, run it separately and report whether
it used real network or LLM credentials. Do not make full project completion
depend on a flaky external provider when a deterministic fake adapter can prove
the local contract.

## GitHub Publishing Policy

After each completed slice:

1. Stage only files that belong to the slice.
2. Confirm `.env`, local databases, reports under `var/`, caches, and generated
   local artifacts are not staged.
3. Commit locally.
4. Push to GitHub.
5. If no remote exists, create a public repository for this project and push to
   it.
6. Prefer a branch and pull request for future multi-commit feature work. For
   this owner-directed project, direct pushes to the main project repository are
   acceptable only when the slice is self-contained, verified, and contains no
   secrets.

## Final Definition Of Done

The project is complete when all of the following are true:

1. Real public-data ingestion supports the ordinary-infrastructure sources in
   the charter, including Binance Public Data, CCXT OHLCV and funding,
   DexScreener snapshots, DefiLlama fundamentals, and optional slow Dune or
   TheGraph evidence when credentials are available.
2. Source qualification can distinguish `Candidate`, `Reachable`,
   `ReachableViaProxy`, `Parseable`, `ResearchUsable`, and
   `ProductionResearchSource` states, and can record whether each source was
   reached directly or through the local proxy.
3. Stored data is normalized into durable local SQLite records with source
   health and data quality reporting.
4. Scanner signals, anomaly detection, hypothesis generation, deterministic
   reflection, validation, memory persistence, and Markdown/JSON reports run as
   a repeatable local workflow.
5. Registered strategy families cover the initial roadmap set:
   funding extremity plus price confirmation, funding mean reversion after
   extremes, DeFi yield regime watchlist, and DEX liquidity/volume watchlist.
6. Historical validators produce consistent strategy-family reports with fees,
   slippage, trade counts where applicable, max drawdown where applicable,
   expectancy, walk-forward or out-of-sample evidence, and stable rejection
   reasons.
7. Paper simulation runs only for historically approved, charter-compliant
   strategy candidates and records blocked outcomes when evidence is missing.
8. Paper outcome ledgers, validation ledgers, paper evidence packages, and memory
   feedback accumulate evidence without losing failed assumptions.
9. Daily and weekly evidence reports answer what improved, what degraded, what
   is blocked, what should stop, and what the next bounded experiment should be.
10. The AI experiment planner reads evidence and memory to propose bounded
   research experiments only against registered validators and available data.
11. Degradation and stop rules prevent repeated testing of weak or worsening
    strategy families.
12. Rollout review can generate passing or blocking tiny-live readiness
    artifacts from accumulated offline evidence, while keeping
    `live_execution_enabled=false`.
13. Operator docs describe the safe local workflow, including data ingestion,
    evidence runs, paper simulation, reports, experiment planning, rollout
    review, replay/recovery, and forbidden paths.
14. The formal evidence campaign runs after the data, strategy, cost, AI
    researcher, and governance layers are ready, starting with historical
    bootstrap and continuing into 30/60/90 out-of-sample paper evidence targets.
15. Continuous effectiveness review can inspect reports, evidence packages,
    AI memos, scoreboards, stopped-family ledgers, and finished artifacts, then
    produce review reports and explicit keep/stop/redesign/add-data/pause
    decisions tied to evidence rather than narrative alone. This criterion is
    satisfied by review artifacts, not product-code changes.
16. `uv run --extra dev pytest -q` passes.
17. `uv run --extra dev ruff check .` passes.
18. `git diff --check` passes.
19. Secret scans and git status confirm no credentials, local `.env`, SQLite
    databases, caches, or generated report artifacts are staged or committed.
20. The repository is pushed to a public GitHub repository.
21. `docs/roadmap.md` and `docs/goals/project-completion-state.md` say there are
    no remaining charter-compliant gaps for the current project vision.

## Current Recommended First Gap

At the time this Goal contract was written, the broad project had implemented
many evidence-factory components, but the full autonomous completion target was
not yet proven. The first Goal round should audit the repository against
`docs/superpowers/plans/2026-05-17-complete-autonomous-evidence-system.md`,
then continue with the earliest incomplete final integration criterion, likely
one of:

- `evidence-run`
- `plan-experiments`
- `evidence-report`
- `rollout-review`
- daily/weekly evidence reporting
- documentation truth alignment after the latest code changes

Use the audit result, not this hint, as the source of truth.
