# Phase 15 Completion Report: VPS Docker Operations Runtime

Date: 2026-05-29

## Scope

Phase 15 adds the recommended VPS operations layer for running the existing
LLM-native evidence factory unattended.

The architecture stays intentionally simple: product commands remain
short-lived jobs; Docker Compose supplies the runtime and mounted durable
`var/`; host systemd timers decide when daily, weekly, monthly, and backup jobs
run.

## Delivered

- Added `Dockerfile` for Python 3.12 slim, `uv`, a non-root `app` user, and
  the `crypto-alpha-agent` entrypoint.
- Added `.dockerignore` to keep `.env`, worktrees, virtualenvs, local
  databases, logs, caches, and `var/` artifacts out of Docker images.
- Added `docker-compose.yml` with the `crypto-alpha-agent` service, `.env`
  runtime loading, read-only `.env` bind, and `./var:/app/var` persistence.
- Added `ops/daily-evidence-run.sh` for daily `evidence-run` artifacts,
  latest pointers, run manifest, failed marker, stdout/stderr logs, and lock
  path.
- Added `ops/weekly-review.sh` for `governance-report`, `ai-research-memo`,
  and `iteration-cycle`, with latest iteration pointers.
- Added `ops/monthly-owner-review.sh` for `rollout-review` packages tied to
  `CRYPTO_ALPHA_AGENT_REVIEW_FAMILY`.
- Added `ops/backup-var.sh` for SQLite, evidence memory, report, and manifest
  backups.
- Added `ops/install-systemd.sh` plus daily, weekly, monthly, and backup
  service/timer units.
- Added `docs/vps-deployment.md` with VPS setup, `.env`, Docker Compose build,
  LLM health check, wrapper dry-runs, systemd installation, outputs, logs,
  backups, updates, and safety boundaries.
- Updated roadmap, runbook, documentation contracts, and project completion
  state.

## Boundary

This phase does not add live trading or self-coding.

- Product commands still require a configured real LLM runtime and fail closed
  when health checks, structured schema validation, evidence refs, or guards
  fail.
- Docker Compose and systemd run existing LLM-native product commands; they do
  not make deterministic modules an independent success path.
- `iteration-cycle` remains review-only with `auto_executes_changes=false`.
- There is no wallet-key access, no exchange order submission, no live order
  routing, no live execution, and no live capital.

## Verification

Verification completed during implementation:

- Baseline worktree full suite: `uv run --extra dev pytest -q` -> 968 passed.
- TDD RED for missing VPS ops files:
  `uv run --extra dev pytest tests/test_vps_ops.py -q` -> failed because the
  Docker, ops, systemd, and VPS deployment files did not exist.
- Intermediate Docker verification:
  `uv run --extra dev pytest tests/test_vps_ops.py -q` -> Docker runtime
  contract passed while ops/systemd/docs checks still failed.
- Ops dry-run regression reproduced on macOS bash 3:
  `ops/weekly-review.sh` failed on `declare -n`; a portable dry-run test was
  added before replacing the nameref usage.
- Focused contracts:
  `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py -q`
  -> 19 passed.
- Portable dry-run plus focused contracts:
  `uv run --extra dev pytest tests/test_vps_ops.py::test_ops_scripts_support_portable_dry_run tests/test_vps_ops.py tests/test_documentation_contract.py -q`
  -> 24 passed.
- Full suite: `uv run --extra dev pytest -q` -> 982 passed.

Final lint, diff, staged diff, and staged secret scan are required immediately
before commit: `uv run --extra dev ruff check .`, `git diff --check`,
`git diff --cached --check`, `git diff --cached --name-only`,
`git diff --cached --no-ext-diff --unified=0`, and
`uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`.

## Remaining Gaps

Phase 15 makes repeated VPS operation practical, but the broader owner autonomy
target still has gaps:

- Autonomous code-writing remains proposal-only.
- Autonomous new data source discovery remains source-probe gated.
- Accepted `iteration-cycle` candidates require human review and separate TDD
  implementation.
- The 30/60/90 out-of-sample evidence campaign still requires real operation
  over time.
- Live execution remains blocked by the current charter.
