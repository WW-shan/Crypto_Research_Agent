# Phase 17 Completion Report: Creation-First Codex Autonomy

Date: 2026-06-06

Commit: local closeout commit on `phase17-closeout`.

## Scope

Phase 17 adds the first creation-first autonomy loop. The new path asks the
configured real LLM for one strict `CreationObject`, asks Codex to build the
selected change in an isolated worktree, runs sandboxed pytest verification,
writes task artifacts, and advances an autonomy backlog.

The product command is `creation-cycle`. The VPS entry point is
`ops/creation-cycle.sh`, scheduled by `crypto-alpha-creation.timer`.

## Delivered

- Added `docs/superpowers/specs/2026-05-30-phase-17-creation-first-codex-autonomy-design.md`.
- Added `docs/superpowers/plans/2026-05-30-phase-17-creation-first-codex-autonomy.md`.
- Added `src/crypto_alpha_agent/autonomy/`:
  - strict creation, role-note, Codex result, and cycle report models;
  - a filesystem artifact store for `var/autonomy/backlog.jsonl` and
    `var/autonomy/tasks/`;
  - bounded report-context loading;
  - Director/Creator and Builder prompts;
  - Codex health-check and builder execution wrapper;
  - git worktree creation and active-worktree promotion;
  - the `run_creation_cycle` orchestrator.
- Added the public `creation-cycle` CLI command, routed through the planning
  LLM role and real LLM runtime gate.
- Added `render_creation_cycle_markdown` for
  `var/reports/creation/latest.md` and machine payload writing for
  `var/reports/creation/latest.json`.
- Added `ops/creation-cycle.sh` and
  `ops/systemd/crypto-alpha-creation.service` /
  `ops/systemd/crypto-alpha-creation.timer`.
- Updated `ops/install-systemd.sh` and `docs/vps-deployment.md` so VPS
  operation includes the creation timer.
- Hardened creation verification:
  - Codex is required before a cycle starts;
  - generated work runs in an isolated worktree;
  - verification accepts only pytest command forms:
    `pytest ...`, `python -m pytest ...`, and `uv run pytest ...`;
  - verification runs in a Docker sandbox with `--network none`, dropped
    Linux capabilities, `no-new-privileges`, read-only container filesystem,
    bounded CPU/memory/PIDs, and only the task worktree mounted;
  - pytest config, local conftest, plugin autoload, no-op pytest modes,
    grouped help/version flags, override addopts, absolute paths, and parent
    path selectors are rejected.
- Added tests for models, store, context, prompts, Codex runner, worktrees,
  cycle orchestration, CLI failure payloads, Markdown escaping, VPS wrapper
  behavior, and documentation contracts.

## Boundary

Phase 17 does not add live trading, exchange order routing, wallet access,
private key access, real capital deployment, MEV, premium RPC, private
infrastructure, or speed-edge execution.

`creation-cycle` may write code in an isolated worktree and may promote a
passing patch into `var/autonomy/active-worktree`, but it is not auto-pushed
and not auto-merged into the owner main checkout. Operators must inspect
patches, reports, and test output before merging work into the main branch.

A real accepted creation-cycle artifact has been observed in the durable
`var/` operator state during this closeout:

- `var/autonomy/backlog.jsonl`
- `var/autonomy/tasks/creation-20260606T074040Z-d88a1ac24e/`
- `var/reports/creation/latest.md`
- `var/reports/creation/latest.json`

The latest real creation-cycle payload recorded
`task_id=creation-20260606T074040Z-d88a1ac24e`, `accepted=true`, and
`runner_exit_code=0`. The promoted patch is present in
`var/autonomy/active-worktree` as a local candidate only; it is not auto-pushed
or auto-merged into the owner main checkout.

## Local Evidence State

The latest local operator evidence store contains real public-data research
artifacts, but it does not prove profit:

- `source_records`: 438 rows.
- `validation_evidence`: 3 rows.
- `paper_outcomes`: 3 rows.
- Existing paper outcomes are all `blocked`, with `net_pnl_usd=0.0`.
- Current repeated blocking reasons include `no_extreme_funding`,
  `insufficient_trades`, `non_positive_expectancy`,
  `non_positive_net_return`, and `unstable_walk_forward_performance`.

The 30/60/90 out-of-sample paper evidence remains uncollected. Tiny-live review
remains blocked.

## Verification

Verification observed during the Phase 17 implementation branch:

- `uv run --extra dev pytest tests/test_creation_autonomy_store.py tests/test_creation_context.py tests/test_codex_runner.py tests/test_autonomy_worktrees.py tests/test_creation_cycle.py tests/test_creation_cycle_cli.py tests/test_creation_cycle_markdown.py -q`
  -> 88 passed.
