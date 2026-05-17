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
5. `docs/tiny-live-readiness.md`
6. `docs/superpowers/plans/*.md`
7. `docs/goals/project-completion-state.md`
8. Current source and test tree under `src/` and `tests/`

When sources conflict, use this priority:

1. `docs/project-charter.md`
2. This Goal contract
3. `docs/roadmap.md`
4. Newer implementation plans
5. Older implementation plans
6. Existing implementation details

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

Use these environment variable names for optional Responses-compatible LLM
tests:

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_API_TYPE=responses
```

Default tests must use fake or injected adapters. A real LLM integration test
may run only when all of these are true:

- `.env` or the shell provides the required variables.
- The test is explicitly marked as an integration test.
- The command explicitly opts into integration tests.
- The test never prints the key or raw provider headers.
- Failure of the external provider is reported as an integration environment
  problem, not hidden as a product success.

## Per-Round Execution Protocol

Each Goal round must complete one coherent implementation slice before moving
on. Do not half-finish a plan and start another.

1. **Load context.** Read the binding sources and inspect the current code,
   tests, CLI commands, and git state.
2. **Audit gaps.** Compare the current repository against the final definition
   of done and the active roadmap. Record the material gaps in the state file.
3. **Select one slice.** Choose the highest-impact, smallest coherent slice that
   moves the project toward the final definition of done.
4. **Use subagents.** Use at least one subagent every round for gap audit,
   implementation, or review. Use multiple subagents when the slice has
   independent parallelizable parts. Give each subagent a disjoint ownership
   boundary for implementation work. Do not let subagents revert unrelated work.
5. **Plan the slice.** Write or update a concrete plan in
   `docs/superpowers/plans/` when the slice is large enough to need one. Smaller
   slices may be recorded directly in `project-completion-state.md`.
6. **Implement with tests.** Add focused failing tests first where practical,
   then implementation, then documentation updates.
7. **Review.** Review the diff against the selected slice, the charter, and
   secret-safety requirements. Fix all Critical or Important issues.
8. **Update state.** Update `docs/goals/project-completion-state.md` and
   `docs/roadmap.md` with what changed, evidence, remaining gaps, and the next
   smallest useful slice before verification, commit, and push.
9. **Verify.** Run the required verification commands for the slice and the full
   project commands listed below.
10. **Commit.** Commit the completed slice, including state and roadmap updates,
    with an intentional message.
11. **Publish.** Push the commit to GitHub. Use the existing remote when present;
    otherwise create a public GitHub repository and push the branch.
12. **Continue or stop.** If the final definition of done still has unmet items,
    start the next round. Stop only when all final criteria pass or a hard
    blocker requires owner input.

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
2. Stored data is normalized into durable local SQLite records with source
   health and data quality reporting.
3. Scanner signals, anomaly detection, hypothesis generation, deterministic
   reflection, validation, memory persistence, and Markdown/JSON reports run as
   a repeatable local workflow.
4. Registered strategy families cover the initial roadmap set:
   funding extremity plus price confirmation, funding mean reversion after
   extremes, DeFi yield regime watchlist, and DEX liquidity/volume watchlist.
5. Historical validators produce consistent strategy-family reports with fees,
   slippage, trade counts where applicable, max drawdown where applicable,
   expectancy, walk-forward or out-of-sample evidence, and stable rejection
   reasons.
6. Paper simulation runs only for historically approved, charter-compliant
   strategy candidates and records blocked outcomes when evidence is missing.
7. Paper outcome ledgers, validation ledgers, paper evidence packages, and memory
   feedback accumulate evidence without losing failed assumptions.
8. Daily and weekly evidence reports answer what improved, what degraded, what
   is blocked, what should stop, and what the next bounded experiment should be.
9. The AI experiment planner reads evidence and memory to propose bounded
   research experiments only against registered validators and available data.
10. Degradation and stop rules prevent repeated testing of weak or worsening
    strategy families.
11. Rollout review can generate passing or blocking tiny-live readiness
    artifacts from accumulated offline evidence, while keeping
    `live_execution_enabled=false`.
12. Operator docs describe the safe local workflow, including data ingestion,
    evidence runs, paper simulation, reports, experiment planning, rollout
    review, replay/recovery, and forbidden paths.
13. `uv run --extra dev pytest -q` passes.
14. `uv run --extra dev ruff check .` passes.
15. `git diff --check` passes.
16. Secret scans and git status confirm no credentials, local `.env`, SQLite
    databases, caches, or generated report artifacts are staged or committed.
17. The repository is pushed to a public GitHub repository.
18. `docs/roadmap.md` and `docs/goals/project-completion-state.md` say there are
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
