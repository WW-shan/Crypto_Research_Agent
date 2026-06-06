# Project Completion State

This file is the working memory for the long-running Codex Goal defined in
`docs/goals/project-completion-goal.md`. Update it at the end of every completed
round.

## Current Round

- Round: 18
- Status: Phase 17 Creation-First Codex Autonomy complete and verified in the
  closeout worktree; owner merge/PR decision remains
- Started: 2026-06-06
- Completed: 2026-06-06
- Active slice: Phase 17: Creation-First Codex Autonomy
- Active plan source:
  `docs/superpowers/plans/2026-05-30-phase-17-creation-first-codex-autonomy.md`
- Phase report:
  `docs/goals/phase-reports/2026-06-06-phase-17-creation-first-codex-autonomy-completion-report.md`

## Completed This Round

- Added the Phase 17 design spec and implementation plan for creation-first
  Codex autonomy.
- Added the `crypto_alpha_agent.autonomy` package with strict creation models,
  task artifact storage, bounded report-context loading, Codex execution,
  worktree management, prompts, and the `run_creation_cycle` orchestrator.
- Added the `creation-cycle` CLI command. Product execution uses the configured
  real LLM planning role and requires Codex availability before starting.
- Added creation-cycle Markdown/JSON report output under
  `var/reports/creation/latest.md` and `var/reports/creation/latest.json`.
- Added persistent creation state under `var/autonomy/backlog.jsonl`,
  `var/autonomy/tasks/`, and `var/autonomy/active-worktree`.
- Added `ops/creation-cycle.sh`,
  `ops/systemd/crypto-alpha-creation.service`, and
  `ops/systemd/crypto-alpha-creation.timer`.
- Hardened generated-work verification so only pytest verification command
  forms are accepted, and accepted commands run in a Docker sandbox with
  `--network none`, dropped capabilities, `no-new-privileges`, a read-only
  filesystem, bounded resources, and only the task worktree mounted.
- Added tests for creation models, store, context, prompts, Codex runner,
  worktrees, cycle orchestration, CLI payloads, Markdown escaping, VPS wrapper
  behavior, and Phase 17 documentation contracts.
- Added this round's Phase completion report.

## Verification Evidence

- Focused creation/autonomy regression bundle:
  `uv run --extra dev pytest tests/test_creation_autonomy_store.py tests/test_creation_context.py tests/test_codex_runner.py tests/test_autonomy_worktrees.py tests/test_creation_cycle.py tests/test_creation_cycle_cli.py tests/test_creation_cycle_markdown.py -q`
  passed with 88 tests.
- Owner main checkout full suite before closeout:
  `uv run --extra dev pytest -q` passed with 1085 tests.
- Owner main checkout lint, diff, and source secret scan passed:
  `uv run --extra dev ruff check .`, `git diff --check`, and
  `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests --path ops --path .github`
  returned no findings.
- Owner main checkout operational dry-runs passed for `ops/creation-cycle.sh`,
  `ops/daily-evidence-run.sh`, `ops/weekly-review.sh`,
  `ops/monthly-owner-review.sh`, `ops/backup-var.sh`, and
  `ops/install-systemd.sh`.
- `docker compose config --quiet` passed.
- `uv run --extra dev crypto-alpha-agent llm-health-check` passed with real
  provider metadata, `json_schema`, and `research_only`.
- `uv run --extra dev crypto-alpha-agent source-probe --list-targets` passed
  with real LLM judgement and no live capital or live order routing.
- Isolated closeout worktree deterministic baseline:
  `uv run --extra dev pytest -m "not llm_integration" -q` passed with
  1075 tests and 10 deselected.
- Real creation-cycle closeout smoke produced an accepted artifact:
  `creation-20260606T074040Z-d88a1ac24e`, `accepted=true`, and
  `runner_exit_code=0`. The resulting local candidate patch was promoted into
  `var/autonomy/active-worktree`; it remains not auto-pushed and not
  auto-merged into the owner main checkout.
