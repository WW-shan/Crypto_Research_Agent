# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 6
- Status: Immediate Phase 4 complete; commit and push pending
- Started: 2026-05-23
- Completed: 2026-05-23
- Active slice: Immediate Phase 4: Evidence Run Infrastructure
- Active plan source:
  `docs/superpowers/plans/2026-05-23-phase-4-evidence-run-infrastructure.md`
- Phase report:
  `docs/goals/phase-reports/2026-05-23-phase-4-evidence-run-infrastructure-completion-report.md`

## Completed This Round

- Ran Phase 4 Smart Search deep research and fetched Python standard-library
  documentation for exclusive file creation, atomic replace, and JSON
  serialization.
- Verified local feasibility from the current worktree:
  - `evidence-run` already ran the pipeline but overwrote the research-loop
    Markdown report with the daily evidence report;
  - no durable run manifest, product-level lock, failed marker, or latest
    pointer existed;
  - source health did not record network route;
  - optional slow-source redaction did not cover parameter and variable values.
- Added `crypto_alpha_agent.pipeline.evidence_run_ops` with exclusive local
  locking, atomic JSON/text artifact writes, network-route detection, redacted
  manifest input handling, and failed-message redaction.
- Updated `evidence-run` to:
  - use a database-root lock by default;
  - write separate daily and research-loop Markdown reports;
  - write JSON payload, manifest, latest pointers, and failed-run markers;
  - return nonzero exit code `2` for lock contention, path collisions, thrown
    failures, and failed core pipeline steps;
  - reject artifact path collisions before the pipeline runs;
  - generate unique run ids for fast retries.
- Updated source health to record direct/proxy/blocked/not-applicable network
  route and to redact URLs, API keys, Dune parameter values, Graph variable
  values, and Graph query text from source failures.
- Updated README, runbook, and roadmap for the new operator command set,
  product-level lock, manifest paths, failed marker, and retention expectations.

## Verification Evidence

- Smart Search:
  `/tmp/smart-search-evidence/2026-05-23-phase4-evidence-run-infrastructure/`
  contains `00-doctor.json`, `01-deep-plan.json`, `02-python-os-open.md`,
  `03-python-os-replace.md`, and `04-python-json.md`. Doctor reported the main
  route timed out but source fetch and documentation capability were usable.
- Local prototype:
  exclusive `os.open(..., O_CREAT | O_EXCL | O_WRONLY)` detected lock
  contention and `os.replace` produced atomic JSON replacement.
- Initial focused runner baseline:
  `uv run --extra dev pytest tests/test_evidence_runner.py -q` passed with 8
  tests before Phase 4 changes.
- Phase 4 RED/GREEN coverage added for lock contention, atomic latest pointer
  updates, network route, core failure redaction, distinct report artifacts,
  manifest/json/latest artifact writes, failed markers, configured secret
  redaction, default DB-root locking across report directories, artifact path
  collisions, unique generated run ids, and slow-source failure redaction.
- Focused Phase 4 runner verification:
  `uv run --extra dev pytest tests/test_evidence_runner.py -q` passed with 19
  tests.
- Broader focused verification:
  `uv run --extra dev pytest tests/test_scheduler_cli.py tests/test_documentation_contract.py -q`
  passed with 17 tests.
- Complete/degradation verification:
  `uv run --extra dev pytest tests/test_complete_evidence_system.py::test_complete_safe_autonomous_evidence_system tests/test_evidence_degradation.py -q`
  passed with 16 tests.
- Review pass 1 found Critical issues in manifest secret redaction and default
  lock scoping plus Important artifact-path and run-id risks. Those were fixed
  with regression tests. Re-review found no remaining Critical or Important
  findings.
- Full verification:
  `uv run --extra dev pytest -q` passed with 797 tests after a transient real
  LLM summary rejection passed on immediate single-test rerun; `uv run --extra
  dev ruff check .` passed; `git diff --check` passed.
- Staged checks and staged secret-safety remain required before the Phase 4
  commit and push.

## Current Project Target

The first complete safe research-loop milestone is complete for the current
charter:

- public-data ingestion;
- local durable SQLite storage;
- scanner and anomaly detection;
- hypothesis generation and reflection;
- deterministic historical validation;
- paper simulation and evidence accumulation;
- validation and paper memory feedback;
- daily and weekly evidence reports;
- bounded AI experiment planning;
- degradation and stop rules;
- rollout review artifacts with `live_execution_enabled=false`.

## Known Hard Boundaries

- No wallet-key access.
- No live order routing.
- No exchange order submission.
- No real-capital execution.
- No MEV, mempool, bridge-race, flash-loan, premium-RPC, or speed-edge
  strategies.
- No secrets in git or public GitHub.

## Known Remaining Gaps

The first complete research-loop milestone remains complete under the current
charter. Post-milestone Phase 0, Immediate Phase 1, Immediate Phase 2,
Immediate Phase 3, and Immediate Phase 4 are complete. Phase 4 still requires
staged checks, staged secret-safety, commit, and push before the next Phase may
start.

