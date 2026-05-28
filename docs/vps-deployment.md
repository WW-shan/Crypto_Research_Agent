# VPS Deployment

This is the recommended unattended operations shape for a VPS:

- Docker Compose provides a repeatable Python 3.12 and `uv` runtime.
- Host `systemd` timers decide when short-lived jobs run.
- The agent still has no internal daemon and no live trading authority.
- Secrets stay in host-local environment files; `.env stays outside git`.

The result is an operator-controlled evidence factory that can keep collecting
data, asking the configured real LLM for judgement, writing reports, and
preserving artifacts over time.

## Safety Boundaries

- Product commands are LLM-native. If `llm-health-check` or the command-level
  structured LLM gate fails, the job fails closed instead of reporting success.
- The deployment has no wallet keys, no exchange trade permissions, no live
  execution, and no live order routing.
- `iteration-cycle` remains review-only and records
  `auto_executes_changes=false`; it does not write code, promote data sources,
  run tests, schedule future commands, or trade.
- Deterministic modules still normalize data, validate schemas, compute source
  quality, run strategy validators, simulate paper outcomes, model costs,
  enforce risk guards, redact secrets, and preserve the evidence ledger. They
  are constraints inside the LLM-native flow, not a standalone success path.

## Server Layout

Use one deploy directory and one persistent `var/` tree:

```bash
sudo mkdir -p /opt/crypto-alpha-agent
sudo chown "$USER":"$USER" /opt/crypto-alpha-agent
git clone <repo-url> /opt/crypto-alpha-agent
cd /opt/crypto-alpha-agent
```

Expected durable outputs:

- `var/research.sqlite` - local SQLite research store.
- `var/memory/evidence.jsonl` - append-only memory and evidence feedback.
- `var/reports/daily/latest.md` - latest daily evidence report pointer.
- `var/reports/daily/latest.evidence-run.json` - latest daily machine payload.
- `var/reports/iteration/latest.json` - latest guarded iteration payload.
- `var/run-manifests/latest.json` - latest run manifest pointer.
- `var/run-manifests/failed/` - failed marker JSON files for nonzero runs.
- `var/log/evidence-run/`, `var/log/weekly-review/`, and
  `var/log/monthly-owner-review/` - stdout/stderr logs.
- `var/backups/` - timestamped SQLite, memory, report, and manifest backups.

## Environment

Create `/opt/crypto-alpha-agent/.env` on the VPS by copying values from the
operator's secret store. Do not commit it.

```env
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_API_TYPE=responses
OPENAI_MODEL=
OPENAI_RESEARCH_MODEL=
OPENAI_CODER_MODEL=
OPENAI_FAST_MODEL=
```

Optional nonsecret runtime knobs can stay in `.env` or a systemd drop-in:

```env
CRYPTO_ALPHA_AGENT_STRATEGY_FAMILY=funding_extremity_price_confirmation
CRYPTO_ALPHA_AGENT_REVIEW_FAMILY=funding_extremity_price_confirmation
CRYPTO_ALPHA_AGENT_SYMBOL=BTC/USDT
CRYPTO_ALPHA_AGENT_FUNDING_SYMBOL=BTC/USDT:USDT
CRYPTO_ALPHA_AGENT_TIMEFRAME=1h
CRYPTO_ALPHA_AGENT_LIMIT=200
CRYPTO_ALPHA_AGENT_CURRENT_CAPITAL_USD=300
```

## Build And Smoke Test

Install Docker and the Compose plugin on the VPS, then build:

```bash
cd /opt/crypto-alpha-agent
docker compose build
docker compose run --rm crypto-alpha-agent llm-health-check
```

If the LLM connection test fails, stop here. The scheduled jobs should not run
until the real LLM provider, model names, credentials, and schema-compatible
responses are healthy.

Dry-run the wrappers before enabling timers:

