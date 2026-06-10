# Operator Runbook

This system is safe-by-default for local operation. The current workflow is
real data ingestion, validation, paper simulation, memory feedback, evidence
reporting, experiment planning, and rollout review. It uses ordinary public APIs
and a few hundred USD capital profile only for constraints. It uses no wallet
keys, no live order routing, and no live execution.
No wallet keys are required or read by the current workflow.

`evidence-run` is a one-shot command. External operator-controlled scheduling
may call it without making the agent an always-on daemon.

## Strategy Library

The current registry has three executable paper-simulated families:

- `funding_extremity_price_confirmation`
- `funding_mean_reversion_after_extreme`
- `funding_open_interest_crowding`

It also has three research-only watchlists:

- `defi_yield_regime_watchlist`
- `dex_liquidity_volume_watchlist`
- `volatility_compression_expansion_watchlist`

`funding_open_interest_crowding` requires OHLCV candles, funding-rate history,
and open-interest history. `volatility_compression_expansion_watchlist` is
watchlist-only; if it is sent to paper simulation, the registry fails closed
with `paper_simulation_not_supported`. Missing data and unqualified sources
remain documented as `blocked_by_missing_data` or
`blocked_by_unqualified_source` evidence instead of being promoted to live
capital.

## Setup

1. Use Python 3.12.
2. Install dependencies with `uv sync --extra dev`.
3. Run commands from the repository root.
4. Keep durable paths under `var/`: SQLite in `var/research.sqlite`, memory in
   `var/memory/evidence.jsonl`, reports in `var/reports/`, run manifests and
   failed markers in `var/run-manifests/`, event artifacts in `var/events/`,
   logs in `var/log/`, locks in `var/locks/`, and rollout artifacts in
   `var/rollout/`.

### VPS Docker Operations

For unattended VPS operation, use the Docker Compose plus host `systemd` timer
layer documented in `docs/vps-deployment.md`. Docker Compose pulls
`ghcr.io/ww-shan/crypto-alpha-agent:main` by default and mounts
`./var:/app/var`; systemd timers call short-lived wrappers instead of turning
the agent into an internal daemon. Local development and local soak runs can
set `CRYPTO_ALPHA_AGENT_IMAGE=crypto-alpha-agent:local` before
`docker compose build` to use the current working tree.

The standard timers are:

- `crypto-alpha-daily.timer` for daily `evidence-run`.
- `crypto-alpha-weekly.timer` for `governance-report`,
  `ai-research-memo`, and `iteration-cycle`.
- `crypto-alpha-monthly.timer` for owner `rollout-review` packages.
- `crypto-alpha-backup.timer` for SQLite, memory, reports, and manifest
  backups.

Run `docker compose run --rm crypto-alpha-agent llm-health-check` before
enabling timers. If the real LLM connection, structured schema response, or
runtime gate fails, leave the timers stopped. Expected VPS latest outputs
include `var/reports/daily/latest.md`,
`var/reports/iteration/latest.json`, and `var/run-manifests/latest.json`.
Secrets remain in local `.env`; `.env stays outside git`.

## Environment

No exchange keys, wallet private keys, RPC secrets, or live API credentials are
required for the current operator workflow.

The product runtime is LLM-native. Every product CLI command requires a
configured real LLM and a passing structured health check before business work
begins. The only bypasses are `llm-health-check`, `--help`, and `--version`.
Keep LLM credentials in `.env` or the shell environment only, and never commit
or paste the values into docs, reports, memory, logs, screenshots, or tests.
The expected variable names are:

```env
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_API_TYPE=responses
OPENAI_MODEL=
OPENAI_RESEARCH_MODEL=
OPENAI_CODER_MODEL=
OPENAI_FAST_MODEL=
```

To smoke-test the configured LLM adapter and runtime gate without exposing
secrets, run:

```bash
uv run --extra dev crypto-alpha-agent llm-health-check

uv run --extra dev pytest \
  tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks \
  -q
```

