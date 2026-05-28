#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

# Default command is intentionally literal for auditability: docker compose.
compose_cmd=(${CRYPTO_ALPHA_AGENT_COMPOSE:-docker compose})
proxy_env_args=()
if [[ -n "${CRYPTO_ALPHA_AGENT_DOCKER_PROXY:-}" ]]; then
  proxy_env_args=(
    -e "HTTP_PROXY=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
    -e "HTTPS_PROXY=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
    -e "ALL_PROXY=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
    -e "http_proxy=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
    -e "https_proxy=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
    -e "all_proxy=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
    -e "CRYPTO_ALPHA_AGENT_PROXY=${CRYPTO_ALPHA_AGENT_DOCKER_PROXY}"
  )
fi

week="$(date -u +%G-W%V)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

db_path="${CRYPTO_ALPHA_AGENT_DB:-var/research.sqlite}"
memory_path="${CRYPTO_ALPHA_AGENT_MEMORY:-var/memory/evidence.jsonl}"
strategy_family="${CRYPTO_ALPHA_AGENT_STRATEGY_FAMILY:-funding_extremity_price_confirmation}"
current_capital_usd="${CRYPTO_ALPHA_AGENT_CURRENT_CAPITAL_USD:-300}"
max_candidates="${CRYPTO_ALPHA_AGENT_MAX_CANDIDATES:-5}"

weekly_dir="var/reports/weekly"
iteration_dir="var/reports/iteration"
log_dir="var/log/weekly-review"

governance_out="${weekly_dir}/${week}-governance.md"
memo_out="${weekly_dir}/${week}-ai-memo.md"
iteration_out="${iteration_dir}/${week}-iteration.md"
iteration_json_out="${iteration_dir}/${week}-iteration.json"
latest_iteration_out="${iteration_dir}/latest.md"
latest_iteration_json_out="${iteration_dir}/latest.json"
stdout_log="${log_dir}/${timestamp}.stdout.log"
stderr_log="${log_dir}/${timestamp}.stderr.log"

mkdir -p \
  "$(dirname "$db_path")" \
  "$(dirname "$memory_path")" \
  "$weekly_dir" \
  "$iteration_dir" \
  "$log_dir"

governance_command=(
)
governance_command+=("${compose_cmd[@]}" run --rm)
if ((${#proxy_env_args[@]} > 0)); then
  governance_command+=("${proxy_env_args[@]}")
fi
governance_command+=(crypto-alpha-agent governance-report
  --db "$db_path"
  --memory "$memory_path"
  --out "$governance_out"
  --current-capital-usd "$current_capital_usd"
)

memo_command=(
)
memo_command+=("${compose_cmd[@]}" run --rm)
if ((${#proxy_env_args[@]} > 0)); then
  memo_command+=("${proxy_env_args[@]}")
fi
memo_command+=(crypto-alpha-agent ai-research-memo
  --db "$db_path"
  --memory "$memory_path"
  --out "$memo_out"
  --strategy-family "$strategy_family"
  --current-capital-usd "$current_capital_usd"
)

iteration_command=(
)
iteration_command+=("${compose_cmd[@]}" run --rm)
if ((${#proxy_env_args[@]} > 0)); then
  iteration_command+=("${proxy_env_args[@]}")
fi
iteration_command+=(crypto-alpha-agent iteration-cycle
  --db "$db_path"
  --memory "$memory_path"
  --out "$iteration_out"
  --json-out "$iteration_json_out"
  --strategy-family "$strategy_family"
  --current-capital-usd "$current_capital_usd"
  --max-candidates "$max_candidates"
)

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  print_dry_run() {
    printf 'DRY RUN:'
    printf ' %q' "$@"
    printf '\n'
  }
  print_dry_run "${governance_command[@]}"
  print_dry_run "${memo_command[@]}"
  print_dry_run "${iteration_command[@]}"
  printf 'DRY RUN: cp %q %q\n' "$iteration_out" "$latest_iteration_out"
  printf 'DRY RUN: cp %q %q\n' "$iteration_json_out" "$latest_iteration_json_out"
  printf 'stdout: %s\nstderr: %s\n' "$stdout_log" "$stderr_log"
  exit 0
fi

exec >"$stdout_log" 2>"$stderr_log"

printf 'Running governance-report for %s\n' "$week"
"${governance_command[@]}"
printf 'Running ai-research-memo for %s\n' "$week"
"${memo_command[@]}"
printf 'Running iteration-cycle for %s\n' "$week"
"${iteration_command[@]}"

cp "$iteration_out" "$latest_iteration_out"
cp "$iteration_json_out" "$latest_iteration_json_out"
