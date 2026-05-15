# Operator Runbook

This system is safe-by-default for local operation. The CLI commands below are deterministic and offline unless a later live gate explicitly changes that behavior.

## Setup

1. Use Python 3.12.
2. Install dependencies with `uv sync --dev`.
3. Run commands from the repository root.
4. Keep event logs under a local path such as `var/events.jsonl`.

## Environment

No exchange keys, wallet private keys, RPC secrets, or live API credentials are required for Task 19 operation.

If live credentials exist in your shell, do not rely on them here. The Task 19 CLI does not need them and should be treated as an offline operator surface.

## Safe Dry Runs

Use these commands for smoke checks:

```bash
uv run crypto-alpha-agent scan --dry-run
uv run crypto-alpha-agent research --dry-run
uv run crypto-alpha-agent backtest --dry-run
uv run crypto-alpha-agent paper --dry-run
```

Each command prints one JSON object to stdout. The JSON includes `live_api_calls: false` and `uses_real_capital: false`.

## Reports

Generate a daily report from persisted observability events:

```bash
uv run crypto-alpha-agent report --events var/events.jsonl --date 2026-05-16
```

The report is regenerated from JSONL events, skips malformed lines, and includes event counts, decision counts, approval/block totals, reason-code counts, metric summaries, and event details. The event file must exist, and `--date` must be a UTC calendar date in `YYYY-MM-DD` format. Events with offset timestamps are grouped by their UTC date.

## Replay Recovery

Use replay after an interrupted run, partial write, or suspicious report:

```bash
uv run crypto-alpha-agent replay --events var/events.jsonl
uv run crypto-alpha-agent replay --events var/events.jsonl --date 2026-05-16
```

Without `--date`, replay reports loaded event counts, skipped malformed lines, and counts by event type. With `--date`, it also regenerates the daily report for that UTC date. Replay requires an existing event file and rejects invalid date values before loading events.

If `skipped_event_lines` is greater than zero, inspect the JSONL file around the interrupted write. Preserve the original file before manual cleanup so the recovery trail remains auditable.

## Paper-Only Constraints

Paper mode is not live trading. It must not:

- Use wallet private keys.
- Submit live exchange orders.
- Transfer funds.
- Depend on live balances.
- Assume fills are executable in production.

Paper results are evidence for review, not permission to trade.

## Risk Approval Basics

Before any candidate moves beyond research or paper simulation, confirm:

- Expected value is positive after fees, slippage, latency, and borrow/funding costs.
- Capital required is within configured opportunity and portfolio limits.
- Daily loss and drawdown limits are not breached.
- Evidence references are present and reproducible.
- A human approval checkpoint exists for any non-paper action.

Blocks from the risk guardian are final until the underlying reason code is resolved and replayed.

## Do Not Do Before Live Gates

Do not add exchange order routing, wallet signing, private-key loading, unrestricted RPC writes, or autonomous live execution in this task. Do not bypass risk approvals, manually edit reports to hide skipped lines, or treat paper fills as proof of executable liquidity.
