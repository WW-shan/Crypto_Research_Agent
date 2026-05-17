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
    ingest_defillama_yield_pools,
    ingest_dexscreener_pairs,
)
from crypto_alpha_agent.data.onchain_ingestion import (
    ingest_dune_query_result,
    ingest_thegraph_query_result,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.observability.logging import load_events
from crypto_alpha_agent.observability.reports import generate_daily_report
from crypto_alpha_agent.pipeline.evidence_runner import run_daily_evidence_pipeline
from crypto_alpha_agent.pipeline.evidence_reports import (
    build_daily_evidence_report,
    build_weekly_evidence_report,
)
from crypto_alpha_agent.pipeline.markdown import (
    render_daily_evidence_report_markdown,
    render_research_loop_markdown,
    render_weekly_evidence_report_markdown,
)
from crypto_alpha_agent.pipeline.memory import (
    persist_paper_outcome_memory,
    persist_research_loop_memory,
    persist_validation_evidence_memory,
)
from crypto_alpha_agent.risk.rollout import build_rollout_review_artifact
from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
from crypto_alpha_agent.pipeline.experiment_planner import plan_next_experiments
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop
from crypto_alpha_agent.scheduler import build_daily_schedule_plan
from crypto_alpha_agent.strategy import default_strategy_registry


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
        choices=(
            "market_candle",
            "funding_rate",
            "dex_pair",
            "defi_yield",
            "research_snapshot",
            "source_health",
        ),
        help="Optional record type filter.",
    )
    research_loop_parser.add_argument("--limit", type=_positive_int, help="Optional positive record limit.")
    research_loop_parser.add_argument("--run-id", help="Optional research loop run identifier.")
    research_loop_parser.add_argument(
        "--include-validation",
        action="store_true",
        help="Include historical validation summaries from stored market candles.",
    )
    research_loop_parser.add_argument("--strategy-family", help="Optional registered strategy validator family.")
    research_loop_parser.add_argument("--price-symbol", help="Stored market candle symbol for strategy validation.")
    research_loop_parser.add_argument("--funding-symbol", help="Stored funding-rate symbol for strategy validation.")
    research_loop_parser.add_argument("--validation-timeframe", help="Stored market candle timeframe for strategy validation.")
    research_loop_parser.add_argument(
        "--threshold-abs",
        type=_positive_finite_float,
        default=0.0005,
        help="Absolute funding-rate threshold for strategy validation.",
    )
    research_loop_parser.add_argument(
        "--hold-bars",
        type=_positive_int,
        default=1,
        help="Number of price bars to hold for strategy validation.",
    )
    research_loop_parser.add_argument(
        "--fee-rate",
        type=_non_negative_finite_float,
        default=0.001,
        help="One-way fee rate for strategy validation.",
    )
    research_loop_parser.add_argument(
        "--slippage-rate",
        type=_non_negative_finite_float,
        default=0.0005,
        help="One-way slippage rate for strategy validation.",
    )
    research_loop_parser.add_argument(
        "--min-trades",
        type=_non_negative_int,
        default=3,
        help="Minimum generated trade count required by strategy validation.",
    )
    research_loop_parser.add_argument(
        "--include-paper-evidence",
        action="store_true",
        help="Attach paper simulation evidence packages from stored paper outcomes.",
    )
    research_loop_parser.add_argument("--report-out", type=Path, help="Optional Markdown report output path.")
    research_loop_parser.add_argument(
        "--memory",
        type=Path,
        help="Optional JSONL memory path for research-loop feedback records.",
    )
    research_loop_parser.add_argument(
        "--allow-stopped-family",
        action="store_true",
        help="Explicitly allow validation for a stopped strategy family.",
    )
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

    rollout_review_parser = subparsers.add_parser(
        "rollout-review",
        help="Build rollout gate evidence and tiny-live readiness review artifacts.",
    )
    rollout_review_parser.add_argument(
        "--db",
        required=True,
        type=_existing_sqlite_db_path,
        help="Path to an existing SQLite research data store.",
    )
    rollout_review_parser.add_argument("--strategy-family", required=True, help="Strategy family to review.")
    rollout_review_parser.add_argument(
        "--human-approved",
        action="store_true",
        help="Record that a human approved this rollout review package.",
    )
    rollout_review_parser.add_argument("--human-approval-reference", help="Human approval ticket or record reference.")
    rollout_review_parser.add_argument(
        "--max-notional-usd",
        type=_non_negative_finite_float,
        default=25.0,
        help="Maximum tiny-live notional considered by the readiness review.",
    )
    rollout_review_parser.add_argument(
        "--max-daily-loss-usd",
        type=_non_negative_finite_float,
        default=10.0,
        help="Maximum tiny-live daily loss budget considered by the readiness review.",
    )
    rollout_review_parser.add_argument("--artifact-out", type=Path, help="Optional readiness artifact JSON path.")
    rollout_review_parser.add_argument(
        "--evidence-package-out",
        type=Path,
        help="Optional rollout evidence package JSON path.",
    )
    rollout_review_parser.set_defaults(handler=_handle_rollout_review)

    plan_experiments_parser = subparsers.add_parser(
        "plan-experiments",
        help="Plan bounded evidence experiments without live capital or order routing.",
    )
    plan_experiments_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    plan_experiments_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    plan_experiments_parser.add_argument("--strategy-family", help="Optional registered strategy family to plan.")
    plan_experiments_parser.add_argument(
        "--max-proposals",
        type=_positive_int,
        default=3,
        help="Maximum experiment proposals to emit.",
    )
    plan_experiments_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used to cap paper notional.",
    )
    plan_experiments_parser.add_argument(
        "--offline-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep planning deterministic and offline.",
    )
    plan_experiments_parser.set_defaults(handler=_handle_plan_experiments)

    evidence_report_parser = subparsers.add_parser(
        "evidence-report",
        help="Generate deterministic daily or weekly evidence Markdown reports.",
    )
    report_mode = evidence_report_parser.add_mutually_exclusive_group(required=True)
    report_mode.add_argument("--daily", action="store_true", help="Write a daily evidence report.")
    report_mode.add_argument("--weekly", action="store_true", help="Write a weekly evidence report.")
    evidence_report_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    evidence_report_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    evidence_report_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown report.")
    evidence_report_parser.add_argument(
        "--strategy-family",
        action="append",
        default=[],
        help="Strategy family to include in daily report. Repeat for multiple families.",
    )
    evidence_report_parser.set_defaults(handler=_handle_evidence_report)

    evidence_run_parser = subparsers.add_parser(
        "evidence-run",
        help="Run the safe end-to-end evidence pipeline without live capital.",
    )
    evidence_run_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    evidence_run_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    evidence_run_parser.add_argument("--report-out", required=True, type=Path, help="Path for the daily Markdown report.")
    evidence_run_parser.add_argument("--weekly-report-out", type=Path, help="Optional path for weekly evidence Markdown.")
    evidence_run_parser.add_argument(
        "--current-capital-usd",
        type=_positive_finite_float,
        default=300.0,
        help="Operator capital profile used for research constraints.",
    )
    evidence_run_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before network-backed evidence ingestion.",
    )
    evidence_run_parser.add_argument("--ccxt-exchange", default="binance", help="CCXT exchange id.")
    evidence_run_parser.add_argument("--symbol", required=True, help="CCXT market symbol for OHLCV ingestion.")
    evidence_run_parser.add_argument(
        "--funding-symbol",
        required=True,
        help="CCXT funding symbol for funding-rate ingestion and validation.",
    )
    evidence_run_parser.add_argument("--timeframe", required=True, help="CCXT OHLCV timeframe.")
    evidence_run_parser.add_argument("--limit", type=_positive_int, default=200, help="Record limit for CCXT ingestion.")
    evidence_run_parser.add_argument(
        "--strategy-family",
        action="append",
        default=[],
        help="Strategy family to validate and paper-simulate. Repeat to run multiple families.",
    )
    evidence_run_parser.add_argument(
        "--allow-stopped-family",
        action="store_true",
        help="Explicitly allow validation and paper simulation for stopped strategy families.",
    )
    evidence_run_parser.add_argument("--run-id", help="Optional evidence run identifier.")
    evidence_run_parser.add_argument(
        "--include-defillama",
        action="store_true",
        help="Optionally ingest DefiLlama yield pools.",
    )
    evidence_run_parser.add_argument(
        "--include-dexscreener",
        action="store_true",
        help="Optionally ingest DexScreener pairs.",
    )
    evidence_run_parser.add_argument("--dex-query", help="DexScreener search query.")
    evidence_run_parser.add_argument(
        "--min-tvl-usd",
        type=_positive_finite_float,
        help="Optional minimum TVL for DefiLlama ingestion.",
    )
    evidence_run_parser.add_argument(
        "--include-dune",
        action="store_true",
        help="Optionally ingest a Dune query result.",
    )
    evidence_run_parser.add_argument("--dune-query-id", type=_positive_int, help="Dune query id to run.")
    evidence_run_parser.add_argument("--dune-api-key", help="Dune API key.")
    evidence_run_parser.add_argument(
        "--dune-param",
        action="append",
        type=_key_value_pair,
        default=[],
        metavar="KEY=VALUE",
        help="Dune query parameter. Repeat for multiple parameters.",
    )
    evidence_run_parser.add_argument(
        "--include-thegraph",
        action="store_true",
        help="Optionally ingest a The Graph query result.",
    )
    evidence_run_parser.add_argument("--subgraph-url", help="The Graph subgraph endpoint URL.")
    evidence_run_parser.add_argument("--graph-query", help="The Graph query document.")
    evidence_run_parser.add_argument(
        "--graph-variable",
        action="append",
        type=_key_value_pair,
        default=[],
        metavar="KEY=VALUE",
        help="The Graph variable. Repeat for multiple variables.",
    )
    evidence_run_parser.set_defaults(handler=_handle_evidence_run, parser=evidence_run_parser)

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
        choices=("binance-public", "ccxt", "dexscreener", "defillama", "dune", "thegraph"),
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
    ingest_parser.add_argument("--query", help="DexScreener search query.")
    ingest_parser.add_argument("--chain", help="DexScreener chain id for token lookup.")
    ingest_parser.add_argument(
        "--token-address",
        action="append",
        default=[],
        help="DexScreener token address for chain lookup. Repeat for multiple tokens.",
    )
    ingest_parser.add_argument(
        "--min-tvl-usd",
        type=_positive_finite_float,
        help="Minimum DefiLlama yield pool TVL in USD.",
    )
    ingest_parser.add_argument("--dune-query-id", type=_positive_int, help="Dune query id to persist.")
    ingest_parser.add_argument("--dune-api-key", help="Dune API key for network-backed query results.")
    ingest_parser.add_argument(
        "--dune-param",
        action="append",
        type=_key_value_pair,
        default=[],
        metavar="KEY=VALUE",
        help="Dune query parameter. Repeat for multiple parameters.",
    )
    ingest_parser.add_argument("--subgraph-url", help="The Graph subgraph endpoint URL.")
    ingest_parser.add_argument("--graph-query", help="The Graph query document.")
    ingest_parser.add_argument(
        "--graph-variable",
        action="append",
        type=_key_value_pair,
        default=[],
        metavar="KEY=VALUE",
        help="The Graph variable. Repeat for multiple variables.",
    )
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
        "--offline-check",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include an offline ingest check before the planned evidence run.",
    )
    schedule_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before network-backed evidence ingestion.",
    )
    schedule_parser.add_argument("--ccxt-exchange", default="binance", help="CCXT exchange id.")
    schedule_parser.add_argument("--symbol", required=True, help="CCXT market symbol for OHLCV ingestion.")
    schedule_parser.add_argument(
        "--funding-symbol",
        required=True,
        help="CCXT funding symbol for funding-rate ingestion and validation.",
    )
    schedule_parser.add_argument(
        "--timeframe",
        default="1h",
        help="CCXT OHLCV timeframe.",
    )
    schedule_parser.add_argument("--limit", type=_positive_int, default=200, help="Record limit for CCXT ingestion.")
    schedule_parser.add_argument(
        "--strategy-family",
        action="append",
        default=[],
        help="Strategy family to validate and paper-simulate. Repeat to run multiple families.",
    )
    schedule_parser.add_argument(
        "--allow-stopped-family",
        action="store_true",
        help="Explicitly plan stopped strategy families for evidence-run.",
    )
    schedule_parser.add_argument(
        "--include-defillama",
        action="store_true",
        help="Optionally plan DefiLlama yield pool ingestion.",
    )
    schedule_parser.add_argument(
        "--include-dexscreener",
        action="store_true",
        help="Optionally plan DexScreener pair ingestion.",
    )
    schedule_parser.add_argument("--dex-query", help="DexScreener search query.")
    schedule_parser.add_argument(
        "--min-tvl-usd",
        type=_positive_finite_float,
        help="Optional minimum TVL for DefiLlama ingestion.",
    )
    schedule_parser.add_argument(
        "--include-dune",
        action="store_true",
        help="Optionally plan a Dune query result.",
    )
    schedule_parser.add_argument("--dune-query-id", type=_positive_int, help="Dune query id to run.")
    schedule_parser.add_argument("--dune-api-key", help="Dune API key.")
    schedule_parser.add_argument(
        "--dune-param",
        action="append",
        type=_key_value_pair,
        default=[],
        metavar="KEY=VALUE",
        help="Dune query parameter. Repeat for multiple parameters.",
    )
    schedule_parser.add_argument(
        "--include-thegraph",
        action="store_true",
        help="Optionally plan a The Graph query result.",
    )
    schedule_parser.add_argument("--subgraph-url", help="The Graph subgraph endpoint URL.")
    schedule_parser.add_argument("--graph-query", help="The Graph query document.")
    schedule_parser.add_argument(
        "--graph-variable",
        action="append",
        type=_key_value_pair,
        default=[],
        metavar="KEY=VALUE",
        help="The Graph variable. Repeat for multiple variables.",
    )
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