These checks print no API key, provider URL, provider headers, or raw HTTP
metadata. They validate that the configured Responses-compatible endpoint can
return schema-valid research-only JSON. If they fail because credentials are
missing, the external provider is down, the configured model rejects the task,
or schema validation fails, the product runtime is not healthy.

Product commands use the real LLM runtime directly:

```bash
uv run --extra dev crypto-alpha-agent plan-experiments \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --current-capital-usd 300

uv run --extra dev crypto-alpha-agent iteration-cycle \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/iteration/iteration-cycle.md \
  --json-out var/reports/iteration/iteration-cycle.json \
  --current-capital-usd 300

uv run --extra dev crypto-alpha-agent research-loop \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl

uv run --extra dev crypto-alpha-agent evidence-report \
  --daily \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/daily.md
```

Deterministic modules still normalize data, validate schemas, compute source
quality, run strategy validators, simulate paper outcomes, model costs, enforce
risk guards, redact secrets, and preserve evidence ledgers. They are
calculators and constraints inside the LLM-native flow; they do not define a
successful product run without the real LLM runtime.

### Real LLM Test Policy

Core acceptance tests call the configured real LLM and fail when credentials,
provider availability, JSON schema compliance, or guard validation fail. They
cover the adapter smoke path, health check, source probe, ingest, planning,
research loop, evidence report, governance report, historical bootstrap, and
rollout review:

```bash
uv run --extra dev pytest \
  tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks \
  tests/test_real_llm_integration_policy.py \
  -q
```

CI that runs the standard suite must provide valid real LLM configuration or
expect the real LLM acceptance tests to fail.
For local deterministic guard regression without real provider calls, run a
deliberately filtered non-product test pass:

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

For local ad hoc shell runs that rely on `.env`, export the local operator
configuration before invoking product commands:

```bash
set -a
source .env
set +a
```

The command output must still redact proxy values. CCXT-backed ingestion reads
the exported proxy variables and passes them to auto-created ccxt exchange
instances; if the variables are only present in `.env` but not exported to the
process environment, ad hoc `ingest` and `evidence-run` commands can fall back
to the direct route and timeout on exchange endpoints.

Dune is optional and credentialed. If used, load `DUNE_API_KEY` from a local
operator config outside git or from the shell environment. Do not paste real
keys into docs, commands saved in shell history, reports, or commits.

## Source Qualification Workflow

Run `source-probe` before treating a new endpoint as strategy evidence. The
workflow is:

1. Read the source coverage matrix in `docs/source-coverage-matrix.md` and the
   query catalog in `docs/source-query-catalog.md`.
2. List available targets without network access.
3. Probe without `--allow-network` first if you only want a blocked
   source-health row for audit.
4. Probe the direct route with `--allow-network --route direct`.
5. If direct public networking fails or times out, configure a local proxy in
   the shell environment and probe with `--route proxy`.
6. Inspect source-health rows before using the data in reports or validators.

```bash
uv run --extra dev crypto-alpha-agent source-probe --list-targets

uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history

uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_open_interest_history \
  --allow-network \
  --route direct

uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target binance_usdm_global_long_short_account_ratio \
  --allow-network \
  --route direct

uv run --extra dev crypto-alpha-agent source-probe \
  --db var/research.sqlite \
  --target dexscreener_pairs \
  --allow-network \
  --route proxy
```

`source-probe` writes source-health fields such as `network_route`,
`provider_status`, `status_transitions`, `http_status`, `parse_status`,
`typed_record_count`, `endpoint_family`, `url_family`, `schema_version`, and
`blocked_reason`. `ReachableViaProxy` means the local proxy route reached the
provider; it does not mean the source is production-ready. A source may become
`ResearchUsable` after a successful parse with nonzero typed rows.
`ProductionResearchSource` is reserved for repeated canary evidence with
fresh, non-duplicated, non-skewed data used by a typed validator.