- After that real artifact existed, a root deterministic closeout run first
  failed during pytest collection because default discovery recursively entered
  generated repository copies under `var/autonomy/active-worktree` and
  `var/autonomy/worktrees/`. The closeout adds a pytest configuration contract
  that limits default discovery to `tests/` and excludes `var/` and
  `.worktrees/`.
- A real-provider closeout rerun also exposed a local `rollout-review` error
  path bug: provider failures during the rollout LLM judgement attempted to
  call `args.parser.error(...)` before the subcommand parser had been attached
  to the namespace. The closeout fixes that parser wiring and adds a regression
  test for the provider-failure path.
- Final closeout focused docs/VPS/config contract:
  `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py tests/test_cli_smoke.py::test_pytest_default_collection_ignores_runtime_worktrees -q`
  passed with 34 tests.
- Final closeout focused CLI/provider-failure bundle:
  `uv run --extra dev pytest tests/test_cli_llm_native_gate.py tests/test_rollout_readiness_cli.py tests/test_vps_ops.py tests/test_documentation_contract.py tests/test_cli_smoke.py::test_pytest_default_collection_ignores_runtime_worktrees -q`
  passed with 49 tests.
- Final closeout deterministic suite:
  `uv run --extra dev pytest -m "not llm_integration" -q` passed with
  1082 tests and 10 deselected.
- Final closeout ruff, diff, secret scan, and compose config checks passed:
  `uv run --extra dev ruff check .`, `git diff --check`,
  `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests --path ops --path .github --path pyproject.toml --path docker-compose.yml`, and
  `docker compose --project-directory /Users/ww/Project/Crypto_Research_Agent -f /Users/ww/Project/Crypto_Research_Agent/.worktrees/phase17-closeout/docker-compose.yml config --quiet`.
- Isolated closeout worktree full real-LLM baseline without owner `.env`
  reached 1081 passed and 10 failed because the isolated worktree intentionally
  does not copy `OPENAI_BASE_URL`, `OPENAI_API_KEY`, or model names.
- Re-running full pytest with the owner local `.env` loaded reached 1086 passed
  and 6 failed because the external real LLM provider returned responses
  without extractable output text or CLI status 2 on provider-failure paths.
  This is recorded as an integration environment failure, not as deterministic
  product-code success.
- TDD RED for Phase 17 documentation closeout:
  `uv run --extra dev pytest tests/test_documentation_contract.py::test_phase17_creation_first_autonomy_closeout_is_documented -q`
  failed because the Phase 17 completion report did not exist.

## Current Project Target

The prior Phase 13 completion state described a deterministic evidence factory.
The active next project line changes the runtime target: product commands must
be LLM-native and must not succeed through deterministic-only fallback.

The evidence factory now has execution-realistic paper simulation,
evidence-grounded AI research planning, and profit governance review active:

- public-data ingestion and local durable SQLite storage;
- typed OHLCV, funding, DEX, DeFi, and open-interest records;
- source-health records that distinguish route, provider reachability, parse
  status, typed rows, and blocked reasons;
- data-quality checks for source failures, stale records, gaps, duplicates,
  timestamp skew, and invalid values;
- three executable paper-simulated families:
  `funding_extremity_price_confirmation`,
  `funding_mean_reversion_after_extreme`, and
  `funding_open_interest_crowding`;
- three research-only watchlists:
  `defi_yield_regime_watchlist`, `dex_liquidity_volume_watchlist`, and
  `volatility_compression_expansion_watchlist`;
- Phase 10 paper execution realism with venue fee assumptions, min-notional and
  precision feasibility, stale-signal gating, funding alignment checks,
  missed/partial-fill modeling, `pre_cost_only_profitable` rejection, and
  evidence package summaries for notional, fees, slippage, stale signals, and
  fills;