def _key_value_pair(raw_value: str) -> tuple[str, str]:
    key, separator, value = raw_value.partition("=")
    if not separator or not key.strip():
        raise argparse.ArgumentTypeError(f"invalid KEY=VALUE argument: {raw_value!r}")
    return key.strip(), value


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
    _validate_research_loop_strategy_args(args)
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
        strategy_family=args.strategy_family,
        price_symbol=args.price_symbol,
        funding_symbol=args.funding_symbol,
        validation_timeframe=args.validation_timeframe,
        threshold_abs=args.threshold_abs,
        hold_bars=args.hold_bars,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
        min_trades=args.min_trades,
        include_paper_evidence=args.include_paper_evidence,
        memory_path=args.memory,
        allow_stopped_family=args.allow_stopped_family,
    )
    memory_records = []
    validation_memory_records = []
    if args.memory is not None:
        memory_records = persist_research_loop_memory(report, args.memory)
        if args.include_validation:
            validation_evidence = ValidationEvidenceLedger(args.db).load_evidence(
                run_id=report.run_id
            )
            if validation_evidence:
                validation_memory_records = persist_validation_evidence_memory(
                    validation_evidence,
                    args.memory,
                    run_id=report.run_id,
                )

    payload = {
        "command": "research-loop",
        "mode": "research_only",
        "uses_real_capital": False,
        "live_order_routing": False,
        "report": report.model_dump(mode="json"),
        "stopped_family_override_used": "stopped_family_override_used" in report.decision_reason_codes,
    }
    if args.memory is not None:
        payload["memory_records_written"] = len(memory_records)
        payload["memory_path"] = str(args.memory)
        payload["validation_memory_records_written"] = len(validation_memory_records)
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


