# Operator Runbook

This system is safe-by-default for local operation. The current workflow is
real data ingestion, validation, paper simulation, memory feedback, evidence
reporting, experiment planning, and rollout review. It uses ordinary public APIs
and a few hundred USD capital profile only for constraints. It uses no wallet
keys, no live order routing, and no live execution.
No wallet keys are required or read by the current workflow.

`evidence-run` is a one-shot command. External operator-controlled scheduling
may call it without making the agent an always-on daemon.

## Setup

1. Use Python 3.12.
2. Install dependencies with `uv sync --extra dev`.
3. Run commands from the repository root.
4. Keep durable paths under `var/`: SQLite in `var/research.sqlite`, memory in
   `var/memory/evidence.jsonl`, reports in `var/reports/`, run manifests and
   failed markers in `var/run-manifests/`, event artifacts in `var/events/`,
   logs in `var/log/`, locks in `var/locks/`, and rollout artifacts in
   `var/rollout/`.

## Environment

No exchange keys, wallet private keys, RPC secrets, or live API credentials are
required for the current operator workflow.

Local LLM credentials are optional operator configuration for offline-only
runs, but the real LLM paths use them for `plan-experiments`,
`research-loop`, and `evidence-report` when those commands are not explicitly
forced offline. Keep them in `.env` or the shell environment only, and never
commit or paste the values into docs, reports, memory, logs, screenshots, or
tests. The expected variable names are:

```env
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_API_TYPE=responses
OPENAI_MODEL=
OPENAI_RESEARCH_MODEL=
OPENAI_CODER_MODEL=
OPENAI_FAST_MODEL=
```

To smoke-test the configured LLM adapter without exposing secrets, run:

```bash
uv run --extra dev pytest \
  tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks \
  -q
```

The smoke test prints no API key, provider URL, provider headers, or raw HTTP
metadata. It validates only that the configured Responses-compatible endpoint
can return schema-valid research-only JSON. If this test fails because the
external provider is down or rejects the configured model, treat it as an
integration environment failure and keep deterministic fake LLM tests for
adversarial cases.

To run the CLI LLM paths explicitly in real mode, use `--no-offline-only`:

```bash
uv run --extra dev crypto-alpha-agent plan-experiments \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --current-capital-usd 300 \
  --no-offline-only

uv run --extra dev crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --no-offline-only

uv run --extra dev crypto-alpha-agent evidence-report \
  --daily \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/daily.md \
  --no-offline-only
```

Use `--offline-only` when you want deterministic local behavior regardless of
local credentials. In pytest runs, real LLM CLI paths are opt-in via
`CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1` so the standard regression suite stays
deterministic.

### Real LLM Test Policy

Local owner-directed development should run the real positive LLM integration
tests when credentials are configured. They cover the adapter smoke path,
`plan-experiments`, `research-loop`, and `evidence-report`:

```bash
uv run --extra dev pytest \
  tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks \
  tests/test_real_llm_integration_policy.py \
  -q
```

In CI or shared automation, set `CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS=1`
explicitly before running real provider tests. Without that opt-in, real LLM
integration tests skip rather than consuming credentials or network budget.
For deterministic local regression without real provider calls, run:

```bash
uv run --extra dev pytest -m "not llm_integration" -q
```

Fake/injected LLM tests remain the deterministic adversarial suite. Do not
replace them with real-model prompts for invalid JSON, schema violations,
live-order requests, wallet/private-key requests, MEV or premium-RPC requests,
high-capital requests, or malicious text that must be rejected by guards.

Before committing any LLM test-policy change, run the staged secret scan:

```bash
git diff --cached --name-only
uv run python -m crypto_alpha_agent.security.secret_scan --staged --fail-on-empty-with-untracked
```

For generated local surfaces, scan the relevant paths explicitly:

```bash
uv run python -m crypto_alpha_agent.security.secret_scan \
  --path var/memory/evidence.jsonl \
  --path var/reports/daily/latest.md \
  --path var/reports/weekly/latest.md \
  --path var/rollout/latest.json \
  --path var/run-manifests/latest.json
```

The scan reports only labels and surface names. It must not print configured
keys, provider URLs, local proxy values, raw provider headers, memory contents,
or raw LLM responses. If a real provider call fails because the provider is
down, times out, or rejects the configured model, record it as an integration
environment failure. Do not treat that as product success.

Some public crypto data endpoints may fail or timeout on the direct network
route. The operator may use a local proxy for source probes and data ingestion.
Keep proxy configuration local and record the source-health route as direct, proxy, blocked,
or not_applicable. The expected variable names are:

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

