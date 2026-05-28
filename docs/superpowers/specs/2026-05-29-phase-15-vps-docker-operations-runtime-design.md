# Phase 15 VPS Docker Operations Runtime Design

## Goal

Package the current LLM-native evidence factory so it can run unattended on a
VPS through Docker Compose and host systemd timers.

## Scope

This phase adds operational deployment files only. It does not add a long-lived
Python daemon, autonomous code-writing, live trading, wallet access, order
routing, or automatic source promotion.

The VPS runtime must:

- run product commands inside a Docker image;
- keep `.env` outside git and load it at runtime;
- persist `var/` on the VPS host;
- schedule one-shot jobs through systemd timers;
- write daily evidence artifacts, weekly review artifacts, monthly review
  artifacts, backups, stdout logs, stderr logs, manifests, latest pointers, and
  failed markers;
- preserve the existing LLM-native rule: if the real LLM health check,
  structured JSON schema validation, or guard validation fails, the command
  exits nonzero.

## Architecture

Use Docker Compose for the application runtime and host systemd timers for
scheduling. Each timer calls a shell wrapper under `ops/`; each wrapper runs a
short-lived `docker compose run --rm crypto-alpha-agent ...` job and exits.

The application remains stateless except for mounted host directories:

- `./var:/app/var`
- `./.env:/app/.env:ro`

The scripts create dated paths under `var/` and keep `latest` report pointers
for easy inspection. The daily job uses the existing `evidence-run` lock. The
weekly job runs `governance-report`, `ai-research-memo`, and
`iteration-cycle`. The monthly job runs a read-only rollout review when enough
evidence exists; if the operator has not configured a family, it exits with a
clear error. The backup job creates compressed local snapshots of SQLite,
memory, reports, and manifests.

## Components

- `Dockerfile`: reproducible Python 3.12 image using `uv sync --extra dev`.
- `.dockerignore`: excludes secrets, local databases, reports, caches,
  worktrees, and virtualenvs from image build context.
- `docker-compose.yml`: defines the `crypto-alpha-agent` service with `.env`,
  persistent `var/`, and safe default command.
- `ops/daily-evidence-run.sh`: daily one-shot evidence collection wrapper.
- `ops/weekly-review.sh`: weekly governance, AI memo, and iteration candidate
  wrapper.
- `ops/monthly-owner-review.sh`: monthly rollout-review wrapper for a chosen
  family.
- `ops/backup-var.sh`: local backup wrapper for `var/`.
- `ops/install-systemd.sh`: installs systemd unit files for a chosen repo path.
- `ops/systemd/*.service` and `ops/systemd/*.timer`: host scheduler units.
- `docs/vps-deployment.md`: operator setup, environment, deploy, run, inspect,
  update, backup, and recovery guide.
- `tests/test_vps_ops.py`: contract tests for generated operational files.
- `tests/test_documentation_contract.py`: documentation contract update.

## Data Flow

Daily:

```text
systemd timer -> ops/daily-evidence-run.sh -> docker compose run evidence-run
  -> var/research.sqlite
  -> var/memory/evidence.jsonl
  -> var/reports/daily/<date>.md
  -> var/reports/daily/<date>.research.md
  -> var/reports/daily/<date>.json
  -> var/reports/daily/latest.md
  -> var/reports/daily/latest.json
  -> var/reports/weekly/<week>.md
  -> var/run-manifests/evidence-run/<run-id>.json
  -> var/run-manifests/latest.json
  -> var/run-manifests/failed/<run-id>.json on failure
  -> var/log/evidence-run/<date>.out.log
  -> var/log/evidence-run/<date>.err.log
```

Weekly:

```text
systemd timer -> ops/weekly-review.sh
  -> governance-report
  -> ai-research-memo
  -> iteration-cycle
  -> var/reports/weekly/<week>-governance.md
  -> var/reports/weekly/<week>-ai-memo.md
  -> var/reports/iteration/<week>-iteration.md
  -> var/reports/iteration/<week>-iteration.json
  -> var/reports/iteration/latest.md
  -> var/reports/iteration/latest.json
  -> var/log/weekly-review/<week>.out.log
  -> var/log/weekly-review/<week>.err.log
```

Backups:

```text
systemd timer -> ops/backup-var.sh
  -> var/backups/<timestamp>/research.sqlite
  -> var/backups/<timestamp>/evidence.jsonl
  -> var/backups/<timestamp>/reports.tgz
  -> var/backups/<timestamp>/run-manifests.tgz
```

## Error Handling

- Wrappers use `set -euo pipefail`.
- Wrappers keep stdout and stderr in separate log files.
- Daily evidence runs rely on the product `--lock-path` to prevent overlaps.
- Nonzero product exits propagate to systemd, so systemd marks the unit failed.
- Daily failed runs also write `failed-marker-out`.
- Weekly and monthly jobs do not hide failures; if governance, memo, or
  iteration-cycle fails, the wrapper exits nonzero.
- Backups fail fast when `var/` is missing.

## Testing

Tests must not require Docker or systemd to be installed. They verify file
contents and run script syntax checks with `bash -n`. Wrapper dry-run mode is
provided through `CRYPTO_ALPHA_AGENT_DRY_RUN=1` so tests can verify generated
commands without running Docker.

## Security Boundaries

- `.env` is mounted read-only and never copied into the image.
- `.dockerignore` excludes `.env`, `var/`, `.venv/`, caches, logs, reports,
  worktrees, and git metadata.
- No wallet paths or exchange order credentials are introduced.
- Docker Compose does not mount `/var/run/docker.sock`.
- All scheduled jobs remain research-only and paper-only.
- `iteration-cycle` continues to emit `auto_executes_changes=false`.
