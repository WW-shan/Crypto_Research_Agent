#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="var/backups/${timestamp}"

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY RUN: mkdir -p %q\n' "$backup_dir"
  printf 'DRY RUN: copy var/research.sqlite when present\n'
  printf 'DRY RUN: copy var/memory/evidence.jsonl when present\n'
  printf 'DRY RUN: tar -czf %q -C var reports\n' "${backup_dir}/reports.tgz"
  printf 'DRY RUN: tar -czf %q -C var run-manifests\n' "${backup_dir}/run-manifests.tgz"
  exit 0
fi

mkdir -p "$backup_dir"

if [[ -f var/research.sqlite ]]; then
  cp var/research.sqlite "$backup_dir/research.sqlite"
fi

if [[ -f var/memory/evidence.jsonl ]]; then
  mkdir -p "$backup_dir/memory"
  cp var/memory/evidence.jsonl "$backup_dir/memory/evidence.jsonl"
fi

if [[ -d var/reports ]]; then
  tar -czf "$backup_dir/reports.tgz" -C var reports
fi

if [[ -d var/run-manifests ]]; then
  tar -czf "$backup_dir/run-manifests.tgz" -C var run-manifests
fi
