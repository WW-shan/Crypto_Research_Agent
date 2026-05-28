#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

# Default command is intentionally literal for auditability: docker compose.
compose_cmd=(${CRYPTO_ALPHA_AGENT_COMPOSE:-docker compose})

if [[ -z "${CRYPTO_ALPHA_AGENT_REVIEW_FAMILY:-}" ]]; then
  echo "CRYPTO_ALPHA_AGENT_REVIEW_FAMILY is required for monthly rollout-review." >&2
  exit 2
fi

month="$(date -u +%Y-%m)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

db_path="${CRYPTO_ALPHA_AGENT_DB:-var/research.sqlite}"
strategy_family="$CRYPTO_ALPHA_AGENT_REVIEW_FAMILY"
review_dir="var/rollout/${strategy_family}"
log_dir="var/log/monthly-owner-review"
artifact_out="${review_dir}/${month}-rollout.json"
evidence_package_out="${review_dir}/${month}-evidence-package.json"
stdout_log="${log_dir}/${timestamp}.stdout.log"
stderr_log="${log_dir}/${timestamp}.stderr.log"

mkdir -p \
  "$(dirname "$db_path")" \
  "$review_dir" \
  "$log_dir"

command=(
  "${compose_cmd[@]}" run --rm crypto-alpha-agent rollout-review
  --db "$db_path"
  --strategy-family "$strategy_family"
  --artifact-out "$artifact_out"
  --evidence-package-out "$evidence_package_out"
)

if [[ -n "${CRYPTO_ALPHA_AGENT_HUMAN_APPROVAL_REFERENCE:-}" ]]; then
  command+=(--human-approved --human-approval-reference "$CRYPTO_ALPHA_AGENT_HUMAN_APPROVAL_REFERENCE")
fi

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY RUN:'
  printf ' %q' "${command[@]}"
  printf '\nstdout: %s\nstderr: %s\n' "$stdout_log" "$stderr_log"
  exit 0
fi

"${command[@]}" >"$stdout_log" 2>"$stderr_log"