- daily/weekly evidence reports, governance reports, paper simulation, memory,
  and rollout review artifacts with `live_execution_enabled=false`.
- AI research context, stricter experiment proposal guards, duplicate rejected
  experiment memory, design-only strategy template proposals, and weekly
  `ai-research-memo` artifacts.
- Phase 12 `governance-report` artifacts that classify families as
  `keep_collecting`, `stop`, `redesign_validator`, `add_data`, or
  `owner_decision_review` from validation, paper, source-health, cost, and
  memory evidence.
- Phase 7 `historical-bootstrap` artifacts that evaluate historical windows,
  report source collection/probe status, classify historical strategy results,
  and set forward 30/60/90 evidence targets without mutating forward evidence
  ledgers or stopped-family memory.
- Phase 13 read-only review artifacts that inspect generated reports, evidence
  packages, AI memos, strategy scoreboards, stopped-family ledgers, and
  finished artifacts, then record explicit family and major-cycle decisions
  tied to evidence references instead of AI narrative.
- Phase 15 VPS operations layer that runs the LLM-native evidence factory as
  host-controlled Docker Compose jobs scheduled by systemd timers, with durable
  `var/` mounts, latest pointers, failed markers, logs, and backups.
- Phase 16 GHCR container publishing that lets VPS deployments pull
  `ghcr.io/ww-shan/crypto-alpha-agent:main` by default, while local builds can
  explicitly use `CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local`.
- Phase 17 creation-first Codex autonomy that reads latest reports and backlog,
  asks the real planning LLM for one strict `CreationObject`, asks Codex to
  build in an isolated worktree, runs sandboxed pytest verification, writes
  `var/autonomy/backlog.jsonl`, `var/autonomy/tasks/`,
  `var/reports/creation/latest.md`, and
  `var/reports/creation/latest.json`, and keeps accepted work out of the owner
  main checkout until human inspection.
- Bounded retries for real LLM structured-output schema drift in runtime
  judgement calls and experiment planning, without accepting live capital,
  live order routing, charter violations, unsupported validators, unsupported
  data fields, or missing evidence refs.

## Known Hard Boundaries

- No wallet keys.
- No wallet-key access.
- No live order routing.
- No exchange order submission.
- No order routing.
- No live execution.
- No live capital.
- No real-capital execution.
- No MEV, mempool, bridge-race, flash-loan, premium-RPC, private
  infrastructure, or speed-edge strategies.
- No secrets in git, logs, docs, memory, reports, screenshots, tests, or public
  GitHub.

## Known Remaining Gaps

The Phase 0 through Phase 17 charter-compliant evidence-factory and first
creation-first autonomy roadmap is implemented in local code. The LLM-native
runtime follow-up removed deterministic-only product success paths. Phase 15
adds the VPS Docker/systemd operations layer for unattended evidence
collection, Phase 16 makes that runtime pullable from GHCR by default, and
Phase 17 adds the first guarded Codex code-creation loop.

Reality audit: `docs/goals/project-reality-audit-2026-05-29.md` records that
the owner's broader autonomy target is larger than the completed Phase 0
through Phase 13 roadmap. Relative to that owner autonomy target, these
implementation gaps remain:

- `iteration-cycle` starts the review-only auto-iteration loop by asking the
  configured real planning LLM for strict `IterationCandidate` records and
  guarding them against uncited evidence, missing tests, missing source probes,
  direct code-write authority, live capital, and live order routing.
- VPS unattended operation is now available through Docker Compose and systemd
  timers with a GHCR-published container default, and Phase 17 adds a separate
  host-controlled `crypto-alpha-creation.timer` for one-shot `creation-cycle`
  jobs. There is still no internal daemon or live execution path.
- autonomous code-writing loop now has a first local Codex implementation, and
  a real accepted creation-cycle artifact has been observed in durable `var/`
  state as `creation-20260606T074040Z-d88a1ac24e` with `accepted=true` and
  `runner_exit_code=0`; accepted work is not auto-pushed or auto-merged into
  the owner main checkout;
