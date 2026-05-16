from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from crypto_alpha_agent.data.ingestion import (
    ingest_binance_public_month,
    ingest_ccxt_funding_rate_history,
    ingest_ccxt_ohlcv,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.observability.logging import load_events
from crypto_alpha_agent.observability.reports import generate_daily_report
from crypto_alpha_agent.pipeline.markdown import render_research_loop_markdown
from crypto_alpha_agent.pipeline.memory import persist_paper_outcome_memory
from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop
from crypto_alpha_agent.scheduler import build_daily_schedule_plan


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
    report_parser.add_argument("--events", required=True, type=_existing_event_path, help="Path to persisted event JSONL.")
    report_parser.add_argument("--date", required=True, type=_utc_date, help="UTC report date in YYYY-MM-DD format.")
    report_parser.set_defaults(handler=_handle_report)

    replay_parser = subparsers.add_parser(
        "replay",
        help="Load persisted events, count them, and optionally regenerate a daily report.",
    )
    replay_parser.add_argument("--events", required=True, type=_existing_event_path, help="Path to persisted event JSONL.")
    replay_parser.add_argument("--date", type=_utc_date, help="Optional UTC report date in YYYY-MM-DD format.")
    replay_parser.set_defaults(handler=_handle_replay)

    research_loop_parser = subparsers.add_parser(
        "research-loop",
        help="Run the stored-data research loop from existing SQLite records.",
    )
    research_loop_parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Path to the SQLite research data store.",
    )
    research_loop_parser.add_argument(
        "--current-capital-usd",
        type=_positive_finite_float,
        default=300.0,
        help="Operator capital profile used for research constraints.",
    )
    research_loop_parser.add_argument("--source", help="Optional source filter.")
    research_loop_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before Binance Public Data ingestion.",
    )
    research_loop_parser.add_argument("--symbol", help="Binance spot symbol for public data ingestion.")
    research_loop_parser.add_argument(
        "--timeframe",
        help="Binance public klines interval for ingestion.",
    )
    research_loop_parser.add_argument("--year", type=_positive_int, help="Positive UTC year for ingestion.")
    research_loop_parser.add_argument("--month", type=_month_number, help="UTC month for ingestion, 1-12.")
    research_loop_parser.add_argument(
        "--record-type",
        choices=("market_candle", "funding_rate", "dex_pair", "defi_yield", "source_health"),
        help="Optional record type filter.",
    )
    research_loop_parser.add_argument("--limit", type=_positive_int, help="Optional positive record limit.")
    research_loop_parser.add_argument("--run-id", help="Optional research loop run identifier.")
    research_loop_parser.add_argument(
        "--include-validation",
        action="store_true",
        help="Include historical validation summaries from stored market candles.",
    )
    research_loop_parser.add_argument(
        "--include-paper-evidence",
        action="store_true",
        help="Attach paper simulation evidence packages from stored paper outcomes.",
    )
    research_loop_parser.add_argument("--report-out", type=Path, help="Optional Markdown report output path.")
    research_loop_parser.set_defaults(handler=_handle_research_loop, parser=research_loop_parser)

    paper_sim_loop_parser = subparsers.add_parser(
        "paper-sim-loop",
        help="Run deterministic paper simulation outcomes from stored validation data.",
    )
    paper_sim_loop_parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Path to the SQLite research data store.",
    )
    paper_sim_loop_parser.add_argument("--strategy-family", required=True, help="Strategy family to simulate.")
    paper_sim_loop_parser.add_argument("--price-symbol", required=True, help="Stored market candle symbol.")
    paper_sim_loop_parser.add_argument("--funding-symbol", required=True, help="Stored funding-rate symbol.")
    paper_sim_loop_parser.add_argument("--timeframe", required=True, help="Stored market candle timeframe.")
    paper_sim_loop_parser.add_argument("--run-id", help="Optional paper simulation run identifier.")
    paper_sim_loop_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used to cap paper notional.",
    )
    paper_sim_loop_parser.add_argument(
        "--notional-usd",
        type=_non_negative_finite_float,
        default=25.0,
        help="Requested per-trade paper notional before low-capital caps.",
    )
    paper_sim_loop_parser.add_argument(
        "--threshold-abs",
        type=_positive_finite_float,
        default=0.0005,
        help="Absolute funding-rate threshold for an extreme signal.",
    )
    paper_sim_loop_parser.add_argument(
        "--hold-bars",
        type=_positive_int,
        default=1,
        help="Number of price bars to hold each paper simulation outcome.",
    )
    paper_sim_loop_parser.add_argument(
        "--fee-rate",
        type=_non_negative_finite_float,
        default=0.001,
        help="One-way fee rate charged on entry and exit.",
    )
    paper_sim_loop_parser.add_argument(
        "--slippage-rate",
        type=_non_negative_finite_float,
        default=0.0005,
        help="One-way slippage rate charged on entry and exit.",
    )
    paper_sim_loop_parser.add_argument(
        "--min-trades",
        type=_non_negative_int,
        default=3,
        help="Minimum generated trade count required by validation.",
    )
    paper_sim_loop_parser.add_argument(
        "--require-walk-forward",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require walk-forward validation splits.",
    )
    paper_sim_loop_parser.add_argument("--report-out", type=Path, help="Optional JSON report output path.")
    paper_sim_loop_parser.add_argument(
        "--memory",
        type=Path,
        help="Optional JSONL memory path for paper outcome feedback records.",
    )
    paper_sim_loop_parser.set_defaults(handler=_handle_paper_sim_loop, parser=paper_sim_loop_parser)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Initialize safe research data ingestion without live capital or order routing.",
    )
    ingest_parser.add_argument(
        "--offline-check",
        action="store_true",
        help="Create/open the research SQLite store and report safe defaults without network access.",
    )
    ingest_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    ingest_parser.add_argument(
        "--current-capital-usd",
        type=float,
        default=300.0,
        help="Operator capital profile used for research constraints.",
    )
    ingest_parser.add_argument(
        "--source",
        action="append",
        choices=("binance-public", "ccxt", "dexscreener", "defillama"),
        default=[],
        help="Optional real-data source declaration. Repeat for multiple sources.",
    )
    ingest_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before declaring any network-backed source.",
    )
    ingest_parser.add_argument(
        "--ccxt-feed",
        choices=("ohlcv", "funding-rate-history"),
        help="CCXT feed to ingest when --source ccxt is provided.",
    )
    ingest_parser.add_argument(
        "--exchange",
        default="binance",
        help="CCXT exchange id for research data ingestion.",
    )
    ingest_parser.add_argument("--symbol", help="CCXT market symbol to ingest.")
    ingest_parser.add_argument("--timeframe", help="CCXT OHLCV timeframe, required for --ccxt-feed ohlcv.")
    ingest_parser.add_argument("--since", type=int, help="Optional CCXT since timestamp in milliseconds.")
    ingest_parser.add_argument("--limit", type=_positive_int, help="Optional positive CCXT record limit.")
    ingest_parser.set_defaults(handler=_handle_ingest, parser=ingest_parser)

    schedule_parser = subparsers.add_parser(
        "schedule",
        help="Build a local dry-run daily job plan without sleeping or running commands.",
    )
    schedule_parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="Required safety flag; emits a plan only.",
    )
    schedule_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    schedule_parser.add_argument("--report-out", required=True, type=Path, help="Planned Markdown report output path.")
    schedule_parser.add_argument("--memory", type=Path, help="Optional memory artifact path to include in the plan.")
    schedule_parser.add_argument(
        "--current-capital-usd",
        type=_positive_finite_float,
        default=300.0,
        help="Operator capital profile used for research constraints.",
    )
    schedule_parser.add_argument("--run-id", help="Optional research loop run identifier.")
    schedule_parser.add_argument(
        "--include-validation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Plan historical validation summaries from stored market candles.",
    )
    schedule_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before planning Binance Public Data ingestion.",
    )
    schedule_parser.add_argument("--source", choices=("binance-public",), help="Optional ingestion source.")
    schedule_parser.add_argument("--symbol", help="Binance spot symbol for public data ingestion.")
    schedule_parser.add_argument(
        "--timeframe",
        default="1h",
        help="Binance public klines interval for ingestion.",
    )
    schedule_parser.add_argument("--year", type=_positive_int, help="Positive UTC year for ingestion.")
    schedule_parser.add_argument("--month", type=_month_number, help="UTC month for ingestion, 1-12.")
    schedule_parser.set_defaults(handler=_handle_schedule, parser=schedule_parser)

    return parser


