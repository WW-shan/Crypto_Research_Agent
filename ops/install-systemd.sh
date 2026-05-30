#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$REPO"

systemd_dir="${CRYPTO_ALPHA_AGENT_SYSTEMD_DIR:-/etc/systemd/system}"
units=(ops/systemd/*.service ops/systemd/*.timer)

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY RUN: install systemd units to %q\n' "$systemd_dir"
  for unit in "${units[@]}"; do
    printf 'DRY RUN: install -m 0644 %q %q\n' "$unit" "${systemd_dir}/$(basename "$unit")"
  done
  printf 'DRY RUN: systemctl daemon-reload\n'
  printf 'DRY RUN: systemctl enable --now crypto-alpha-daily.timer crypto-alpha-weekly.timer crypto-alpha-monthly.timer crypto-alpha-backup.timer crypto-alpha-creation.timer\n'
  exit 0
fi

if [[ "$systemd_dir" == "/etc/systemd/system" ]]; then
  install_cmd=(sudo install -m 0644)
else
  mkdir -p "$systemd_dir"
  install_cmd=(install -m 0644)
fi

for unit in "${units[@]}"; do
  "${install_cmd[@]}" "$unit" "${systemd_dir}/$(basename "$unit")"
done

if [[ "${CRYPTO_ALPHA_AGENT_SKIP_SYSTEMCTL:-0}" != "1" ]]; then
  sudo systemctl daemon-reload
  sudo systemctl enable --now \
    crypto-alpha-daily.timer \
    crypto-alpha-weekly.timer \
    crypto-alpha-monthly.timer \
    crypto-alpha-backup.timer \
    crypto-alpha-creation.timer
fi