Future work is now ordered as an evidence-factory buildout before the formal
evidence campaign:

- Immediate Phase 5: start data and strategy expansion after the Phase 4
  infrastructure commit is pushed.
- Phase 8: qualify and deepen public data sources, including proxy-aware
  source probes.
- Phase 9: expand deterministic strategy validators and watchlists.
- Phase 10: make paper/backtest results execution-realistic after costs.
- Phase 11: upgrade the AI researcher to reason from evidence without bypassing
  validators.
- Phase 12: add portfolio/governance scoring for profit/no-profit decisions.
- Phase 7: only after Phases 8-12, run historical bootstrap and then collect
  future out-of-sample paper observations.
- Phase 13: perform read-only review of generated reports, evidence packages,
  AI memos, strategy scoreboards, and finished artifacts, then write review
  reports and decision records that judge whether the system is improving
  profit research effectiveness.

Live execution remains outside the current charter until a future explicit
charter revision.

## Next Round Entry Instructions

If work continues after Phase 4:

1. Read `docs/project-charter.md` before any new plan.
2. Read `docs/goals/project-completion-goal.md` and follow its Per-Round
   Execution Protocol exactly: Smart Search deep research before design,
   local code-feasibility verification before planning, evidence-first substep
   gates for every meaningful added capability, one Phase per round,
   Superpowers workflows, subagent use, repeated review/fix/re-review cycles,
   state synchronization, a complete Phase report under
   `docs/goals/phase-reports/`, and no next Phase until the current Phase is
   clean, verified, committed, and pushed.
3. Read the "Immediate Sequence: Worktree Then Real LLM" section in
   `docs/roadmap.md`.
4. Treat Phase 6 as merged into Immediate Phase 0 / Immediate Phase 1 entry
   readiness, not as a later standalone feature phase.
5. Start with Immediate Phase 5: Data And Strategy Expansion. Phase 4 added
   evidence-run manifests, locking, failed markers, artifact latest pointers,
   and source-health route/redaction. Do not reimplement Phase 1, Phase 2,
   Phase 3, or Phase 4.
6. Treat live execution, wallet keys, exchange order routing, private RPC,
   MEV, and speed-edge paths as blocked unless the owner explicitly revises the
   charter.
7. Use the Phase 1/2 model routing: research/planning/code use the configured
   strong model and report/summary use the configured fast model. Preserve fake
   LLM tests for deterministic adversarial cases, and make real positive tests
   explicit and secret-safe.
8. Use the local proxy variables in `.env` for public-data endpoints that fail
   direct probing, and record source health as direct, proxy, or failed.
9. Build Phase 8, Phase 9, Phase 10, Phase 11, and Phase 12 before starting the
   formal Phase 7 evidence campaign.
10. In Phase 7, first run historical bootstrap over qualified data, then treat
    future daily evidence as out-of-sample confirmation or rejection.
11. Use Phase 13 as a read-only report/artifact effectiveness review loop that
    produces review reports and decision records, not as a code implementation
    or tiny-live phase.
12. Prefer evidence-factory quality and validator expansion over new agent
    framework work.
13. Keep failed evidence and rejected assumptions in memory.
14. Update this file and `docs/roadmap.md` after any future milestone.

## Round History

| Round | Date | Slice | Verification | Commit | GitHub |
| --- | --- | --- | --- | --- | --- |
| 0 | 2026-05-17 | Goal contract bootstrap | pytest 676 passed; ruff passed; diff check passed; staged secret review passed | Goal bootstrap docs slice | public repo target |
| 1 | 2026-05-17 UTC / 2026-05-18 local | Complete autonomous evidence system milestone | pytest 750 passed; ruff passed; diff check passed; focused source tests 52 passed; forbidden-path review found no production live path | `fb1635d281f33e93a6723832bdf04a115e160c86` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 2 | 2026-05-23 | Immediate Phase 0 / merged Phase 6 worktree and configuration closeout | focused Phase 0 checks 8 passed; pytest 750 passed; ruff passed; diff check passed; staged secret review passed | Phase 0 completion commit `docs: complete phase 0 closeout` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 3 | 2026-05-23 | Immediate Phase 1 real LLM adapter | tests 762 passed; ruff passed; diff check passed; staged secret review passed | Phase 1 completion commit `feat: add real llm adapter` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 4 | 2026-05-23 | Immediate Phase 2 connect LLM to research loop | tests 770 passed; ruff passed; diff check passed; staged secret review passed | `ae3e601 feat: connect llm to research loop` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 5 | 2026-05-23 | Immediate Phase 3 real LLM test policy | focused Phase 3 tests 16 passed; pytest 785 passed; ruff passed; diff check passed; staged secret review passed | `9fb1945 test: formalize real llm policy` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 6 | 2026-05-23 | Immediate Phase 4 evidence run infrastructure | focused Phase 4 runner tests 19 passed; scheduler/docs 17 passed; complete/degradation 16 passed; pytest 797 passed; ruff passed; diff check passed | pending Phase 4 commit `feat: add evidence run infrastructure` | `https://github.com/WW-shan/Crypto_Research_Agent` |