Proxy configuration stays local. The JSON payload and source-health rows record
the route class, not the proxy URL or credentials. `DUNE_API_KEY` and optional
The Graph credentials are represented only by local configuration state or a
redacted credential marker; do not copy real values into memory, reports,
logs, screenshots, tests, or commits.

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

3. Run the upstream evidence-universe lab when the current work is data-depth
   or hypothesis discovery rather than paper simulation:

   ```bash
   uv run --extra dev crypto-alpha-agent evidence-universe-lab \
     --db var/research.sqlite \
     --memory var/memory/candidate-state.jsonl \
     --universe-preset liquid-usdm-top20 \
     --max-symbols 8 \
     --timeframe 1h \
     --start-year 2026 \
     --start-month 1 \
     --end-year 2026 \
     --end-month 5 \
     --min-unique-months 3 \
     --min-asset-count 3 \
     --min-split-count 3 \
     --purge-gap-bars 24 \
     --cost-bps-grid 5 \
     --cost-bps-grid 10 \
     --cost-bps-grid 20 \
     --cost-bps-grid 50 \
     --cost-aware-execution \
     --min-edge-over-cost-multiplier 2 \
     --max-turnover 0.5 \
     --collect \
     --allow-network \
     --persist-candidate-state \
     --out-dir var/reports/evidence-universe-lab/latest \
     --json-out var/reports/evidence-universe-lab/latest/evidence-universe-lab.json
   ```

   This command is read-only with respect to trading decisions. It may collect
   missing Binance Public Data records only when `--collect --allow-network` is
   explicit, then writes data-depth, feasibility v2, cost-aware execution,
   turnover-gated, and candidate-state artifacts. A blocked lab result must not
   be sent to backtest or paper.

   Round 25 extends this upstream lab route with canonical execution-history
   coverage, Binance USD-M funding/open-interest ingestion, endpoint-level
   derivatives metadata, and derivatives temporal observations. When running a
   Round 25 closeout, write artifacts to a round-specific directory such as
   `var/reports/evidence-universe-lab/round-25-derivatives-pit-main/` and keep
   `--persist-candidate-state` enabled. If feasible candidate count remains
   zero, do not run event-driven backtest, paper simulation, live execution,
   wallet access, or order routing. The 2026-06-10 Round 25 closeout evaluated
   11 candidates, found 0 feasible candidates, and therefore kept the backtest
   gate closed.

4. Generate or regenerate the daily report if needed:

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

2. Build the profit governance report when a weekly or monthly owner review is
   due:

   ```bash
   uv run --extra dev crypto-alpha-agent governance-report \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --out var/reports/monthly/2026-05-governance.md \
     --current-capital-usd 300
   ```

   The report is read-only and paper-only. It includes a weekly family
   scoreboard, profit review, stopped-family ledger, paper-only portfolio
   selector, and monthly owner review. Use it to decide whether each family
   should keep collecting, stop, redesign validator, add data, or move near an
   owner decision review. A governance report never allocates real capital and
   never enables live order routing.

3. Build the Phase 5 expansion preparation report:

   ```bash
   uv run --extra dev crypto-alpha-agent expansion-prep-report \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --out var/reports/phase5/expansion-prep.md \
     --current-capital-usd 300
   ```

   The report is read-only. It ranks future source and strategy expansion
   candidates, surfaces stable blocked reasons, and keeps live execution
   blocked.

4. Run bounded planning for the next experiments:

   ```bash
   uv run --extra dev crypto-alpha-agent plan-experiments \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --strategy-family funding_extremity_price_confirmation \
     --max-proposals 3 \
     --current-capital-usd 300
   ```

5. Generate the weekly AI research memo:

   ```bash
   uv run --extra dev crypto-alpha-agent ai-research-memo \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --out var/reports/weekly/2026-W21-ai-memo.md \
     --current-capital-usd 300
   ```

   The memo is evidence-grounded and read-only. It summarizes what changed,
   what failed, what should stop, and the next bounded experiment. It cannot
   create paper outcomes, bypass registered validators, route orders, or use
   live execution.