- `uv run --extra dev pytest -q` in the owner main checkout -> 1085 passed.
- `uv run --extra dev ruff check .` -> passed.
- `git diff --check` -> passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests --path ops --path .github`
  -> `[]`.
- `docker compose config --quiet` -> passed.
- `CRYPTO_ALPHA_AGENT_DRY_RUN=1 bash ops/creation-cycle.sh` -> printed the
  expected `creation-cycle` command, latest Markdown/JSON paths, lock path, and
  log paths.
- `CRYPTO_ALPHA_AGENT_DRY_RUN=1 bash ops/daily-evidence-run.sh` -> printed the
  expected daily `evidence-run` command.
- `CRYPTO_ALPHA_AGENT_DRY_RUN=1 bash ops/weekly-review.sh` -> printed the
  expected `governance-report`, `ai-research-memo`, and `iteration-cycle`
  commands.
- `CRYPTO_ALPHA_AGENT_DRY_RUN=1 CRYPTO_ALPHA_AGENT_REVIEW_FAMILY=funding_extremity_price_confirmation bash ops/monthly-owner-review.sh`
  -> printed the expected `rollout-review` command.
- `CRYPTO_ALPHA_AGENT_DRY_RUN=1 bash ops/backup-var.sh` -> printed the expected
  backup operations.
- `CRYPTO_ALPHA_AGENT_DRY_RUN=1 bash ops/install-systemd.sh` -> printed all five
  timer installs, including `crypto-alpha-creation.timer`.
- `uv run --extra dev crypto-alpha-agent llm-health-check` in the owner main
  checkout -> exit code 0 with real provider, `json_schema`, and
  `research_only` capability.
- `uv run --extra dev crypto-alpha-agent source-probe --list-targets` in the
  owner main checkout -> exit code 0 with real LLM judgement and no live
  capital or live order routing.

Closeout verification in the isolated worktree:

- Initial `uv run --extra dev pytest -q` without the owner `.env` failed in 10
  real LLM integration tests because the isolated worktree intentionally did
  not copy `OPENAI_BASE_URL`, `OPENAI_API_KEY`, or model names.
- After a real creation-cycle artifact existed under `var/autonomy/`, the first
  deterministic closeout run of
  `uv run --extra dev pytest -m "not llm_integration" -q` failed during
  collection because pytest recursively discovered generated repository copies
  under `var/autonomy/active-worktree` and `var/autonomy/worktrees/`. The fix
  constrains default pytest discovery to `tests/` and excludes `var/` and
  `.worktrees/`.
- A real-provider closeout rerun exposed a local `rollout-review` error path
  bug: provider failures during the rollout LLM judgement attempted to call
  `args.parser.error(...)` before the subcommand parser had been attached to
  the namespace. The closeout fixes that parser wiring and adds a regression
  test for the provider-failure path.
- `uv run --extra dev pytest tests/test_cli_smoke.py::test_pytest_default_collection_ignores_runtime_worktrees -q`
  -> 1 passed.
- TDD RED for this closeout documentation contract:
  `uv run --extra dev pytest tests/test_documentation_contract.py::test_phase17_creation_first_autonomy_closeout_is_documented -q`
  -> failed because this Phase 17 completion report did not exist.
- TDD GREEN for the updated creation-cycle artifact documentation contract:
  `uv run --extra dev pytest tests/test_documentation_contract.py::test_phase17_creation_first_autonomy_closeout_is_documented -q`
  -> 1 passed.
- Focused closeout docs/VPS/config contract:
  `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py tests/test_cli_smoke.py::test_pytest_default_collection_ignores_runtime_worktrees -q`
  -> 34 passed.
- Focused CLI provider-failure regression bundle:
  `uv run --extra dev pytest tests/test_cli_llm_native_gate.py tests/test_rollout_readiness_cli.py tests/test_vps_ops.py tests/test_documentation_contract.py tests/test_cli_smoke.py::test_pytest_default_collection_ignores_runtime_worktrees -q`
  -> 49 passed.
- Deterministic closeout suite:
  `uv run --extra dev pytest -m "not llm_integration" -q` -> 1082 passed,
  10 deselected.
- Full closeout pytest without owner `.env`:
  `uv run --extra dev pytest -q` -> 1081 passed and 10 failed because the
  isolated worktree intentionally does not copy `OPENAI_BASE_URL`,
  `OPENAI_API_KEY`, or model names.
- Full closeout pytest with the owner local `.env` loaded:
  `set -a; source /Users/ww/Project/Crypto_Research_Agent/.env; set +a; uv run --extra dev pytest -q`
  -> 1086 passed and 6 failed because the external real LLM provider returned
  responses without extractable output text or CLI status 2 on provider-failure
  paths. This is recorded as an integration environment failure, not as
  deterministic product-code success.
- `uv run --extra dev ruff check .` -> passed.
- `git diff --check` -> passed.
- `uv run python -m crypto_alpha_agent.security.secret_scan --path README.md --path docs --path src --path tests --path ops --path .github --path pyproject.toml --path docker-compose.yml`
  -> `[]`.
- `docker compose --project-directory /Users/ww/Project/Crypto_Research_Agent -f /Users/ww/Project/Crypto_Research_Agent/.worktrees/phase17-closeout/docker-compose.yml config --quiet`
  -> passed. The explicit owner project directory is required because the
  isolated closeout worktree intentionally does not copy the ignored local
  `.env`.
- Staged closeout checks before commit:
  `git diff --cached --check`, `git diff --cached --name-only`,
  `git diff --cached --no-ext-diff --unified=0`, and
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`
  -> passed, with staged secret scan returning `[]`.

## Remaining Gaps

- Merge or open a PR for the verified `phase17-closeout` branch after owner
  review. At closeout start, local `main` was ahead of `origin/main` by 29
  commits.
- Inspect the real accepted creation-cycle candidate
  `creation-20260606T074040Z-d88a1ac24e` before deciding whether to merge its
  patch from `var/autonomy/active-worktree` into the owner main checkout.
- Continue the evidence campaign over real elapsed time.
- Expand or rotate away from currently stopped/blocked funding-extremity
  evidence paths only through public-data validation, source probes, paper
  simulation, and human review.
- Keep live execution blocked unless a future charter revision explicitly
  authorizes a separate live phase.
