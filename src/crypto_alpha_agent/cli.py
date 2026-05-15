from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from crypto_alpha_agent.observability.logging import load_events
from crypto_alpha_agent.observability.reports import generate_daily_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = args.handler(args)
    print(json.dumps(payload, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crypto-alpha-agent",
        description="Operate the crypto alpha research agent in local safe modes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_dry_run_command(
        subparsers,
        "scan",
        "Run the offline market scanner smoke path.",
        _handle_scan,
    )
    _add_dry_run_command(
        subparsers,
        "research",
        "Run the offline research planning smoke path.",
        _handle_research,
    )
    _add_dry_run_command(
        subparsers,
        "backtest",
        "Run a deterministic backtest smoke path.",
        _handle_backtest,
    )
    _add_dry_run_command(
        subparsers,
        "paper",
        "Run a paper-execution smoke path without real capital.",
        _handle_paper,
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Generate a daily report from an event JSONL file.",
    )
    report_parser.add_argument("--events", required=True, type=Path, help="Path to persisted event JSONL.")
    report_parser.add_argument("--date", required=True, help="UTC report date in YYYY-MM-DD format.")
    report_parser.set_defaults(handler=_handle_report)

    replay_parser = subparsers.add_parser(
        "replay",
        help="Load persisted events, count them, and optionally regenerate a daily report.",
    )
    replay_parser.add_argument("--events", required=True, type=Path, help="Path to persisted event JSONL.")
    replay_parser.add_argument("--date", help="Optional UTC report date in YYYY-MM-DD format.")
    replay_parser.set_defaults(handler=_handle_replay)

    return parser


def _add_dry_run_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    handler: Any,
) -> None:
    command_parser = subparsers.add_parser(name, help=help_text)
    command_parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="Required safety flag; performs only deterministic local work.",
    )
    command_parser.set_defaults(handler=handler)


def _base_payload(command: str) -> dict[str, Any]:
    return {
        "command": command,
        "mode": "dry_run",
        "live_api_calls": False,
        "uses_real_capital": False,
    }


def _handle_scan(_args: argparse.Namespace) -> dict[str, Any]:
    return {
        **_base_payload("scan"),
        "signals_scanned": 0,
        "opportunities": [],
        "notes": ["offline dry run only", "no providers configured"],
    }


def _handle_research(_args: argparse.Namespace) -> dict[str, Any]:
    return {
        **_base_payload("research"),
        "hypotheses_generated": 0,
        "required_evidence": [
            "venue liquidity",
            "fee and slippage assumptions",
            "risk approval before any paper action",
        ],
    }


def _handle_backtest(_args: argparse.Namespace) -> dict[str, Any]:
    return {
        **_base_payload("backtest"),
        "result": {
            "net_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "trade_count": 0,
            "fee_adjusted_expectancy": 0.0,
            "slippage_adjusted_expectancy": 0.0,
        },
        "artifact_refs": [],
    }


def _handle_paper(_args: argparse.Namespace) -> dict[str, Any]:
    return {
        **_base_payload("paper"),
        "orders_submitted": 0,
        "touched_real_capital": False,
        "constraints": ["paper account only", "no wallet access", "no exchange order routing"],
    }


def _handle_report(args: argparse.Namespace) -> dict[str, Any]:
    loaded = load_events(args.events)
    report = generate_daily_report(
        loaded.events,
        args.date,
        skipped_event_lines=loaded.skipped_count,
    )
    return {
        "command": "report",
        "event_path": str(args.events),
        "loaded_events": len(loaded.events),
        "skipped_event_lines": loaded.skipped_count,
        "report": report.model_dump(mode="json"),
    }


def _handle_replay(args: argparse.Namespace) -> dict[str, Any]:
    loaded = load_events(args.events)
    payload: dict[str, Any] = {
        "command": "replay",
        "event_path": str(args.events),
        "loaded_events": len(loaded.events),
        "skipped_event_lines": loaded.skipped_count,
        "event_type_counts": dict(sorted(Counter(event.event_type for event in loaded.events).items())),
    }
    if args.date:
        report = generate_daily_report(
            loaded.events,
            args.date,
            skipped_event_lines=loaded.skipped_count,
        )
        payload["report"] = report.model_dump(mode="json")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