def _validate_research_loop_strategy_args(args: argparse.Namespace) -> None:
    strategy_options = [
        args.price_symbol,
        args.funding_symbol,
        args.validation_timeframe,
    ]
    if args.strategy_family is None and any(value is not None for value in strategy_options):
        args.parser.error("--strategy-family is required when strategy validation symbols are provided")
    if args.strategy_family is None:
        return
    if not args.include_validation:
        args.parser.error("--include-validation is required when --strategy-family is provided")
    registry = default_strategy_registry(current_capital_usd=args.current_capital_usd)
    strategy_family = args.strategy_family.strip()
    requires_funding_parameters = True
    if strategy_family in registry.list_families():
        spec = registry.get(strategy_family)
        requires_funding_parameters = _requires_funding_validation_parameters(
            spec.required_record_types
        )
    if not requires_funding_parameters:
        return
    missing = [
        option
        for option, value in (
            ("--price-symbol", args.price_symbol),
            ("--funding-symbol", args.funding_symbol),
            ("--validation-timeframe", args.validation_timeframe),
        )
        if value is None
    ]
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --strategy-family is provided")


def _requires_funding_validation_parameters(required_record_types: tuple[str, ...]) -> bool:
    return {"market_candle", "funding_rate"}.issubset(set(required_record_types))


