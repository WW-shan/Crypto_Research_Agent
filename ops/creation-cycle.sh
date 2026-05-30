#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ACTIVE_WORKTREE="${CRYPTO_ALPHA_AGENT_ACTIVE_WORKTREE:-${REPO}/var/autonomy/active-worktree}"
RUN_REPO="$REPO"
if [[ -d "$ACTIVE_WORKTREE" ]]; then
  RUN_REPO="$ACTIVE_WORKTREE"
fi
cd "$RUN_REPO"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
db_path="${CRYPTO_ALPHA_AGENT_DB:-var/research.sqlite}"
memory_path="${CRYPTO_ALPHA_AGENT_MEMORY:-var/memory/evidence.jsonl}"
autonomy_root="${CRYPTO_ALPHA_AGENT_AUTONOMY_ROOT:-var/autonomy}"
reports_root="${CRYPTO_ALPHA_AGENT_REPORTS_ROOT:-var/reports}"
max_creations="${CRYPTO_ALPHA_AGENT_MAX_CREATIONS:-1}"
log_dir="${CRYPTO_ALPHA_AGENT_CREATION_LOG_DIR:-var/log/creation-cycle}"
stdout_log="${log_dir}/${timestamp}.stdout.log"
stderr_log="${log_dir}/${timestamp}.stderr.log"
latest_markdown="${reports_root}/creation/latest.md"
latest_json="${reports_root}/creation/latest.json"
# Default latest artifacts: var/reports/creation/latest.md and var/reports/creation/latest.json.

mkdir -p \
  "$(dirname "$db_path")" \
  "$(dirname "$memory_path")" \
  "$autonomy_root" \
  "${autonomy_root}/tasks" \
  "${autonomy_root}/worktrees" \
  "${reports_root}/creation" \
  "$log_dir"

command=(
  uv run crypto-alpha-agent creation-cycle
  --db "$db_path"
  --memory "$memory_path"
  --autonomy-root "$autonomy_root"
  --task-root "${autonomy_root}/tasks"
  --worktree-root "${autonomy_root}/worktrees"
  --reports-root "$reports_root"
  --repo-root "$RUN_REPO"
  --max-creations "$max_creations"
)

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY RUN:'
  printf ' %q' "${command[@]}"
  printf '\n'
  printf 'DRY RUN: latest markdown %q\n' "$latest_markdown"
  printf 'DRY RUN: latest json %q\n' "$latest_json"
  printf 'stdout: %s\nstderr: %s\n' "$stdout_log" "$stderr_log"
  exit 0
fi

exec "${command[@]}" >"$stdout_log" 2>"$stderr_log"