Dune is optional and credentialed. If used, load `DUNE_API_KEY` from a local
operator config outside git or from the shell environment. Do not paste real
keys into docs, commands saved in shell history, reports, or commits.

## Operator Baseline

Before and after local runs, check the worktree:

```bash
git status --short
```

The normal operator baseline is:

- `.env`, `.agents/`, `.claude/`, `var/`, caches, local reports, SQLite
  databases, logs, screenshots, and generated artifacts stay out of git.
- `.agents/` and `.claude/` are local AI-tool installs. They are not product
  deliverables unless a future approved plan explicitly promotes tooling into
  repository documentation or source.
- Local LLM and proxy settings stay in `.env` or the shell environment. Docs
  list variable names only, not configured values.
- Do not stage provider headers, raw keys, memory dumps, reports, databases,
  logs, screenshots, or generated artifacts.
- If `git status --short` shows unexpected files after an evidence run, decide
  whether they are product changes, local artifacts to ignore, or generated
  evidence that belongs under `var/` before starting another phase.

## Daily Sequence

1. Run an offline store check:

   ```bash
   uv run --extra dev crypto-alpha-agent ingest \
     --offline-check \
     --db var/research.sqlite \
     --current-capital-usd 300
   ```

2. Run the daily evidence pipeline:

   ```bash
   uv run --extra dev crypto-alpha-agent evidence-run \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --run-id 2026-05-18-funding-extremity \
     --report-out var/reports/daily/2026-05-18.md \
     --research-report-out var/reports/daily/2026-05-18.research.md \
     --json-out var/reports/daily/2026-05-18.json \
     --manifest-out var/run-manifests/evidence-run/2026-05-18-funding-extremity.json \
     --latest-report-out var/reports/daily/latest.md \
     --latest-json-out var/reports/daily/latest.json \
     --latest-manifest-out var/run-manifests/latest.json \
     --lock-path var/locks/evidence-run.lock \
     --failed-marker-out var/run-manifests/failed/2026-05-18-funding-extremity.json \
     --current-capital-usd 300 \
     --allow-network \
     --ccxt-exchange binance \
     --symbol BTC/USDT \
     --funding-symbol BTC/USDT:USDT \
     --timeframe 1h \
     --limit 200 \
     --strategy-family funding_extremity_price_confirmation \
     --include-defillama \
     --min-tvl-usd 10000 \
     --include-dexscreener \
     --dex-query "ETH USDC"
   ```

3. Generate or regenerate the daily report if needed:

   ```bash
   uv run --extra dev crypto-alpha-agent evidence-report --daily \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --out var/reports/daily/2026-05-18.md \
     --strategy-family funding_extremity_price_confirmation
   ```

4. Review the daily report, research-loop report, JSON payload, run manifest,
   JSON stdout capture, source health, skipped or failed steps, paper outcomes,
   validation evidence, memory records, and data quality notes. Preserve the
   artifacts before manual cleanup.

## Weekly Sequence

1. Build the weekly evidence report:

   ```bash
   uv run --extra dev crypto-alpha-agent evidence-report --weekly \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --out var/reports/weekly/2026-W21.md
   ```

2. Run bounded planning for the next experiments:

   ```bash
   uv run --extra dev crypto-alpha-agent plan-experiments \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --strategy-family funding_extremity_price_confirmation \
     --max-proposals 3 \
     --current-capital-usd 300 \
     --offline-only
   ```

3. If a strategy has at least 30 paper observations and clean walk-forward
   evidence, build a review artifact without enabling live execution:

   ```bash
   uv run --extra dev crypto-alpha-agent rollout-review \
     --db var/research.sqlite \
     --strategy-family funding_extremity_price_confirmation \
     --max-notional-usd 25 \
     --max-daily-loss-usd 10 \
     --artifact-out var/rollout/funding-extremity/tiny-live-readiness.json \
     --evidence-package-out var/rollout/funding-extremity/evidence-package.json
   ```

4. Preserve the evidence package and readiness artifact for tiny-live review.
   A passing review artifact is not permission to trade.

## Data Ingestion Workflow

All network ingestion requires `--allow-network`. Ingestion writes research data
only and does not submit orders or read wallet keys.

Binance Public Data:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source binance-public \
  --allow-network

uv run --extra dev crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --source binance-public \
  --symbol BTCUSDT \
  --timeframe 1h \
  --year 2026 \
  --month 5 \
  --allow-network \
  --report-out var/reports/daily/binance-public.md
```

CCXT OHLCV and funding:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed ohlcv \
  --exchange binance \
  --symbol BTC/USDT \
  --timeframe 1h \
  --limit 200

uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed funding-rate-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --limit 200
```