```bash
CRYPTO_ALPHA_AGENT_DRY_RUN=1 ops/daily-evidence-run.sh
CRYPTO_ALPHA_AGENT_DRY_RUN=1 ops/weekly-review.sh
CRYPTO_ALPHA_AGENT_DRY_RUN=1 \
  CRYPTO_ALPHA_AGENT_REVIEW_FAMILY=funding_extremity_price_confirmation \
  ops/monthly-owner-review.sh
CRYPTO_ALPHA_AGENT_DRY_RUN=1 ops/backup-var.sh
```

Run one manual evidence job when the LLM health check is green:

```bash
ops/daily-evidence-run.sh
```

Review:

- `var/reports/daily/latest.md`
- `var/reports/daily/latest.evidence-run.json`
- `var/run-manifests/latest.json`
- the stdout and stderr log paths printed by the wrapper in dry-run mode

## Install systemd Timers

Copy unit files and enable timers:

```bash
cd /opt/crypto-alpha-agent
ops/install-systemd.sh
systemctl list-timers 'crypto-alpha-*'
```

Installed timers:

- `crypto-alpha-daily.timer` runs the daily `evidence-run` wrapper.
- `crypto-alpha-weekly.timer` runs `governance-report`, `ai-research-memo`,
  and `iteration-cycle`, then refreshes
  `var/reports/iteration/latest.md` and `var/reports/iteration/latest.json`.
- `crypto-alpha-monthly.timer` runs `rollout-review` for
  `CRYPTO_ALPHA_AGENT_REVIEW_FAMILY`.
- `crypto-alpha-backup.timer` snapshots SQLite, memory, reports, and manifests.

Manual operations:

```bash
systemctl start crypto-alpha-daily.service
journalctl -u crypto-alpha-daily.service -n 100 --no-pager
systemctl status crypto-alpha-weekly.timer
```

The unit files intentionally do not embed `OPENAI_API_KEY`, Dune keys, wallet
keys, or exchange keys. Use host-local `.env` or root-owned systemd drop-ins for
configuration if needed.

## Job Outputs

Daily job:

- Updates `var/research.sqlite`.
- Appends to `var/memory/evidence.jsonl`.
- Writes dated daily, research, weekly, JSON, and manifest artifacts.
- Updates `var/reports/daily/latest.md`,
  `var/reports/daily/latest.evidence-run.json`, and
  `var/run-manifests/latest.json`.
- Writes a failed marker under `var/run-manifests/failed/` on controlled
  evidence-run failures.

Weekly job:

- Writes `var/reports/weekly/<week>-governance.md`.
- Writes `var/reports/weekly/<week>-ai-memo.md`.
- Writes `var/reports/iteration/<week>-iteration.md`.
- Writes `var/reports/iteration/<week>-iteration.json`.
- Refreshes `var/reports/iteration/latest.md` and
  `var/reports/iteration/latest.json`.

Monthly job:

- Writes rollout readiness JSON under `var/rollout/<family>/`.
- Writes the matching evidence package under `var/rollout/<family>/`.
- Does not grant live trading permission.

Backup job:

- Copies `var/research.sqlite` when present.
- Copies `var/memory/evidence.jsonl` when present.
- Creates compressed archives for `var/reports/` and
  `var/run-manifests/`.

## Updates

Use an explicit maintenance window:

```bash
cd /opt/crypto-alpha-agent
systemctl stop crypto-alpha-daily.timer crypto-alpha-weekly.timer \
  crypto-alpha-monthly.timer crypto-alpha-backup.timer
git pull --ff-only
docker compose build
docker compose run --rm crypto-alpha-agent llm-health-check
systemctl start crypto-alpha-daily.timer crypto-alpha-weekly.timer \
  crypto-alpha-monthly.timer crypto-alpha-backup.timer
```

If `llm-health-check` fails after an update, leave timers stopped, inspect the
provider configuration, and do not treat deterministic artifacts as a
successful product run.