def _existing_event_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"event file does not exist: {raw_path}")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"event path is not a file: {raw_path}")
    return path


def _existing_sqlite_db_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"SQLite DB does not exist: {raw_path}")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"SQLite DB path is not a file: {raw_path}")
    return path


def _utc_date(raw_date: str) -> date:
    try:
        return date.fromisoformat(raw_date)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid UTC date {raw_date!r}; expected YYYY-MM-DD") from exc


def _positive_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid positive integer: {raw_value!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"invalid positive integer: {raw_value!r}")
    return value


def _month_number(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid month: {raw_value!r}; expected 1-12") from exc
    if value < 1 or value > 12:
        raise argparse.ArgumentTypeError(f"invalid month: {raw_value!r}; expected 1-12")
    return value


def _positive_finite_float(raw_value: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid finite positive capital: {raw_value!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"invalid finite positive capital: {raw_value!r}")
    return value


def _non_negative_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid non-negative integer: {raw_value!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError(f"invalid non-negative integer: {raw_value!r}")
    return value


def _non_negative_finite_float(raw_value: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid finite non-negative value: {raw_value!r}") from exc
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(f"invalid finite non-negative value: {raw_value!r}")
    return value


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


def _handle_research_loop(args: argparse.Namespace) -> dict[str, Any]:
    ingestion = None
    source = _normalize_research_loop_source(args.source)
    if source == "binance_public" and _has_binance_ingestion_intent(args):
        _validate_binance_research_loop_ingestion_args(args)
        ingestion = ingest_binance_public_month(
            db_path=args.db,
            symbol=args.symbol,
            interval=args.timeframe or "1h",
            year=args.year,
            month=args.month,
            allow_network=True,
        )
    else:
        _require_existing_sqlite_db(args.parser, args.db)

    report = run_stored_research_loop(
        args.db,
        current_capital_usd=args.current_capital_usd,
        source=source,
        record_type=args.record_type,
        limit=args.limit,
        run_id=args.run_id,
        include_validation=args.include_validation,
        include_paper_evidence=args.include_paper_evidence,
    )
    payload = {
        "command": "research-loop",
        "mode": "research_only",
        "uses_real_capital": False,
        "live_order_routing": False,
        "report": report.model_dump(mode="json"),
    }
    if args.report_out is not None:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(render_research_loop_markdown(report), encoding="utf-8")
        payload["report_artifact"] = str(args.report_out)
    if ingestion is not None:
        payload["ingestion"] = ingestion.model_dump(mode="json")
    return payload


def _normalize_research_loop_source(source: str | None) -> str | None:
    if source == "binance-public":
        return "binance_public"
    return source


def _has_binance_ingestion_intent(args: argparse.Namespace) -> bool:
    return bool(
        args.allow_network
        or args.symbol is not None
        or args.year is not None
        or args.month is not None
        or args.timeframe is not None
    )


def _require_existing_sqlite_db(parser: argparse.ArgumentParser, db_path: Path) -> None:
    try:
        _existing_sqlite_db_path(str(db_path))
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))


def _validate_binance_research_loop_ingestion_args(args: argparse.Namespace) -> None:
    if not args.allow_network:
        args.parser.error("--allow-network is required when --source binance-public is provided")
    missing = [
        option
        for option, value in (
            ("--symbol", args.symbol),
            ("--year", args.year),
            ("--month", args.month),
        )
        if value is None
    ]
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source binance-public is provided")


def _handle_ingest(args: argparse.Namespace) -> dict[str, Any]:
    ingestion = None
    if args.offline_check and args.source:
        args.parser.error("--offline-check cannot be combined with --source")
    if _has_ccxt_ingestion_intent(args):
        _validate_ccxt_ingest_args(args)
        ingestion = _run_ccxt_ingestion(args)

    if args.source and not args.allow_network:
        args.parser.error("--allow-network is required when --source is provided")
    if not args.offline_check and not args.source:
        args.parser.error("--offline-check is required unless --source is provided")

    mode = "network_declared"
    if args.offline_check:
        ResearchDataStore(args.db)
        mode = "offline_check"

    payload = {
        "command": "ingest",
        "mode": mode,
        "db_path": str(args.db),
        "sources_requested": args.source,
        "network_allowed": args.allow_network,
        "uses_real_capital": False,
        "live_order_routing": False,
        "capital_profile": {
            "current_capital_usd": args.current_capital_usd,
            "low_latency_required": False,
            "premium_rpc_required": False,
        },
        "notes": [
            "ingestion is for research and paper validation only",
            "no live orders are submitted",
            "no wallet keys are read",
        ],
    }
    if ingestion is not None:
        payload["ingestion"] = ingestion.model_dump(mode="json")
    return payload


def _handle_paper_sim_loop(args: argparse.Namespace) -> dict[str, Any]:
    _require_existing_sqlite_db(args.parser, args.db)
    try:
        report = run_paper_sim_loop(
            args.db,
            run_id=args.run_id,
            strategy_family=args.strategy_family,
            price_symbol=args.price_symbol,
            funding_symbol=args.funding_symbol,
            timeframe=args.timeframe,
            current_capital_usd=args.current_capital_usd,
            notional_usd=args.notional_usd,
            threshold_abs=args.threshold_abs,
            hold_bars=args.hold_bars,
            fee_rate=args.fee_rate,
            slippage_rate=args.slippage_rate,
            min_trades=args.min_trades,
            require_walk_forward=args.require_walk_forward,
        )
    except ValueError as exc:
        args.parser.error(str(exc))

    memory_records = []
    if args.memory is not None:
        memory_records = persist_paper_outcome_memory(report.outcomes, args.memory)

    payload = {
        "command": "paper-sim-loop",
        "mode": "paper_simulation_only",
        "uses_real_capital": False,
        "live_order_routing": False,
        "memory_records_written": len(memory_records),
        "memory_path": str(args.memory) if args.memory is not None else None,
        "report": report.model_dump(mode="json"),
    }
    if args.report_out is not None:
        payload["report_artifact"] = str(args.report_out)
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _has_ccxt_ingestion_intent(args: argparse.Namespace) -> bool:
    ccxt_sources = [source for source in args.source if source == "ccxt"]
    return bool(
        ccxt_sources
        or args.ccxt_feed is not None
        or args.symbol is not None
        or args.timeframe is not None
        or args.since is not None
        or args.limit is not None
    )


def _validate_ccxt_ingest_args(args: argparse.Namespace) -> None:
    if set(args.source) != {"ccxt"}:
        args.parser.error("CCXT ingestion flags require --source ccxt and cannot be combined with other sources")
    if not args.allow_network:
        args.parser.error("--allow-network is required when --source ccxt is provided")

    missing = [
        option
        for option, value in (
            ("--ccxt-feed", args.ccxt_feed),
            ("--symbol", args.symbol),
        )
        if value is None
    ]
    if args.ccxt_feed == "ohlcv" and args.timeframe is None:
        missing.append("--timeframe")
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source ccxt is provided")
    if args.ccxt_feed == "funding-rate-history" and args.timeframe is not None:
        args.parser.error("--timeframe cannot be combined with --ccxt-feed funding-rate-history")


def _run_ccxt_ingestion(args: argparse.Namespace):
    if args.ccxt_feed == "ohlcv":
        return ingest_ccxt_ohlcv(
            args.db,
            symbol=args.symbol,
            timeframe=args.timeframe,
            since=args.since,
            limit=args.limit,
            allow_network=True,
            exchange_id=args.exchange,
        )
    return ingest_ccxt_funding_rate_history(
        args.db,
        symbol=args.symbol,
        since=args.since,
        limit=args.limit,
        allow_network=True,
        exchange_id=args.exchange,
    )


def _handle_schedule(args: argparse.Namespace) -> dict[str, Any]:
    try:
        plan = build_daily_schedule_plan(
            db_path=args.db,
            report_out=args.report_out,
            memory_path=args.memory,
            current_capital_usd=args.current_capital_usd,
            run_id=args.run_id,
            include_validation=args.include_validation,
            allow_network=args.allow_network,
            source=args.source,
            symbol=args.symbol,
            timeframe=args.timeframe,
            year=args.year,
            month=args.month,
        )
    except ValueError as exc:
        args.parser.error(str(exc))
    return plan.model_dump(mode="json")


if __name__ == "__main__":
    raise SystemExit(main())
