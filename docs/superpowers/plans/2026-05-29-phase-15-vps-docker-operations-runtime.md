# Phase 15 VPS Docker Operations Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a VPS-ready Docker Compose and systemd timer operations layer for unattended LLM-native evidence collection and review.

**Architecture:** Keep product commands as short-lived jobs. Docker Compose supplies the runtime and mounted persistent `var/`; host systemd timers call shell wrappers that execute daily, weekly, monthly, and backup jobs.

**Tech Stack:** Docker, Docker Compose, bash, systemd timers, Python 3.12, uv, pytest, ruff.

---

## Files

- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.yml`
- Create: `ops/daily-evidence-run.sh`
- Create: `ops/weekly-review.sh`
- Create: `ops/monthly-owner-review.sh`
- Create: `ops/backup-var.sh`
- Create: `ops/install-systemd.sh`
- Create: `ops/systemd/crypto-alpha-daily.service`
- Create: `ops/systemd/crypto-alpha-daily.timer`
- Create: `ops/systemd/crypto-alpha-weekly.service`
- Create: `ops/systemd/crypto-alpha-weekly.timer`
- Create: `ops/systemd/crypto-alpha-monthly.service`
- Create: `ops/systemd/crypto-alpha-monthly.timer`
- Create: `ops/systemd/crypto-alpha-backup.service`
- Create: `ops/systemd/crypto-alpha-backup.timer`
- Create: `docs/vps-deployment.md`
- Create: `tests/test_vps_ops.py`
- Modify: `tests/test_documentation_contract.py`
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`

## Task 1: VPS Ops Contract Tests

- [ ] Write `tests/test_vps_ops.py` with tests that assert required ops files exist, scripts pass `bash -n`, scripts include `docker compose run --rm crypto-alpha-agent`, daily script uses `evidence-run` with lock/latest/manifest/failed marker paths, weekly script runs `governance-report`, `ai-research-memo`, and `iteration-cycle`, and Docker files exclude `.env` from build context while mounting it read-only at runtime.
- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py -q`.
- [ ] Verify RED because the files do not exist yet.

## Task 2: Docker Runtime Files

- [ ] Add `Dockerfile` using Python 3.12 slim, uv, non-root `app` user, `/app` workdir, `uv sync --extra dev --frozen`, and default `crypto-alpha-agent --help`.
- [ ] Add `.dockerignore` excluding `.env`, `.git`, `.venv`, `.worktrees`, `var`, caches, logs, local databases, and reports.
- [ ] Add `docker-compose.yml` with service `crypto-alpha-agent`, build context `.`, `env_file: .env`, `./var:/app/var`, read-only `.env` bind, and no Docker socket mount.
- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py -q`.
- [ ] Verify Docker-file tests pass while ops-script tests still fail.

## Task 3: Ops Shell Wrappers

- [ ] Add daily, weekly, monthly, backup, and install scripts under `ops/`.
- [ ] Each runtime script must use `set -euo pipefail`, resolve `REPO`, create required `var/` directories, emit commands in `CRYPTO_ALPHA_AGENT_DRY_RUN=1`, write stdout/stderr logs, and propagate nonzero exits.
- [ ] Daily script must run `evidence-run` with dated reports, latest pointers, manifest, failed marker, and lock path.
- [ ] Weekly script must run `governance-report`, `ai-research-memo`, and `iteration-cycle`, and copy iteration outputs to latest pointers.
- [ ] Monthly script must require `CRYPTO_ALPHA_AGENT_REVIEW_FAMILY` and run `rollout-review` for that family.
- [ ] Backup script must copy SQLite and memory when present and tar reports/manifests.
- [ ] Run `bash -n ops/*.sh` and `uv run --extra dev pytest tests/test_vps_ops.py -q`.
- [ ] Verify ops-script tests pass.

## Task 4: Systemd Units

- [ ] Add one-shot service and timer files for daily, weekly, monthly, and backup jobs.
- [ ] Services must call `/opt/crypto-alpha-agent/ops/<script>.sh`, set `WorkingDirectory=/opt/crypto-alpha-agent`, and avoid embedding secrets.
- [ ] Timers must use UTC-ish server schedules and `Persistent=true`.
- [ ] Run `uv run --extra dev pytest tests/test_vps_ops.py -q`.
- [ ] Verify systemd contract tests pass.

## Task 5: Documentation

- [ ] Add `docs/vps-deployment.md` covering VPS prerequisites, clone path, `.env`, Docker Compose build, manual smoke tests, systemd install, daily/weekly/monthly outputs, backups, logs, failures, updates, and safety boundaries.
- [ ] Update `docs/runbook.md`, `docs/roadmap.md`, `docs/goals/project-completion-state.md`, and `tests/test_documentation_contract.py` with Phase 15 terms.
- [ ] Run `uv run --extra dev pytest tests/test_documentation_contract.py tests/test_vps_ops.py -q`.
- [ ] Verify docs and ops contracts pass.

## Task 6: Final Verification And Commit

- [ ] Run focused tests:
  `uv run --extra dev pytest tests/test_vps_ops.py tests/test_documentation_contract.py -q`.
- [ ] Run full verification:
  `uv run --extra dev pytest -q`.
- [ ] Run lint and diff checks:
  `uv run --extra dev ruff check .` and `git diff --check`.
- [ ] Stage intended files and run:
  `git diff --cached --check`,
  `git diff --cached --name-only`,
  `git diff --cached --no-ext-diff --unified=0`,
  `uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked`.
- [ ] Commit with `feat: add vps docker operations runtime`.