6. Run the guarded LLM-native iteration cycle:

   ```bash
   uv run --extra dev crypto-alpha-agent iteration-cycle \
     --db var/research.sqlite \
     --memory var/memory/evidence.jsonl \
     --out var/reports/iteration/2026-W21-iteration-cycle.md \
     --json-out var/reports/iteration/2026-W21-iteration-cycle.json \
     --current-capital-usd 300 \
     --max-candidates 5
   ```

   The command emits strict `IterationCandidate` records from the configured
   real planning LLM and then applies deterministic guards. It is a review
   artifact only: `auto_executes_changes=false`, autonomous code-writing loop
   remains proposal-only, and autonomous new data source discovery remains
   probe-gated through source discovery queries and `source-probe` targets. It
   cannot write code, run tests, promote a `ProductionResearchSource`, place
   orders, or schedule its own next command.

7. If a strategy has at least 30 paper observations and clean walk-forward
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

8. Preserve the evidence package and readiness artifact for tiny-live review.
   A passing review artifact is not permission to trade.

## Historical Bootstrap Workflow

Use `historical-bootstrap` after the evidence factory layers are available and
before treating a long-running campaign as meaningful. The command builds a
historical bootstrap report, machine-readable JSON payload, and run manifest.
It can run offline for audit, or it can use `--allow-network` to collect public
historical source windows. Network mode requires at least one explicit
`YYYY-MM-DD/YYYY-MM-DD` bootstrap window. It never reads wallet keys, routes
orders, or uses real capital.

```bash
uv run --extra dev crypto-alpha-agent historical-bootstrap \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/phase7/historical-bootstrap.md \
  --json-out var/reports/phase7/historical-bootstrap.json \
  --manifest-out var/run-manifests/historical-bootstrap/2026-05-24.json \
  --run-id 2026-05-24-phase7-bootstrap \
  --price-symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --bootstrap-window 2026-02-01/2026-03-01 \
  --bootstrap-window 2026-03-01/2026-04-01 \
  --bootstrap-window 2026-04-01/2026-05-01 \
  --strategy-family funding_extremity_price_confirmation \
  --strategy-family funding_mean_reversion_after_extreme \
  --strategy-family funding_open_interest_crowding \
  --current-capital-usd 300 \
  --allow-network \
  --ccxt-exchange binance \
  --binance-symbol BTCUSDT \
  --limit 1000 \
  --notional-usd 25
```

What to inspect:

- Bootstrap windows: start/end dates, symbols, timeframe, and stored record
  counts.
- Source collection: Binance Public Data, CCXT funding history, CCXT
  open-interest history, and source probes such as
  `binance_usdm_global_long_short_account_ratio`.
- Strategy results: validation status, trade count, blocked reasons, paper
  outcomes, cost-model modes, governance action, and classification.
- Forward 30/60/90 evidence targets: current forward observations by family,
  30 and 60 paper observation targets, and the 90 calendar-day target.
- Out-of-sample policy: future out-of-sample paper observations must come from
  later `evidence-run` runs; historical bootstrap windows are not profit proof.

If `--allow-network` is omitted, blocked source steps are expected and should
be preserved as audit evidence. If network collection succeeds, preserve the
historical bootstrap report, JSON payload, manifest, SQLite snapshot, memory
file, and any source-health rows before starting the future daily evidence
campaign. Historical bootstrap paper outcomes are report-local and do not count
as forward out-of-sample sample progress. If a network-enabled source
collection step fails, the manifest is marked failed and the CLI exits nonzero.

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

uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed open-interest-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200
```

Binance USD-M first-party derivatives context:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source binance-usdm \
  --allow-network \
  --binance-usdm-feed funding-rate-history \
  --symbol BTCUSDT \
  --limit 1000

uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source binance-usdm \
  --allow-network \
  --binance-usdm-feed open-interest-history \
  --symbol BTCUSDT \
  --period 1h \
  --limit 500
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
  --venue binance \
  --cost-model-mode pessimistic \
  --max-signal-age-seconds 3600 \
  --max-volume-participation-rate 0.05 \
  --memory var/memory/evidence.jsonl \
  --report-out var/reports/paper/funding-extremity.json
```

The Phase 10 default for paper simulation is `cost_model_mode=pessimistic`.
This records maker/taker fee assumptions for the configured public venue, uses
taker-style fee floors unless explicitly overridden, applies fixed slippage
bps, enforces symbol-level min notional, quantity step, and tick-size
constraints, checks funding signal age, and models missed or `partial_fill`
outcomes when candle volume cannot support the requested notional. Keep this
mode as the default before rollout review.

Blocked or failed paper outcomes are evidence. Do not delete them because they
feed degradation detection and future experiment planning.

For `funding_open_interest_crowding`, also ingest open-interest history before
validation or paper simulation:

```bash
uv run --extra dev crypto-alpha-agent ingest \
  --db var/research.sqlite \
  --source ccxt \
  --allow-network \
  --ccxt-feed open-interest-history \
  --exchange binance \
  --symbol BTC/USDT:USDT \
  --timeframe 1h \
  --limit 200

uv run --extra dev crypto-alpha-agent paper-sim-loop \
  --db var/research.sqlite \
  --strategy-family funding_open_interest_crowding \
  --price-symbol BTC/USDT \
  --funding-symbol BTC/USDT:USDT \
  --timeframe 1h \
  --current-capital-usd 300 \
  --notional-usd 25 \
  --memory var/memory/evidence.jsonl \
  --report-out var/reports/paper/funding-oi-crowding.json
```

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

## Profit Governance Workflow

```bash
uv run --extra dev crypto-alpha-agent governance-report \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/monthly/2026-05-governance.md \
  --current-capital-usd 300
```

What to inspect:

- Weekly family scoreboard metrics: sample size, net PnL, cost-adjusted
  expectancy, max drawdown, hit rate, failure rate, source-health quality,
  stale-signal rate, and walk-forward stability.
- Profit review decisions: whether each family is improving, worth more data,
  should stop, or is near an owner decision review.
- Stopped-family ledger entries with reason, date, evidence refs, and revival
  conditions.
- Paper-only portfolio selector rankings for future paper observations. These
  rankings allocate no real capital.
- Monthly owner review comparison against doing nothing, fees, opportunity
  cost, and the owner's capital constraints.

## AI Research Memo Workflow

```bash
uv run --extra dev crypto-alpha-agent ai-research-memo \
  --db var/research.sqlite \
  --memory var/memory/evidence.jsonl \
  --out var/reports/weekly/2026-W21-ai-memo.md
```

The memo reads the same local evidence ledgers and memory used by
`plan-experiments`. It carries no execution authority: AI proposals must cite
existing validation or paper evidence, or an explicit supported data gap, and
they may only select a registered validator or propose a design-only validator
template that still needs deterministic tests and human review.

What to inspect:

- What changed in family sample size, validation count, and recommended action.
- What failed, including rejected reason codes from weekly evidence and
  experiment planning.
- Which stopped or degraded families should remain blocked.
- Which next experiment or validator-template proposal is suggested, with
  evidence refs.

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
| `min_notional_exceeds_max_notional` | The symbol cannot be tested inside the current `max_notional_usd <= 25` owner profile. |
| `stale_signal` | The signal-to-entry delay exceeded the configured ordinary execution age limit. |
| `pre_cost_only_profitable` | The candidate had positive gross PnL but fees and slippage made net PnL non-positive. |
| `missed_fill_assumed` | Pessimistic volume participation says the requested notional would not fill. |
| `partial_fill` | Partial-fill mode reduced paper notional because full liquidity was unavailable. |
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
- Historical bootstrap Markdown/JSON reports and manifests.
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