DexScreener:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source dexscreener \
  --allow-network \
  --query "ETH USDC"
```

DefiLlama:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source defillama \
  --allow-network \
  --min-tvl-usd 10000
```

Dune:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source dune \
  --allow-network \
  --dune-query-id 123456 \
  --dune-api-key "$DUNE_API_KEY" \
  --dune-param chain=ethereum
```

The Graph:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source thegraph \
  --allow-network \
  --subgraph-url "$THEGRAPH_SUBGRAPH_URL" \
  --graph-query '{ pools(first: 5) { id totalValueLockedUSD } }'
```

## Paper Simulation Workflow

Paper simulation requires stored OHLCV price bars and funding-rate history. Run
it after ingestion:

```bash
uv run --extra dev crypto-alpha-agent paper-sim-loop \
  --db var/research.sqlite \
  --strategy-family funding_extremity_price_confirmation \
  --price-symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --current-capital-usd 300 \
  --notional-usd 25 \
  --memory var/memory/evidence.jsonl \
  --report-out var/reports/paper/funding-extremity.json
```

Blocked or failed paper outcomes are evidence. Do not delete them because they
feed degradation detection and future experiment planning.

## Daily Report Workflow

The daily report workflow can be run by `evidence-run --report-out` or directly:

```bash
uv run --extra dev crypto-alpha-agent evidence-report --daily \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/daily/2026-05-18.md \
  --strategy-family funding_extremity_price_confirmation
```

What to inspect:

- `reason_codes`, `should_continue`, `should_collect_more_data`, and
  `should_stop_family`.
- Source health for CCXT, DexScreener, DefiLlama, Dune, and The Graph.
- Validation evidence count, paper outcome count, and sample progress toward
  30 paper observations.
- New or blocked candidates, data quality issues, and next experiment
  proposals.

## Weekly Report Workflow

```bash
uv run --extra dev crypto-alpha-agent evidence-report --weekly \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/weekly/2026-W21.md
```

What to inspect:

- Strategy family summaries, top rejected reasons, best improving family, and
  degraded families.
- Whether near-paper eligibility or near-tiny-live review is true.
- Whether artifact retention paths contain the daily Markdown/JSON captures,
  weekly reports, memory, SQLite, and rollout artifacts needed for audit.

## Replay/Recovery Workflow

Use replay/recovery only when an observability JSONL artifact already exists,
for example from `EventLogger` or an operator wrapper that deliberately writes
observability events. `evidence-run` itself writes stdout JSON, a durable JSON
payload, a run manifest, failed-run markers for nonzero exits, and daily/weekly
evidence artifacts; it does not automatically create
`var/events/research-observability.jsonl`.

```bash
uv run --extra dev crypto-alpha-agent replay \
  --events var/events/research-observability.jsonl

uv run --extra dev crypto-alpha-agent replay \
  --events var/events/research-observability.jsonl \
  --date 2026-05-18
```

Replay validates the event artifact, counts skipped malformed lines, and can
regenerate a daily observability report by UTC date. Preserve the original
event JSONL before manual cleanup. If no observability JSONL exists, recover
from the command stdout JSON, daily report, weekly report, memory file, SQLite
database snapshot, paper report JSON, rollout readiness artifact, and evidence
package.

## Failure Reasons And Meanings

| Reason code | Meaning |
| --- | --- |
| `missing_config` | Optional source was requested but required Dune or The Graph config was absent. |
| `source_failure` | Optional public data source failed; prior evidence should remain visible. |
| `insufficient_price_bars` | Paper simulation lacks enough OHLCV records. |
| `insufficient_funding_records` | Paper simulation lacks enough funding-rate records. |
| `insufficient_walk_forward` | Validation evidence is not strong enough for paper or rollout gates. |
| `stopped_family_skipped` | A degraded family marker exists and the run skipped that family by default. |
| `stopped_family_override_used` | Operator explicitly used `--allow-stopped-family`; audit this. |
| `degraded_expectancy` | Recent paper outcomes show negative or weakening expectancy. |
| `drawdown_breach` | Validation or paper evidence breached the configured drawdown threshold. |
| `insufficient_sample_size` | Rollout review has fewer than the required observations. |
| `max_loss_budget_breached` | `max_observed_loss_usd` exceeds the rollout loss budget. |

## How To Stop A Degraded Family

Daily and weekly reports can mark a family degraded automatically. To stop a
family manually, add a degraded marker to memory:

