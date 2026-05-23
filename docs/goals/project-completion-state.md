# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 1
- Status: milestone published; final verification passed and GitHub push
  completed
- Started: 2026-05-17
- Completed: 2026-05-17 UTC / 2026-05-18 Asia-Shanghai local time
- Active slice: complete safe autonomous evidence system milestone
- Active plan source:
  `docs/superpowers/plans/2026-05-17-complete-autonomous-evidence-system.md`

## Completed This Round

- Completed degradation stop rules across `evidence-run`, `research-loop`,
  scheduler plans, and experiment planning.
- Added `rollout-review` so accumulated paper outcomes and validation evidence
  produce a rollout evaluation, tiny-live readiness artifact, and preserved
  strategy-specific evidence package while keeping live execution disabled.
- Hardened rollout evidence semantics:
  - blocked and `no_signal` paper outcomes do not satisfy rollout observation
    count;
  - failed and rejected outcomes feed the failure-rate gate;
  - unapproved validation evidence cannot make rollout gates pass;
  - duplicate canonical validation evidence cannot inflate walk-forward splits;
  - `max_observed_loss_usd` uses the conservative recorded or derived loss.
- Completed operator documentation for daily and weekly evidence operations,
  data ingestion, paper simulation, experiment planning, rollout review,
  replay/recovery, external cron/systemd handoff, logs, locks, failure
  notification, and artifact retention.
- Added a full local acceptance test proving:
  - `evidence-run`;
  - `research-loop --include-validation --include-paper-evidence --memory`;
  - `plan-experiments`;
  - `evidence-report --weekly`;
  - `rollout-review`.
- Strengthened acceptance coverage for source health, memory feedback, report
  contents, rollout artifact persistence, evidence package consistency,
  low-capital constraints, no-live flags, and unexpected network calls.
- Fixed final review findings:
  - TheGraph subgraph URLs are redacted from schedule plans and optional-source
    failure messages.
  - HTTP failure messages redact URLs before they can be surfaced in source
    health.
  - `RiskGuardian` no longer grants live execution authority under the current
    charter; even fully approved `gated_live` contexts are blocked with
    `live_execution_disabled_by_charter`.

## Verification Evidence

- Focused Task 16 checks:
  `uv run --extra dev pytest tests/test_rollout_readiness_cli.py tests/test_rollout_gates.py tests/test_live_readiness.py -q`
  passed with 40 tests.
- Focused Task 17 checks:
  `uv run --extra dev pytest tests/test_documentation_contract.py -q` passed
  with 7 tests.
- Focused Task 18 check:
  `uv run --extra dev pytest tests/test_complete_evidence_system.py -q` passed.
- Source coverage check:
  `uv run --extra dev pytest tests/test_binance_public_ingestion.py tests/test_ccxt_ingestion_service.py tests/test_defillama_dex_ingestion_service.py tests/test_onchain_ingestion_service.py -q`
  passed with 52 tests.
- Final review fix checks:
  `uv run --extra dev pytest tests/test_scheduler_cli.py tests/test_evidence_runner.py tests/test_risk_guardian.py tests/test_tool_retries.py -q`
  passed with 44 tests.
- Full tests:
  `uv run --extra dev pytest -q` passed with 750 tests.
- Ruff:
  `uv run --extra dev ruff check .` passed.
- Diff check:
  `git diff --check` passed.
- Forbidden-path check:
  `rg -n "create_order|private_key|seed phrase|send_transaction|live_order_routing.*True|touched_real_capital.*True" src tests docs README.md`
  returned only documentation safety wording, negative tests, and production
  denylist terms used to block unsafe behavior. It did not reveal production
  live execution authority.
- Pre-state staged diff check:
  `git diff --cached --check`, `git diff --cached --name-only`, and
  `git diff --cached --no-ext-diff --unified=0` were clean before state updates.
- Secret-safety review result:
  no `.env`, SQLite database, `var/` artifact, cache, generated report, API key,
  bearer token, private key, seed phrase, or wallet material was staged.
- Final commit hash: `fb1635d281f33e93a6723832bdf04a115e160c86`
- Public GitHub repository URL:
  `https://github.com/WW-shan/Crypto_Research_Agent`

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

None for the first complete research-loop milestone under the current charter.

Future work is now ordered as an evidence-factory buildout before the formal
evidence campaign:

- Immediate Phase 0 / Phase 6 merge: close the worktree and operator
  configuration state before Phase 1.
- Immediate Phase 1-3: connect the real local LLM and test it safely.
- Immediate Phase 4-5: keep evidence-run infrastructure operable while
  preparing data and strategy expansion.
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

If work continues after this milestone:

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
5. Start with Immediate Phase 0 before implementing the LLM adapter:
   cleanly decide the `.agents/` and `.claude/` boundary, keep `.env` ignored,
   keep local LLM and proxy variables local, and either delete or intentionally
   incorporate the current `tests/test_llm_configured_client.py` draft into the
   approved Phase 1 plan.
6. Treat live execution, wallet keys, exchange order routing, private RPC,
   MEV, and speed-edge paths as blocked unless the owner explicitly revises the
   charter.
7. Connect the owner's local real LLM configuration before treating long-running
   evidence collection as operational. The preferred model routing is
   `gpt-5.5` for research/planning/code and `gpt-5.4-mini` for fast
   summaries.
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