- autonomous new data source discovery remains probe-gated beyond the curated
  source-probe and query catalogs;
- accepted iteration candidates still require human review and separate TDD
  implementation before any source, strategy, experiment, or code-change
  candidate can become product code.

Operational evidence collection also remains necessary:

- collect ordinary public source data;
- run daily `evidence-run`, evidence reports, AI memos, governance reports, and
  review reports over time;
- accumulate 30/60/90 out-of-sample paper observations before any
  profit/no-profit owner decision;
- inspect the real accepted creation-cycle candidate
  `creation-20260606T074040Z-d88a1ac24e` in `var/autonomy/active-worktree`
  before deciding whether to merge it into the owner main checkout;
- update the Phase 13 decision log when evidence changes.

Live execution remains outside the current charter until a future explicit
charter revision.

## Future Operation Instructions

If work continues after Phase 13:

1. Read `docs/project-charter.md` before any new plan.
2. Read `docs/goals/project-completion-goal.md` and follow its Per-Round
   Execution Protocol exactly: Smart Search deep research before design,
   local code-feasibility verification before planning, evidence-first substep
   gates for every meaningful added capability, one Phase per round,
   Superpowers workflows, subagent use, repeated review/fix/re-review cycles,
   state synchronization, a complete Phase report under
   `docs/goals/phase-reports/`, and no next Phase until the current Phase is
   clean, verified, committed, and pushed.
3. Do not start a new product-code phase unless the owner revises the roadmap
   or charter. Current useful work is running the evidence campaign and updating
   review records when new evidence exists.
4. Treat live execution, wallet keys, exchange order routing, private RPC,
   MEV, premium-RPC, and speed-edge paths as blocked unless the owner
   explicitly revises the charter.
5. Use the Phase 1/2 model routing: research/planning/code use the configured
   strong model and report/summary use the configured fast model. Preserve fake
   LLM tests for deterministic adversarial cases, and make real positive tests
   explicit and secret-safe.
6. For Phase 13, review generated reports, evidence packages, AI memos,
   strategy scoreboards, stopped-family ledgers, source-health rows, and
   decision records. Do not add product code or live execution.
7. Keep failed evidence and rejected assumptions in memory.
8. Update this file and `docs/roadmap.md` only when the public roadmap or final
   project state changes.

## Round History