```bash
uv run --extra dev python - <<'PY'
from crypto_alpha_agent.pipeline.evidence_reports import mark_family_degraded

mark_family_degraded(
    "funding_extremity_price_confirmation",
    ["operator_stop", "degraded_expectancy"],
    "var/memory/evidence.jsonl",
)
PY
```

After the marker exists, `evidence-run`, `plan-experiments`, `research-loop`,
and scheduler plans skip that family by default. Use `--allow-stopped-family`
only for an explicit, auditable override.

## Evidence Preservation

Evidence package preservation is mandatory for tiny-live review. Keep:

- Daily Markdown/JSON captures from `evidence-run` and `evidence-report`.
- Weekly reports.
- `var/memory/evidence.jsonl`.
- `var/research.sqlite` and dated SQLite backups.
- Paper simulation JSON reports.
- Event JSONL used for replay/recovery.
- `rollout-review` readiness artifacts and evidence packages.

Do not rewrite reports to hide skipped lines, source failures, blocked
candidates, stopped families, or failed paper outcomes. Preserve original files
and append operator notes separately.

## External Scheduling Handoff

The agent has no internal daemon. The external operator-controlled scheduling
handoff is: cron or systemd calls exactly one `evidence-run`, captures stdout
and stderr log paths, sends a failure notification on nonzero exit (a
nonzero-exit notification), and applies artifact retention. The command should
be idempotent for the chosen date/run-id, should preserve idempotency through
stable artifact paths, and must use one-run-at-a-time locking.

Recommended wrapper shape:

```bash
#!/usr/bin/env bash
set -u

repo="${CRYPTO_ALPHA_AGENT_REPO:-/path/to/Crypto_Research_Agent}"
run_date="$(date -u +%F)"
week="$(date -u +%G-W%V)"
run_id="$run_date-funding-extremity"
lock="var/locks/evidence-run.lock"
stdout_log="var/log/evidence-run/$run_date.out.log"
stderr_log="var/log/evidence-run/$run_date.err.log"

mkdir -p var/locks var/log/evidence-run var/reports/daily \
  var/reports/weekly var/run-manifests/evidence-run var/run-manifests/failed

cd "$repo" || exit 1

uv run --extra dev crypto-alpha-agent evidence-run \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --run-id "$run_id" \
  --report-out "var/reports/daily/$run_date.md" \
  --research-report-out "var/reports/daily/$run_date.research.md" \
  --weekly-report-out "var/reports/weekly/$week.md" \
  --json-out "var/reports/daily/$run_date.json" \
  --manifest-out "var/run-manifests/evidence-run/$run_id.json" \
  --latest-report-out "var/reports/daily/latest.md" \
  --latest-json-out "var/reports/daily/latest.json" \
  --latest-manifest-out "var/run-manifests/latest.json" \
  --lock-path "$lock" \
  --failed-marker-out "var/run-manifests/failed/$run_id.json" \
  --current-capital-usd 300 \
  --allow-network \
  --ccxt-exchange binance \
  --symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200 \
  --strategy-family funding_extremity_price_confirmation \
  >"$stdout_log" \
  2>"$stderr_log"

status=$?
if [ "$status" -ne 0 ]; then
  /usr/local/bin/notify-crypto-alpha-failure "evidence-run failed: $status"
fi
exit "$status"
```

The wrapper shows log paths and product-level run locking explicitly. It keeps
stdout/stderr separate; stdout is the command JSON output for review. Do not
wrap the same lock path with `flock` unless you also pass `--no-lock`, because
the CLI lock uses exclusive file creation. Adjust the notification hook to local
email, chat, pager, or ticketing.

Recommended cron shape:

```cron
15 1 * * * /usr/local/bin/crypto-alpha-evidence-run.sh
```

Recommended systemd shape:

```ini
# /etc/systemd/system/crypto-alpha-evidence-run.service
[Service]
Type=oneshot
ExecStart=/usr/local/bin/crypto-alpha-evidence-run.sh

# /etc/systemd/system/crypto-alpha-evidence-run.timer
[Timer]
OnCalendar=*-*-* 01:15:00 UTC
Persistent=true
```

Retention guidance:

- Keep daily Markdown/JSON and stdout/stderr logs for at least 180 days.
- Keep weekly reports, memory, SQLite backups, and paper JSON for at least 365
  days.
- Keep rollout artifacts and evidence packages until the tiny-live review is
  closed and the operator has archived the decision record.
- Keep event JSONL used for replay/recovery with the matching daily report.

## Do Not Do Before Live Gates

Do not add exchange order routing, wallet signing, private-key loading,
unrestricted RPC writes, or autonomous live execution in this task. Do not
bypass risk approvals, manually edit reports to hide skipped lines, or treat
paper fills as proof of executable liquidity.