def _handle_ingest(args: argparse.Namespace) -> dict[str, Any]:
    ingestion = None
    if args.offline_check and args.source:
        args.parser.error("--offline-check cannot be combined with --source")
    if _has_onchain_ingestion_intent(args):
        _validate_onchain_ingest_args(args)
        ingestion = _run_onchain_ingestion(args)
    elif _has_dex_or_defi_ingestion_intent(args):
        _validate_dex_or_defi_ingest_args(args)
        ingestion = _run_dex_or_defi_ingestion(args)
    elif _has_ccxt_ingestion_intent(args):
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
        memory_records = persist_paper_outcome_memory(
            report.outcomes,
            args.memory,
            replace_run=True,
        )

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


def _handle_rollout_review(args: argparse.Namespace) -> dict[str, Any]:
    review = build_rollout_review_artifact(
        db_path=args.db,
        strategy_family=args.strategy_family,
        human_approved=args.human_approved,
        human_approval_reference=args.human_approval_reference,
        max_notional_usd=args.max_notional_usd,
        max_daily_loss_usd=args.max_daily_loss_usd,
    )
    payload = review.model_dump(mode="json")

    if args.artifact_out is not None:
        payload["readiness_artifact_path"] = str(args.artifact_out)
        payload["evidence_package"]["artifact_path"] = str(args.artifact_out)
    if args.evidence_package_out is not None:
        payload["evidence_package_out"] = str(args.evidence_package_out)
        payload["evidence_package"]["evidence_package_path"] = str(args.evidence_package_out)

    if args.artifact_out is not None:
        args.artifact_out.parent.mkdir(parents=True, exist_ok=True)
        args.artifact_out.write_text(
            json.dumps(payload["readiness_artifact"], sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.evidence_package_out is not None:
        args.evidence_package_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_package_out.write_text(
            json.dumps(payload["evidence_package"], sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return payload


def _handle_plan_experiments(args: argparse.Namespace) -> dict[str, Any]:
    result = plan_next_experiments(
        db_path=args.db,
        memory_path=args.memory,
        strategy_family=args.strategy_family,
        max_proposals=args.max_proposals,
        current_capital_usd=args.current_capital_usd,
        offline_only=args.offline_only,
    )
    return {
        "command": "plan-experiments",
        "current_capital_usd": args.current_capital_usd,
        "proposals": [
            proposal.model_dump(mode="json")
            for proposal in result.proposals
        ],
        "degraded_strategy_families": result.degraded_strategy_families,
        "accepted": result.accepted,
        "rejected_reason_codes": result.rejected_reason_codes,
        "uses_real_capital": False,
        "live_order_routing": False,
    }


def _handle_evidence_report(args: argparse.Namespace) -> dict[str, Any]:
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.daily:
        report = build_daily_evidence_report(
            db_path=args.db,
            memory_path=args.memory,
            strategy_families=args.strategy_family,
        )
        args.out.write_text(render_daily_evidence_report_markdown(report), encoding="utf-8")
        return {
            "command": "evidence-report",
            "daily_report_out": str(args.out),
            "report": report.model_dump(mode="json"),
            "uses_real_capital": False,
            "live_order_routing": False,
        }

    report = build_weekly_evidence_report(db_path=args.db, memory_path=args.memory)
    args.out.write_text(render_weekly_evidence_report_markdown(report), encoding="utf-8")
    return {
        "command": "evidence-report",
        "weekly_report_out": str(args.out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }


def _handle_evidence_run(args: argparse.Namespace) -> dict[str, Any]:
    strategy_families = args.strategy_family or ["funding_extremity_price_confirmation"]
    try:
        report = run_daily_evidence_pipeline(
            db_path=args.db,
            memory_path=args.memory,
            report_out=args.report_out,
            current_capital_usd=args.current_capital_usd,
            allow_network=args.allow_network,
            ccxt_exchange=args.ccxt_exchange,
            symbol=args.symbol,
            funding_symbol=args.funding_symbol,
            timeframe=args.timeframe,
            limit=args.limit,
            strategy_families=strategy_families,
            run_id=args.run_id,
            include_defillama=args.include_defillama,
            include_dexscreener=args.include_dexscreener,
            dex_query=args.dex_query,
            min_tvl_usd=args.min_tvl_usd,
            include_dune=args.include_dune,
            dune_query_id=args.dune_query_id,
            dune_api_key=args.dune_api_key,
            dune_params=_key_value_pairs_to_dict(args.dune_param) if args.dune_param else None,
            include_thegraph=args.include_thegraph,
            subgraph_url=args.subgraph_url,
            graph_query=args.graph_query,
            graph_variables=_key_value_pairs_to_dict(args.graph_variable) if args.graph_variable else None,
            allow_stopped_family=args.allow_stopped_family,
        )
    except ValueError as exc:
        args.parser.error(str(exc))

    daily_evidence_report = build_daily_evidence_report(
        db_path=args.db,
        memory_path=args.memory,
        strategy_families=strategy_families,
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        render_daily_evidence_report_markdown(daily_evidence_report),
        encoding="utf-8",
    )

    payload = {
        "command": "evidence-run",
        "uses_real_capital": False,
        "live_order_routing": False,
        "memory_records_written": report.memory_records_written,
        "report_artifact": report.report_artifact,
        "daily_report_out": str(args.report_out),
        "steps": [step.model_dump(mode="json") for step in report.steps],
        "report": report.model_dump(mode="json"),
        "stopped_family_override_used": report.stopped_family_override_used,
    }
    if args.weekly_report_out is not None:
        weekly_evidence_report = build_weekly_evidence_report(
            db_path=args.db,
            memory_path=args.memory,
        )
        args.weekly_report_out.parent.mkdir(parents=True, exist_ok=True)
        args.weekly_report_out.write_text(
            render_weekly_evidence_report_markdown(weekly_evidence_report),
            encoding="utf-8",
        )
        payload["weekly_report_out"] = str(args.weekly_report_out)
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


def _has_onchain_ingestion_intent(args: argparse.Namespace) -> bool:
    sources = set(args.source)
    return bool(
        sources.intersection({"dune", "thegraph"})
        or args.dune_query_id is not None
        or args.dune_api_key is not None
        or args.dune_param
        or args.subgraph_url is not None
        or args.graph_query is not None
        or args.graph_variable
    )


def _has_dex_or_defi_ingestion_intent(args: argparse.Namespace) -> bool:
    sources = set(args.source)
    return bool(
        sources.intersection({"dexscreener", "defillama"})
        or args.query is not None
        or args.chain is not None
        or args.token_address
        or args.min_tvl_usd is not None
    )


def _validate_onchain_ingest_args(args: argparse.Namespace) -> None:
    sources = set(args.source)
    if len(sources) != 1 or not sources.issubset({"dune", "thegraph"}):
        args.parser.error("Dune/TheGraph ingestion flags require exactly one Dune or TheGraph --source")
    if not args.allow_network:
        args.parser.error("--allow-network is required when --source dune or --source thegraph is provided")
    if _has_ccxt_specific_flags(args):
        args.parser.error("Dune/TheGraph ingestion flags cannot be combined with CCXT flags")
    if _has_dex_or_defi_specific_flags(args):
        args.parser.error("Dune/TheGraph ingestion flags cannot be combined with DEX/DeFi flags")

    source = next(iter(sources))
    if source == "dune":
        _validate_dune_ingest_args(args)
        return
    _validate_thegraph_ingest_args(args)


def _validate_dune_ingest_args(args: argparse.Namespace) -> None:
    missing = [
        option
        for option, value in (
            ("--dune-query-id", args.dune_query_id),
            ("--dune-api-key", args.dune_api_key),
        )
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source dune is provided")
    if args.subgraph_url is not None or args.graph_query is not None or args.graph_variable:
        args.parser.error("TheGraph flags cannot be combined with --source dune")
    _validate_unique_key_value_pairs(args.parser, args.dune_param, "--dune-param")


def _validate_thegraph_ingest_args(args: argparse.Namespace) -> None:
    missing = [
        option
        for option, value in (
            ("--subgraph-url", args.subgraph_url),
            ("--graph-query", args.graph_query),
        )
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source thegraph is provided")
    if args.dune_query_id is not None or args.dune_api_key is not None or args.dune_param:
        args.parser.error("Dune flags cannot be combined with --source thegraph")
    _validate_unique_key_value_pairs(args.parser, args.graph_variable, "--graph-variable")


def _validate_dex_or_defi_ingest_args(args: argparse.Namespace) -> None:
    sources = set(args.source)
    if len(sources) != 1 or not sources.issubset({"dexscreener", "defillama"}):
        args.parser.error("DEX/DeFi ingestion flags require exactly one DEX/DeFi --source")
    if not args.allow_network:
        args.parser.error("--allow-network is required when --source dexscreener or --source defillama is provided")
    if _has_ccxt_specific_flags(args):
        args.parser.error("CCXT ingestion flags cannot be combined with DEX/DeFi sources")

    source = next(iter(sources))
    if source == "dexscreener":
        if args.min_tvl_usd is not None:
            args.parser.error("--min-tvl-usd cannot be combined with --source dexscreener")
        _validate_non_blank_dexscreener_args(args)
        has_query = args.query is not None
        has_token_lookup = args.chain is not None and bool(args.token_address)
        if has_query == has_token_lookup:
            args.parser.error("--source dexscreener requires either --query or both --chain and --token-address")
        return

    if args.query is not None or args.chain is not None or args.token_address:
        args.parser.error("DexScreener flags cannot be combined with --source defillama")


def _has_ccxt_specific_flags(args: argparse.Namespace) -> bool:
    return bool(
        args.ccxt_feed is not None
        or args.exchange != "binance"
        or args.symbol is not None
        or args.timeframe is not None
        or args.since is not None
        or args.limit is not None
    )


def _has_dex_or_defi_specific_flags(args: argparse.Namespace) -> bool:
    return bool(
        args.query is not None
        or args.chain is not None
        or args.token_address
        or args.min_tvl_usd is not None
    )


def _validate_non_blank_dexscreener_args(args: argparse.Namespace) -> None:
    if args.query is not None and not args.query.strip():
        args.parser.error("--query cannot be blank")
    if args.chain is not None and not args.chain.strip():
        args.parser.error("--chain cannot be blank")
    if any(not token_address.strip() for token_address in args.token_address):
        args.parser.error("--token-address cannot be blank")


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


def _run_onchain_ingestion(args: argparse.Namespace):
    if set(args.source) == {"dune"}:
        return ingest_dune_query_result(
            db_path=args.db,
            query_id=args.dune_query_id,
            allow_network=True,
            api_key=args.dune_api_key,
            params=_key_value_pairs_to_dict(args.dune_param),
        )
    return ingest_thegraph_query_result(
        db_path=args.db,
        subgraph_url=args.subgraph_url,
        query=args.graph_query,
        allow_network=True,
        variables=_key_value_pairs_to_dict(args.graph_variable),
    )


def _run_dex_or_defi_ingestion(args: argparse.Namespace):
    if set(args.source) == {"dexscreener"}:
        return ingest_dexscreener_pairs(
            args.db,
            query=args.query,
            chain=args.chain,
            token_addresses=args.token_address,
            allow_network=True,
        )
    return ingest_defillama_yield_pools(
        args.db,
        min_tvl_usd=args.min_tvl_usd if args.min_tvl_usd is not None else 10000.0,
        allow_network=True,
    )


def _validate_unique_key_value_pairs(
    parser: argparse.ArgumentParser,
    pairs: list[tuple[str, str]],
    flag_name: str,
) -> None:
    duplicate_keys = _duplicate_key_value_keys(pairs)
    if duplicate_keys:
        parser.error(f"{flag_name} cannot repeat keys: {', '.join(duplicate_keys)}")


def _key_value_pairs_to_dict(pairs: list[tuple[str, str]]) -> dict[str, str]:
    duplicate_keys = _duplicate_key_value_keys(pairs)
    if duplicate_keys:
        raise ValueError(f"duplicate key-value arguments: {', '.join(duplicate_keys)}")
    return {key: value for key, value in pairs}


def _duplicate_key_value_keys(pairs: list[tuple[str, str]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for key, _value in pairs:
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return sorted(duplicates)


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
            ccxt_exchange=args.ccxt_exchange,
            symbol=args.symbol,
            funding_symbol=args.funding_symbol,
            timeframe=args.timeframe,
            limit=args.limit,
            strategy_families=args.strategy_family,
            include_offline_check=args.offline_check,
            include_defillama=args.include_defillama,
            include_dexscreener=args.include_dexscreener,
            dex_query=args.dex_query,
            min_tvl_usd=args.min_tvl_usd,
            include_dune=args.include_dune,
            dune_query_id=args.dune_query_id,
            dune_api_key=args.dune_api_key,
            dune_params=[f"{key}={value}" for key, value in args.dune_param],
            include_thegraph=args.include_thegraph,
            subgraph_url=args.subgraph_url,
            graph_query=args.graph_query,
            graph_variables=[f"{key}={value}" for key, value in args.graph_variable],
            allow_stopped_family=args.allow_stopped_family,
        )
    except ValueError as exc:
        args.parser.error(str(exc))
    return plan.model_dump(mode="json")


if __name__ == "__main__":
    raise SystemExit(main())
