#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

# Default command is intentionally literal for auditability: docker compose.
compose_cmd=(${CRYPTO_ALPHA_AGENT_COMPOSE:-docker compose})

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
day="$(date -u +%F)"
run_id="daily-${timestamp}"

db_path="${CRYPTO_ALPHA_AGENT_DB:-var/research.sqlite}"
memory_path="${CRYPTO_ALPHA_AGENT_MEMORY:-var/memory/evidence.jsonl}"
strategy_family="${CRYPTO_ALPHA_AGENT_STRATEGY_FAMILY:-funding_extremity_price_confirmation}"
symbol="${CRYPTO_ALPHA_AGENT_SYMBOL:-BTC/USDT}"
funding_symbol="${CRYPTO_ALPHA_AGENT_FUNDING_SYMBOL:-BTC/USDT:USDT}"
timeframe="${CRYPTO_ALPHA_AGENT_TIMEFRAME:-1h}"
limit="${CRYPTO_ALPHA_AGENT_LIMIT:-200}"
current_capital_usd="${CRYPTO_ALPHA_AGENT_CURRENT_CAPITAL_USD:-300}"
ccxt_exchange="${CRYPTO_ALPHA_AGENT_CCXT_EXCHANGE:-binance}"

report_out="var/reports/daily/${day}.md"
research_report_out="var/reports/research/${day}.md"
weekly_report_out="var/reports/weekly/${day}-from-daily.md"
json_out="var/reports/daily/${day}.evidence-run.json"
manifest_out="var/run-manifests/evidence-run/${run_id}.json"
latest_report_out="var/reports/daily/latest.md"
latest_json_out="var/reports/daily/latest.evidence-run.json"
latest_manifest_out="var/run-manifests/latest.json"
failed_marker_out="var/run-manifests/failed/${run_id}.json"
lock_path="var/locks/evidence-run.lock"
stdout_log="var/log/evidence-run/${run_id}.stdout.log"
stderr_log="var/log/evidence-run/${run_id}.stderr.log"

mkdir -p \
  "$(dirname "$db_path")" \
  "$(dirname "$memory_path")" \
  "$(dirname "$report_out")" \
  "$(dirname "$research_report_out")" \
  "$(dirname "$weekly_report_out")" \
  "$(dirname "$json_out")" \
  "$(dirname "$manifest_out")" \
  "$(dirname "$latest_manifest_out")" \
  "$(dirname "$failed_marker_out")" \
  "$(dirname "$lock_path")" \
  "$(dirname "$stdout_log")" \
  "$(dirname "$stderr_log")"

command=(
  "${compose_cmd[@]}" run --rm crypto-alpha-agent evidence-run
  --db "$db_path"
  --memory "$memory_path"
  --report-out "$report_out"
  --research-report-out "$research_report_out"
  --weekly-report-out "$weekly_report_out"
  --json-out "$json_out"
  --manifest-out "$manifest_out"
  --latest-report-out "$latest_report_out"
  --latest-json-out "$latest_json_out"
  --latest-manifest-out "$latest_manifest_out"
  --failed-marker-out "$failed_marker_out"
  --lock-path "$lock_path"
  --current-capital-usd "$current_capital_usd"
  --ccxt-exchange "$ccxt_exchange"
  --symbol "$symbol"
  --funding-symbol "$funding_symbol"
  --timeframe "$timeframe"
  --limit "$limit"
  --strategy-family "$strategy_family"
  --run-id "$run_id"
)

if [[ "${CRYPTO_ALPHA_AGENT_ALLOW_NETWORK:-1}" == "1" ]]; then
  command+=(--allow-network)
fi

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY RUN:'
  printf ' %q' "${command[@]}"
  printf '\nstdout: %s\nstderr: %s\n' "$stdout_log" "$stderr_log"
  exit 0
fi

"${command[@]}" >"$stdout_log" 2>"$stderr_log"