| Round | Date | Slice | Verification | Commit | GitHub |
| --- | --- | --- | --- | --- | --- |
| 0 | 2026-05-17 | Goal contract bootstrap | pytest 676 passed; ruff passed; diff check passed; staged secret review passed | Goal bootstrap docs slice | public repo target |
| 1 | 2026-05-17 UTC / 2026-05-18 local | Complete autonomous evidence system milestone | pytest 750 passed; ruff passed; diff check passed; focused source tests 52 passed; forbidden-path review found no production live path | `fb1635d281f33e93a6723832bdf04a115e160c86` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 2 | 2026-05-23 | Immediate Phase 0 / merged Phase 6 worktree and configuration closeout | focused Phase 0 checks 8 passed; pytest 750 passed; ruff passed; diff check passed; staged secret review passed | Phase 0 completion commit `docs: complete phase 0 closeout` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 3 | 2026-05-23 | Immediate Phase 1 real LLM adapter | tests 762 passed; ruff passed; diff check passed; staged secret review passed | Phase 1 completion commit `feat: add real llm adapter` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 4 | 2026-05-23 | Immediate Phase 2 connect LLM to research loop | tests 770 passed; ruff passed; diff check passed; staged secret review passed | `ae3e601 feat: connect llm to research loop` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 5 | 2026-05-23 | Immediate Phase 3 real LLM test policy | focused Phase 3 tests 16 passed; pytest 785 passed; ruff passed; diff check passed; staged secret review passed | `9fb1945 test: formalize real llm policy` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 6 | 2026-05-23 | Immediate Phase 4 evidence run infrastructure | focused Phase 4 runner tests 19 passed; scheduler/docs 17 passed; complete/degradation 16 passed; pytest 797 passed; ruff passed; diff/staged checks passed; staged secret scan passed | `a31bda7 feat: add evidence run infrastructure` plus `c3b6127 docs: finalize phase 4 state` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 7 | 2026-05-23 | Immediate Phase 5 data and strategy expansion preparation | focused Phase 5 tests 29 passed; pytest 802 passed; ruff passed; review re-check found no Critical or Important findings | `f6964ab feat: add expansion preparation report` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 8 | 2026-05-24 | Phase 8 data depth and quality expansion | focused Phase 8 tests 61 passed; pytest 832 passed; ruff passed; diff/staged checks passed; path and staged secret scans returned [] | Phase 8 completion commit `feat: add source qualification workflow` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 9 | 2026-05-24 | Phase 9 strategy validator library expansion | focused Phase 9 tests 157 passed; pytest 868 passed; ruff passed; diff check passed; path secret scan returned [] | Phase 9 completion commit `feat: expand strategy validator library` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 10 | 2026-05-24 | Phase 10 execution realism and cost model | focused Phase 10 tests 48 passed; pytest 881 passed, 4 skipped; ruff passed; diff check passed; path secret scan returned [] | Phase 10 completion commit `feat: add execution realism cost model` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 11 | 2026-05-24 | Phase 11 AI researcher upgrade | focused Phase 11/end-to-end tests 53 passed; pytest 893 passed, 4 skipped; ruff passed | Phase 11 completion commit `feat: upgrade ai researcher evidence guards` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 12 | 2026-05-24 | Phase 12 profit evidence review and portfolio governance | focused Phase 12 tests 28 passed; pytest 898 passed, 4 skipped; ruff passed; diff check passed; path secret scan returned [] | `e89e008 feat: add profit governance report` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 13 | 2026-05-24 | Phase 7 final evidence campaign after factory buildout | focused Phase 7 tests 59 passed; pytest 912 passed, 4 skipped; ruff passed; diff and staged secret checks passed | `feat: add historical bootstrap campaign` | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 14 | 2026-05-24 | Phase 13 continuous research review and reporting | deterministic pytest 912 passed, 4 skipped; ruff passed; diff and staged secret checks passed; local real LLM provider test failed schema and is non-gating | `9ca8966 docs: add phase 13 review records` plus final state sync | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 15 | 2026-05-29 | Phase 14 LLM-native autonomous iteration controller | focused Phase 14 tests 16 passed; pytest 965 passed; ruff passed; diff check passed; staged secret scan required before commit | Phase 14 implementation commit | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 16 | 2026-05-29 | Phase 15 VPS Docker operations runtime | focused VPS/docs contracts 24 passed; pytest 982 passed; final ruff, diff, staged diff, and staged secret checks required before commit | Phase 15 implementation commit | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 17 | 2026-05-29 | Phase 16 GHCR container publishing | focused GHCR/docs/runtime/planner contracts 81 passed; real LLM planner smoke 1 passed; pytest 990 passed; final ruff, diff, staged diff, and staged secret checks required before commit | Phase 16 implementation commit | `https://github.com/WW-shan/Crypto_Research_Agent` |
| 18 | 2026-06-06 | Phase 17 creation-first Codex autonomy | focused creation tests 88 passed; owner main pytest 1085 passed; real accepted creation artifact observed; final focused docs/VPS/config tests 34 passed; focused CLI provider-failure bundle 49 passed; deterministic closeout pytest 1082 passed, 10 deselected; ruff/diff/secret/compose checks passed; full real LLM closeout baseline with owner `.env` hit 6 provider integration failures | Phase 17 local implementation commits plus closeout docs | local branch ahead of `origin/main` by 29 commits before closeout |
