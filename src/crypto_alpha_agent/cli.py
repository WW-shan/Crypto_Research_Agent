from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import uuid
from contextlib import nullcontext
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Sequence

from crypto_alpha_agent.autonomy.codex_runner import CodexRunner, CodexUnavailableError
from crypto_alpha_agent.autonomy.cycle import run_creation_cycle
from crypto_alpha_agent.agents.report_summarizer import ReportType, summarize_evidence_report
from crypto_alpha_agent.config import LLMRole
from crypto_alpha_agent.data.ingestion import (
    ingest_binance_public_month,
    ingest_binance_public_um_futures_month,
    ingest_binance_usdm_basis,
    ingest_binance_usdm_global_long_short_account_ratio,
    ingest_binance_usdm_premium_index_klines,
    ingest_binance_usdm_taker_buy_sell_volume,
    ingest_ccxt_funding_rate_history,
    ingest_ccxt_open_interest_history,
    ingest_ccxt_ohlcv,
    ingest_defillama_yield_pools,
    ingest_dexscreener_pairs,
)
from crypto_alpha_agent.data.onchain_ingestion import (
    ingest_dune_query_result,
    ingest_thegraph_query_result,
)
from crypto_alpha_agent.data.source_probe import available_probe_targets, probe_target
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.llm import (
    LLMProviderError,
    LLMRuntimeError,
    RealLLMRuntime,
    build_required_real_llm_runtime,
)
from crypto_alpha_agent.llm.redaction import redact_text
from crypto_alpha_agent.observability.logging import load_events
from crypto_alpha_agent.observability.reports import generate_daily_report
from crypto_alpha_agent.orchestrator import build_llm_research_graph
from crypto_alpha_agent.pipeline.ai_research_memo import build_ai_research_memo
from crypto_alpha_agent.pipeline.evidence_runner import run_daily_evidence_pipeline
from crypto_alpha_agent.pipeline.llm_judgements import (
    BootstrapInterpretation,
    EvidenceRunInterpretation,
    LLMJudgementTask,
    RolloutReadinessNarrative,
    run_data_readiness_judgement,
    run_source_research_judgement,
    run_runtime_command_judgement,
)
from crypto_alpha_agent.pipeline.evidence_run_ops import (
    EvidenceRunArtifact,
    EvidenceRunLock,
    EvidenceRunLockError,
    EvidenceRunManifest,
    network_route_from_environment,
    redacted_evidence_run_inputs,
    redacted_failure,
    write_json_artifact,
    write_text_artifact,
)
from crypto_alpha_agent.pipeline.evidence_reports import (
    build_daily_evidence_report,
    build_weekly_evidence_report,
)
from crypto_alpha_agent.pipeline.candidate_state_memory import (
    persist_candidate_state_memory,
)
from crypto_alpha_agent.pipeline.data_depth_campaign import (
    CampaignMonth,
    DataDepthCampaignReport,
    DataDepthCampaignSpec,
    build_data_depth_campaign_report,
    campaign_symbol_to_binance_symbol,
    expand_campaign_months,
    render_data_depth_campaign_markdown,
)
from crypto_alpha_agent.pipeline.expansion_preparation import build_expansion_preparation_report
from crypto_alpha_agent.pipeline.governance_reports import build_profit_governance_report
from crypto_alpha_agent.pipeline.historical_bootstrap import build_historical_bootstrap_report
from crypto_alpha_agent.pipeline.iteration_controller import build_iteration_cycle_report
from crypto_alpha_agent.pipeline.markdown import (
    render_ai_research_memo_markdown,
    render_daily_evidence_report_markdown,
    render_expansion_preparation_markdown,
    render_historical_bootstrap_markdown,
    render_iteration_cycle_markdown,
    render_profit_governance_report_markdown,
    render_research_loop_markdown,
    render_weekly_evidence_report_markdown,
)
from crypto_alpha_agent.pipeline.strategy_feasibility import (
    build_derivatives_conditioned_lab_report,
    build_large_liquid_momentum_feasibility_report,
    build_multi_hypothesis_feasibility_report,
    render_derivatives_conditioned_lab_markdown,
    render_multi_hypothesis_feasibility_markdown,
    render_strategy_feasibility_markdown,
)
from crypto_alpha_agent.pipeline.universe_presets import resolve_universe_symbols
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


class EvidenceRunConfigurationError(ValueError):
    reason_code = "evidence_run_path_collision"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "llm_gate_bypass", False):
        payload = args.handler(args)
        print(json.dumps(payload, sort_keys=True))
        return int(payload.get("exit_code", 0) or 0)
    try:
        runtime = build_required_real_llm_runtime(
            role=_llm_role_for_command(args.command)
        )
        runtime.health_check(command=args.command)
    except LLMProviderError as exc:
        payload = _llm_preflight_failure_payload(
            args.command,
            _llm_provider_runtime_error(exc),
        )
        print(json.dumps(payload, sort_keys=True))
        return 2
    except LLMRuntimeError as exc:
        payload = _llm_preflight_failure_payload(args.command, exc)
        print(json.dumps(payload, sort_keys=True))
        return 2
    args.llm_runtime = runtime
    payload = args.handler(args)
    print(json.dumps(payload, sort_keys=True))
    return int(payload.get("exit_code", 0) or 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crypto-alpha-agent",
        description="Operate the crypto alpha research agent in local safe modes.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="crypto-alpha-agent 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    llm_health_parser = subparsers.add_parser(
        "llm-health-check",
        help="Run the required real LLM structured health check.",
    )
    llm_health_parser.set_defaults(
        handler=_handle_llm_health_check,
        llm_gate_bypass=True,
    )

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
    report_parser.set_defaults(handler=_handle_report, parser=report_parser)

    replay_parser = subparsers.add_parser(
        "replay",
        help="Load persisted events, count them, and optionally regenerate a daily report.",
    )
    replay_parser.add_argument("--events", required=True, type=_existing_event_path, help="Path to persisted event JSONL.")
    replay_parser.add_argument("--date", type=_utc_date, help="Optional UTC report date in YYYY-MM-DD format.")
    replay_parser.set_defaults(handler=_handle_replay, parser=replay_parser)

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
            "open_interest",
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
        "--venue",
        default="binance",
        help="Public venue whose fee and market-constraint assumptions apply.",
    )
    paper_sim_loop_parser.add_argument(
        "--cost-model-mode",
        choices=("base", "pessimistic"),
        default="pessimistic",
        help="Execution cost model mode; pessimistic is the default rollout gate.",
    )
    paper_sim_loop_parser.add_argument(
        "--max-notional-usd",
        type=_positive_finite_float,
        default=25.0,
        help="Maximum per-trade notional allowed by the owner profile.",
    )
    paper_sim_loop_parser.add_argument(
        "--max-signal-age-seconds",
        type=_positive_finite_float,
        default=3600.0,
        help="Maximum age between signal and paper entry before stale_signal blocks.",
    )
    paper_sim_loop_parser.add_argument(
        "--min-notional-usd",
        type=_non_negative_finite_float,
        help="Optional symbol-level minimum notional override.",
    )
    paper_sim_loop_parser.add_argument(
        "--min-quantity",
        type=_non_negative_finite_float,
        help="Optional symbol-level minimum quantity override.",
    )
    paper_sim_loop_parser.add_argument(
        "--quantity-step",
        type=_non_negative_finite_float,
        help="Optional symbol-level quantity step override.",
    )
    paper_sim_loop_parser.add_argument(
        "--tick-size",
        type=_non_negative_finite_float,
        help="Optional symbol-level tick size override.",
    )
    paper_sim_loop_parser.add_argument(
        "--max-volume-participation-rate",
        type=_positive_finite_float,
        default=0.05,
        help="Maximum share of candle quote volume a paper fill may assume.",
    )
    paper_sim_loop_parser.add_argument(
        "--allow-partial-fills",
        action="store_true",
        help="Allow low-liquidity paper fills to reduce notional instead of blocking.",
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
    plan_experiments_parser.set_defaults(handler=_handle_plan_experiments, parser=plan_experiments_parser)

    iteration_cycle_parser = subparsers.add_parser(
        "iteration-cycle",
        help="Ask the LLM for guarded next iteration candidates without executing changes.",
    )
    iteration_cycle_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    iteration_cycle_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    iteration_cycle_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown iteration report.")
    iteration_cycle_parser.add_argument("--json-out", required=True, type=Path, help="Path for the machine-readable payload JSON.")
    iteration_cycle_parser.add_argument("--strategy-family", help="Optional registered strategy family to focus.")
    iteration_cycle_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used for research constraints.",
    )
    iteration_cycle_parser.add_argument(
        "--max-candidates",
        type=_positive_int,
        default=5,
        help="Maximum LLM iteration candidates to accept after deterministic guards.",
    )
    iteration_cycle_parser.set_defaults(handler=_handle_iteration_cycle, parser=iteration_cycle_parser)

    creation_cycle_parser = subparsers.add_parser(
        "creation-cycle",
        help="run one creation-first Codex autonomy cycle.",
    )
    creation_cycle_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    creation_cycle_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    creation_cycle_parser.add_argument(
        "--autonomy-root",
        type=Path,
        default=Path("var/autonomy"),
        help="Root directory for autonomy cycle state.",
    )
    creation_cycle_parser.add_argument(
        "--task-root",
        type=Path,
        default=Path("var/autonomy/tasks"),
        help=(
            "Compatibility path only; task paths are currently derived from "
            "--autonomy-root."
        ),
    )
    creation_cycle_parser.add_argument(
        "--worktree-root",
        type=Path,
        default=Path("var/autonomy/worktrees"),
        help=(
            "Compatibility path only; worktree paths are currently derived from "
            "--autonomy-root."
        ),
    )
    creation_cycle_parser.add_argument(
        "--reports-root",
        type=Path,
        default=Path("var/reports"),
        help="Root directory for creation cycle reports.",
    )
    creation_cycle_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root used by Codex and worktree operations.",
    )
    creation_cycle_parser.add_argument(
        "--max-creations",
        type=_positive_int,
        default=1,
        help="Compatibility limit; this cycle currently creates one object.",
    )
    creation_cycle_parser.add_argument(
        "--no-run-commands",
        action="store_true",
        help=(
            "Still runs the Codex builder; skips verification command execution "
            "and worktree promotion."
        ),
    )
    creation_cycle_parser.set_defaults(handler=_handle_creation_cycle, parser=creation_cycle_parser)

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
    evidence_report_parser.set_defaults(handler=_handle_evidence_report, parser=evidence_report_parser)

    governance_report_parser = subparsers.add_parser(
        "governance-report",
        help="Generate deterministic profit governance and paper-only portfolio review.",
    )
    governance_report_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    governance_report_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    governance_report_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown governance report.")
    governance_report_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used for paper-only governance constraints.",
    )
    governance_report_parser.set_defaults(handler=_handle_governance_report, parser=governance_report_parser)

    historical_bootstrap_parser = subparsers.add_parser(
        "historical-bootstrap",
        help="Generate a Phase 7 historical bootstrap and evidence-campaign report.",
    )
    historical_bootstrap_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    historical_bootstrap_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    historical_bootstrap_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown bootstrap report.")
    historical_bootstrap_parser.add_argument("--json-out", required=True, type=Path, help="Path for the machine-readable payload JSON.")
    historical_bootstrap_parser.add_argument("--manifest-out", required=True, type=Path, help="Path for the bootstrap manifest JSON.")
    historical_bootstrap_parser.add_argument("--run-id", help="Optional historical bootstrap run identifier.")
    historical_bootstrap_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used for research constraints.",
    )
    historical_bootstrap_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before network-backed historical source collection.",
    )
    historical_bootstrap_parser.add_argument("--binance-symbol", help="Binance Public Data symbol, e.g. BTCUSDT.")
    historical_bootstrap_parser.add_argument("--price-symbol", required=True, help="Stored market candle symbol.")
    historical_bootstrap_parser.add_argument("--funding-symbol", required=True, help="Stored funding-rate symbol.")
    historical_bootstrap_parser.add_argument("--timeframe", required=True, help="Stored market candle timeframe.")
    historical_bootstrap_parser.add_argument(
        "--bootstrap-window",
        action="append",
        default=[],
        help="Historical bootstrap window in YYYY-MM-DD/YYYY-MM-DD form. Repeat for multiple windows.",
    )
    historical_bootstrap_parser.add_argument(
        "--strategy-family",
        action="append",
        default=[],
        help="Registered strategy family to include. Repeat for multiple families.",
    )
    historical_bootstrap_parser.add_argument("--ccxt-exchange", default="binance", help="CCXT exchange id for public market data.")
    historical_bootstrap_parser.add_argument("--limit", type=_positive_int, default=1000, help="Positive CCXT record limit.")
    historical_bootstrap_parser.add_argument(
        "--notional-usd",
        type=_non_negative_finite_float,
        default=25.0,
        help="Paper notional used for historical paper simulation.",
    )
    historical_bootstrap_parser.set_defaults(
        handler=_handle_historical_bootstrap,
        parser=historical_bootstrap_parser,
    )

    ai_research_memo_parser = subparsers.add_parser(
        "ai-research-memo",
        help="Generate a weekly evidence-grounded AI research memo without execution authority.",
    )
    ai_research_memo_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    ai_research_memo_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    ai_research_memo_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown memo.")
    ai_research_memo_parser.add_argument("--strategy-family", help="Optional registered strategy family to plan next.")
    ai_research_memo_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used to cap paper notional.",
    )
    ai_research_memo_parser.set_defaults(handler=_handle_ai_research_memo)

    expansion_prep_parser = subparsers.add_parser(
        "expansion-prep-report",
        help="Generate the read-only Phase 5 data and strategy expansion preparation report.",
    )
    expansion_prep_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    expansion_prep_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    expansion_prep_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown report.")
    expansion_prep_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used to evaluate registry constraints.",
    )
    expansion_prep_parser.set_defaults(handler=_handle_expansion_prep_report, parser=expansion_prep_parser)

    strategy_feasibility_parser = subparsers.add_parser(
        "strategy-feasibility",
        help="Build a read-only local strategy feasibility report before registering a family.",
    )
    strategy_feasibility_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    strategy_feasibility_parser.add_argument(
        "--memory",
        type=Path,
        help="Path to the JSONL candidate memory store for multi-hypothesis mode; Task 4 reads no memory and writes no memory.",
    )
    strategy_feasibility_parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "large-liquid-momentum-regime",
            "derivatives-conditioned-lab",
            "multi-hypothesis-lab",
        ),
        help="Feasibility mode to evaluate.",
    )
    strategy_feasibility_parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Stored market candle symbol. Repeat for multiple symbols.",
    )
    strategy_feasibility_parser.add_argument(
        "--universe-preset",
        help="Optional deterministic universe preset such as liquid-usdm-top20.",
    )
    strategy_feasibility_parser.add_argument(
        "--max-symbols",
        type=_positive_int,
        help="Optional cap after combining explicit symbols and a universe preset.",
    )
    strategy_feasibility_parser.add_argument("--timeframe", required=True, help="Stored market candle timeframe.")
    strategy_feasibility_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown report.")
    strategy_feasibility_parser.add_argument("--json-out", required=True, type=Path, help="Path for the machine-readable payload JSON.")
    strategy_feasibility_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used for feasibility constraints.",
    )
    strategy_feasibility_parser.add_argument(
        "--derivatives-symbol",
        action="append",
        default=[],
        help="Optional derivatives mapping in SYMBOL=BINANCEUSDM format. Repeat for multiple symbols.",
    )
    strategy_feasibility_parser.add_argument(
        "--derivatives-period",
        default="1h",
        help="Binance USD-M derivatives context period.",
    )
    strategy_feasibility_parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Candidate to evaluate. Repeat to select multiple candidates; valid IDs depend on --mode.",
    )
    strategy_feasibility_parser.add_argument(
        "--min-split-count",
        type=_positive_int,
        default=3,
        help="Minimum positive walk-forward split count.",
    )
    strategy_feasibility_parser.add_argument(
        "--feasibility-version",
        choices=("v1", "v2"),
        default="v1",
        help="Multi-hypothesis feasibility policy version.",
    )
    strategy_feasibility_parser.add_argument(
        "--purge-gap-bars",
        type=_non_negative_int,
        default=0,
        help="Bars to exclude between train and test windows in multi-hypothesis v2.",
    )
    strategy_feasibility_parser.add_argument(
        "--min-unique-months",
        type=_non_negative_int,
        default=0,
        help="Minimum unique signal months required by multi-hypothesis v2.",
    )
    strategy_feasibility_parser.add_argument(
        "--min-asset-count",
        type=_non_negative_int,
        default=0,
        help="Minimum point-in-time eligible asset count required by multi-hypothesis v2.",
    )
    strategy_feasibility_parser.add_argument(
        "--cost-bps",
        type=_non_negative_finite_float,
        default=10.0,
        help="Round-trip cost assumption in basis points.",
    )
    strategy_feasibility_parser.add_argument(
        "--cost-bps-grid",
        action="append",
        type=_non_negative_finite_float,
        default=[],
        help="Multi-hypothesis cost sensitivity grid value in basis points. Repeat to override the default 5/10/20/50 grid.",
    )
    strategy_feasibility_parser.add_argument(
        "--cost-aware-execution",
        action="store_true",
        help="Filter multi-hypothesis observations whose signal edge does not clear the configured cost threshold.",
    )
    strategy_feasibility_parser.add_argument(
        "--min-edge-over-cost-multiplier",
        type=_non_negative_finite_float,
        default=1.0,
        help="Minimum signal edge multiple over cost required when --cost-aware-execution is enabled.",
    )
    strategy_feasibility_parser.add_argument(
        "--max-turnover",
        type=_non_negative_finite_float,
        help="Optional multi-hypothesis turnover cap; candidates above it are blocked.",
    )
    strategy_feasibility_parser.add_argument(
        "--persist-candidate-state",
        action="store_true",
        help="Persist multi-hypothesis candidate states to --memory. Default mode stays read-only.",
    )
    strategy_feasibility_parser.set_defaults(
        handler=_handle_strategy_feasibility,
        parser=strategy_feasibility_parser,
        llm_gate_bypass=True,
    )

    data_depth_parser = subparsers.add_parser(
        "data-depth-campaign",
        help="Build a read-only data-depth campaign coverage plan.",
    )
    data_depth_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    data_depth_parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Market symbol to audit. Repeat for multiple symbols.",
    )
    data_depth_parser.add_argument(
        "--universe-preset",
        help="Optional deterministic universe preset such as liquid-usdm-top20.",
    )
    data_depth_parser.add_argument(
        "--max-symbols",
        type=_positive_int,
        help="Optional cap after combining explicit symbols and a universe preset.",
    )
    data_depth_parser.add_argument("--timeframe", required=True, help="Stored market candle timeframe.")
    data_depth_parser.add_argument("--start-year", required=True, type=_positive_int, help="Campaign start UTC year.")
    data_depth_parser.add_argument("--start-month", required=True, type=_month_number, help="Campaign start UTC month.")
    data_depth_parser.add_argument("--end-year", required=True, type=_positive_int, help="Campaign end UTC year.")
    data_depth_parser.add_argument("--end-month", required=True, type=_month_number, help="Campaign end UTC month.")
    data_depth_parser.add_argument(
        "--collect",
        action="store_true",
        help="Execute missing Binance Public Data collection jobs.",
    )
    data_depth_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before --collect performs network access.",
    )
    data_depth_parser.add_argument(
        "--min-unique-months",
        type=_positive_int,
        default=3,
        help="Minimum unique covered months required per symbol.",
    )
    data_depth_parser.add_argument("--out", required=True, type=Path, help="Path for the Markdown report.")
    data_depth_parser.add_argument("--json-out", required=True, type=Path, help="Path for the machine-readable payload JSON.")
    data_depth_parser.set_defaults(
        handler=_handle_data_depth_campaign,
        parser=data_depth_parser,
        llm_gate_bypass=True,
    )

    evidence_universe_lab_parser = subparsers.add_parser(
        "evidence-universe-lab",
        help="Run the read-only data-depth campaign and feasibility v2 lab.",
    )
    evidence_universe_lab_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    evidence_universe_lab_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL candidate memory store.")
    evidence_universe_lab_parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Market symbol to audit and evaluate. Repeat for multiple symbols.",
    )
    evidence_universe_lab_parser.add_argument(
        "--universe-preset",
        help="Optional deterministic universe preset such as liquid-usdm-top20.",
    )
    evidence_universe_lab_parser.add_argument(
        "--max-symbols",
        type=_positive_int,
        help="Optional cap after combining explicit symbols and a universe preset.",
    )
    evidence_universe_lab_parser.add_argument("--timeframe", required=True, help="Stored market candle timeframe.")
    evidence_universe_lab_parser.add_argument("--start-year", required=True, type=_positive_int, help="Campaign start UTC year.")
    evidence_universe_lab_parser.add_argument("--start-month", required=True, type=_month_number, help="Campaign start UTC month.")
    evidence_universe_lab_parser.add_argument("--end-year", required=True, type=_positive_int, help="Campaign end UTC year.")
    evidence_universe_lab_parser.add_argument("--end-month", required=True, type=_month_number, help="Campaign end UTC month.")
    evidence_universe_lab_parser.add_argument(
        "--collect",
        action="store_true",
        help="Execute missing Binance Public Data collection jobs before feasibility.",
    )
    evidence_universe_lab_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before --collect performs network access.",
    )
    evidence_universe_lab_parser.add_argument(
        "--min-unique-months",
        type=_positive_int,
        default=3,
        help="Minimum unique covered months required per symbol and feasibility candidate.",
    )
    evidence_universe_lab_parser.add_argument(
        "--min-asset-count",
        type=_positive_int,
        default=3,
        help="Minimum point-in-time eligible asset count required by feasibility v2.",
    )
    evidence_universe_lab_parser.add_argument(
        "--min-split-count",
        type=_positive_int,
        default=3,
        help="Minimum positive walk-forward split count.",
    )
    evidence_universe_lab_parser.add_argument(
        "--purge-gap-bars",
        type=_non_negative_int,
        default=24,
        help="Bars to exclude between train and test windows in feasibility v2.",
    )
    evidence_universe_lab_parser.add_argument(
        "--cost-bps-grid",
        action="append",
        type=_non_negative_finite_float,
        default=[],
        help="Feasibility cost sensitivity grid value in basis points. Repeat to override the default 5/10/20/50 grid.",
    )
    evidence_universe_lab_parser.add_argument(
        "--cost-aware-execution",
        action="store_true",
        help="Filter feasibility observations whose signal edge does not clear the configured cost threshold.",
    )
    evidence_universe_lab_parser.add_argument(
        "--min-edge-over-cost-multiplier",
        type=_non_negative_finite_float,
        default=1.0,
        help="Minimum signal edge multiple over cost required when --cost-aware-execution is enabled.",
    )
    evidence_universe_lab_parser.add_argument(
        "--max-turnover",
        type=_non_negative_finite_float,
        help="Optional feasibility turnover cap; candidates above it are blocked.",
    )
    evidence_universe_lab_parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Candidate to evaluate. Repeat to select multiple candidates.",
    )
    evidence_universe_lab_parser.add_argument(
        "--current-capital-usd",
        type=_non_negative_finite_float,
        default=300.0,
        help="Operator capital profile used for feasibility constraints.",
    )
    evidence_universe_lab_parser.add_argument(
        "--persist-candidate-state",
        action="store_true",
        help="Persist feasibility v2 candidate states to --memory.",
    )
    evidence_universe_lab_parser.add_argument("--out-dir", required=True, type=Path, help="Directory for Markdown and JSON lab artifacts.")
    evidence_universe_lab_parser.add_argument("--json-out", required=True, type=Path, help="Path for the machine-readable summary JSON.")
    evidence_universe_lab_parser.set_defaults(
        handler=_handle_evidence_universe_lab,
        parser=evidence_universe_lab_parser,
        llm_gate_bypass=True,
    )

    evidence_run_parser = subparsers.add_parser(
        "evidence-run",
        help="Run the safe end-to-end evidence pipeline without live capital.",
    )
    evidence_run_parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite research data store.")
    evidence_run_parser.add_argument("--memory", required=True, type=Path, help="Path to the JSONL memory store.")
    evidence_run_parser.add_argument("--report-out", required=True, type=Path, help="Path for the daily Markdown report.")
    evidence_run_parser.add_argument(
        "--research-report-out",
        type=Path,
        help="Optional path for the research-loop Markdown report; defaults to a .research.md sidecar.",
    )
    evidence_run_parser.add_argument("--weekly-report-out", type=Path, help="Optional path for weekly evidence Markdown.")
    evidence_run_parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path for the machine-readable evidence-run payload JSON.",
    )
    evidence_run_parser.add_argument(
        "--manifest-out",
        type=Path,
        help="Optional path for the evidence-run manifest JSON.",
    )
    evidence_run_parser.add_argument(
        "--latest-report-out",
        type=Path,
        help="Optional latest-pointer path for the daily Markdown report.",
    )
    evidence_run_parser.add_argument(
        "--latest-json-out",
        type=Path,
        help="Optional latest-pointer path for the evidence-run payload JSON.",
    )
    evidence_run_parser.add_argument(
        "--latest-manifest-out",
        type=Path,
        help="Optional latest-pointer path for the evidence-run manifest JSON.",
    )
    evidence_run_parser.add_argument(
        "--lock-path",
        type=Path,
        help="Optional local lock path preventing overlapping evidence-run invocations.",
    )
    evidence_run_parser.add_argument(
        "--failed-marker-out",
        type=Path,
        help="Optional path for the failed-run marker JSON.",
    )
    evidence_run_parser.add_argument(
        "--no-lock",
        action="store_true",
        help="Disable the local evidence-run lock for controlled test or recovery runs.",
    )
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

    source_probe_parser = subparsers.add_parser(
        "source-probe",
        help="Qualify public data sources and persist proxy-aware source health.",
    )
    source_probe_parser.add_argument(
        "--list-targets",
        action="store_true",
        help="List source-probe targets without network access.",
    )
    source_probe_parser.add_argument("--db", type=Path, help="Path to the SQLite research data store.")
    source_probe_parser.add_argument("--target", help="Source-probe target id.")
    source_probe_parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Required explicit gate before a source probe performs network access.",
    )
    source_probe_parser.add_argument(
        "--route",
        choices=("auto", "direct", "proxy"),
        default="auto",
        help="Network route to test; proxy requires local proxy environment configuration.",
    )
    source_probe_parser.add_argument(
        "--credential-configured",
        action="store_true",
        help="Record that a required local credential exists without passing its value.",
    )
    source_probe_parser.set_defaults(handler=_handle_source_probe, parser=source_probe_parser)

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
        choices=(
            "binance-public",
            "binance-usdm",
            "ccxt",
            "dexscreener",
            "defillama",
            "dune",
            "thegraph",
        ),
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
        choices=("ohlcv", "funding-rate-history", "open-interest-history"),
        help="CCXT feed to ingest when --source ccxt is provided.",
    )
    ingest_parser.add_argument(
        "--public-data-market",
        choices=("spot", "um-futures"),
        help="Binance Public Data market namespace when --source binance-public is provided.",
    )
    ingest_parser.add_argument("--year", type=_positive_int, help="Positive UTC year for Binance Public Data ingestion.")
    ingest_parser.add_argument("--month", type=_month_number, help="UTC month for Binance Public Data ingestion, 1-12.")
    ingest_parser.add_argument(
        "--exchange",
        default="binance",
        help="CCXT exchange id for research data ingestion.",
    )
    ingest_parser.add_argument("--symbol", help="CCXT market symbol to ingest.")
    ingest_parser.add_argument("--timeframe", help="CCXT OHLCV timeframe, required for --ccxt-feed ohlcv.")
    ingest_parser.add_argument("--since", type=int, help="Optional CCXT since timestamp in milliseconds.")
    ingest_parser.add_argument("--limit", type=_positive_int, help="Optional positive CCXT record limit.")
    ingest_parser.add_argument(
        "--binance-usdm-feed",
        choices=(
            "premium-index-klines",
            "basis",
            "global-long-short-account-ratio",
            "taker-buy-sell-volume",
        ),
        help="Binance USD-M public derivatives feed to ingest.",
    )
    ingest_parser.add_argument("--pair", help="Binance USD-M pair for pair-scoped feeds.")
    ingest_parser.add_argument("--contract-type", help="Binance USD-M contract type, such as PERPETUAL.")
    ingest_parser.add_argument("--period", help="Binance USD-M statistics period, such as 1h.")
    ingest_parser.add_argument("--interval", help="Binance USD-M kline interval, such as 1h.")
    ingest_parser.add_argument(
        "--start-time-ms",
        type=int,
        help="Optional Binance USD-M start timestamp in milliseconds.",
    )
    ingest_parser.add_argument(
        "--end-time-ms",
        type=int,
        help="Optional Binance USD-M end timestamp in milliseconds.",
    )
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
    command_parser.set_defaults(handler=handler, parser=command_parser)


def _base_payload(command: str) -> dict[str, Any]:
    return {
        "command": command,
        "mode": "dry_run",
        "live_api_calls": True,
        "live_api_call_types": ["llm_health_check"],
        "live_market_api_calls": False,
        "uses_real_capital": False,
        "live_order_routing": False,
    }


def _llm_role_for_command(command: str) -> LLMRole:
    if command in {"plan-experiments", "iteration-cycle", "creation-cycle", "schedule"}:
        return "planning"
    if command in {
        "evidence-report",
        "governance-report",
        "historical-bootstrap",
        "rollout-review",
    }:
        return "summary"
    return "research"


def _llm_preflight_failure_payload(
    command: str,
    exc: LLMRuntimeError,
) -> dict[str, Any]:
    return {
        "command": command,
        "exit_code": 2,
        "reason_code": exc.reason_code,
        "llm_required": True,
        "llm_provider": "unavailable",
        "side_effects_started": False,
        "uses_real_capital": False,
        "live_order_routing": False,
        "failure": redact_text(str(exc)),
    }


def _llm_provider_runtime_error(exc: LLMProviderError) -> LLMRuntimeError:
    return LLMRuntimeError(
        "llm_provider_unavailable",
        redact_text(str(exc)),
    )


def _apply_runtime_command_judgement(
    args: argparse.Namespace,
    payload: dict[str, Any],
    *,
    command: str,
    evidence_refs: list[str],
    objective: str,
) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        judgement = run_runtime_command_judgement(
            runtime,
            command=command,
            facts=payload,
            evidence_refs=evidence_refs,
            objective=objective,
        )
    except LLMProviderError as exc:
        args.parser.error(str(_llm_provider_runtime_error(exc)))
        raise AssertionError("argparse parser.error should exit") from exc
    except (LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    payload["llm_judgement"] = judgement.model_dump(mode="json")
    payload.update(runtime.metadata())
    return payload


def _handle_llm_health_check(_args: argparse.Namespace) -> dict[str, Any]:
    try:
        runtime = build_required_real_llm_runtime(role="research")
        health = runtime.health_check(command="llm-health-check")
    except LLMProviderError as exc:
        return _llm_preflight_failure_payload(
            "llm-health-check",
            _llm_provider_runtime_error(exc),
        )
    except LLMRuntimeError as exc:
        return _llm_preflight_failure_payload("llm-health-check", exc)
    return {
        "command": "llm-health-check",
        "exit_code": 0,
        "llm_required": True,
        "health": health.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
    }


def _handle_scan(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        **_base_payload("scan"),
        "signals_scanned": 0,
        "opportunities": [],
        "notes": ["llm-gated dry run only", "no market data provider calls"],
    }
    return _apply_runtime_command_judgement(
        args,
        payload,
        command="scan",
        evidence_refs=["runtime:scan"],
        objective="Review this command output under the LLM-native runtime policy.",
    )


def _handle_research(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        **_base_payload("research"),
        "hypotheses_generated": 0,
        "required_evidence": [
            "venue liquidity",
            "fee and slippage assumptions",
            "risk approval before any paper action",
        ],
    }
    return _apply_runtime_command_judgement(
        args,
        payload,
        command="research",
        evidence_refs=["runtime:research"],
        objective="Review this command output under the LLM-native runtime policy.",
    )


def _handle_backtest(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
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
    return _apply_runtime_command_judgement(
        args,
        payload,
        command="backtest",
        evidence_refs=["runtime:backtest"],
        objective="Review this command output under the LLM-native runtime policy.",
    )


def _handle_paper(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        **_base_payload("paper"),
        "orders_submitted": 0,
        "touched_real_capital": False,
        "constraints": ["paper account only", "no wallet access", "no exchange order routing"],
    }
    return _apply_runtime_command_judgement(
        args,
        payload,
        command="paper",
        evidence_refs=["runtime:paper"],
        objective="Review this command output under the LLM-native runtime policy.",
    )


def _handle_report(args: argparse.Namespace) -> dict[str, Any]:
    loaded = load_events(args.events)
    report = generate_daily_report(
        loaded.events,
        args.date,
        skipped_event_lines=loaded.skipped_count,
    )
    payload = {
        "command": "report",
        "event_path": str(args.events),
        "loaded_events": len(loaded.events),
        "skipped_event_lines": loaded.skipped_count,
        "report": report.model_dump(mode="json"),
    }
    return _apply_runtime_command_judgement(
        args,
        payload,
        command="report",
        evidence_refs=["runtime:report"],
        objective="Review this report output under the LLM-native runtime policy.",
    )


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
    return _apply_runtime_command_judgement(
        args,
        payload,
        command="replay",
        evidence_refs=["runtime:replay"],
        objective="Review this replay output under the LLM-native runtime policy.",
    )


def _handle_research_loop(args: argparse.Namespace) -> dict[str, Any]:
    _validate_research_loop_strategy_args(args)
    runtime: RealLLMRuntime = args.llm_runtime
    llm = runtime.llm
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
        **runtime.metadata(),
    }
    try:
        llm_state = build_llm_research_graph(
            llm,
            max_capital_usd=args.current_capital_usd,
        ).invoke(
            {
                "research_report": report,
                "memory_path": str(args.memory) if args.memory is not None else None,
                "suggest_paper_action": False,
            }
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    payload["llm_research_result"] = llm_state["llm_research_result"]
    if "memory_record_id" in llm_state:
        payload["llm_memory_record_id"] = llm_state["memory_record_id"]
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
    runtime: RealLLMRuntime = args.llm_runtime
    ingestion = None
    if args.offline_check and args.source:
        args.parser.error("--offline-check cannot be combined with --source")
    if _has_binance_public_ingestion_intent(args):
        _validate_binance_public_ingest_args(args)
        ingestion = _run_binance_public_ingestion(args)
    elif _has_binance_usdm_ingestion_intent(args):
        _validate_binance_usdm_ingest_args(args)
        ingestion = _run_binance_usdm_ingestion(args)
    elif _has_onchain_ingestion_intent(args):
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
    try:
        judgement = run_data_readiness_judgement(
            runtime,
            command="ingest",
            ingestion_summary=payload,
            evidence_refs=[f"ingest:{mode}"],
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    payload["llm_judgement"] = judgement.model_dump(mode="json")
    payload.update(runtime.metadata())
    return payload


def _handle_source_probe(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    if args.list_targets:
        targets = [target.model_dump(mode="json") for target in available_probe_targets()]
        try:
            judgement = run_source_research_judgement(
                runtime,
                command="source-probe",
                source_health={"targets": targets},
                evidence_refs=["source-health:list-targets"],
            )
        except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
            args.parser.error(str(exc))
            raise AssertionError("argparse parser.error should exit") from exc
        return {
            "command": "source-probe",
            "targets": targets,
            "llm_judgement": judgement.model_dump(mode="json"),
            "uses_real_capital": False,
            "live_order_routing": False,
            "exit_code": 0,
            **runtime.metadata(),
        }
    if args.db is None or args.target is None:
        args.parser.error("--db and --target are required unless --list-targets is provided")

    result = probe_target(
        db_path=args.db,
        target_id=args.target,
        allow_network=args.allow_network,
        route=args.route,
        env=dict(os.environ),
        credential_configured=args.credential_configured,
    )
    try:
        judgement = run_source_research_judgement(
            runtime,
            command="source-probe",
            source_health=result.model_dump(mode="json"),
            evidence_refs=[f"source-health:{result.target_id}"],
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    return {
        "command": "source-probe",
        "result": result.model_dump(mode="json"),
        "llm_judgement": judgement.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        "exit_code": result.exit_code,
        **runtime.metadata(),
    }


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
            venue=args.venue,
            cost_model_mode=args.cost_model_mode,
            max_notional_usd=args.max_notional_usd,
            max_signal_age_seconds=args.max_signal_age_seconds,
            min_notional_usd=args.min_notional_usd,
            min_quantity=args.min_quantity,
            quantity_step=args.quantity_step,
            tick_size=args.tick_size,
            max_volume_participation_rate=args.max_volume_participation_rate,
            allow_partial_fills=args.allow_partial_fills,
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
    payload = _apply_runtime_command_judgement(
        args,
        payload,
        command="paper-sim-loop",
        evidence_refs=[f"paper-sim-loop:{args.strategy_family}"],
        objective="Review this paper simulation output under the LLM-native runtime policy.",
    )
    if args.report_out is not None:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _handle_rollout_review(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    review = build_rollout_review_artifact(
        db_path=args.db,
        strategy_family=args.strategy_family,
        human_approved=args.human_approved,
        human_approval_reference=args.human_approval_reference,
        max_notional_usd=args.max_notional_usd,
        max_daily_loss_usd=args.max_daily_loss_usd,
    )
    payload = review.model_dump(mode="json")
    try:
        judgement = runtime.structured_call(
            LLMJudgementTask(
                command="rollout-review",
                schema_name="RolloutReadinessNarrative",
                objective="Explain rollout readiness without enabling live execution.",
                facts=payload,
                evidence_refs=[f"rollout:{args.strategy_family}"],
                constraints=[
                    "live_execution_enabled must be false",
                    "uses_real_capital must be false",
                    "live_order_routing must be false",
                ],
            ),
            RolloutReadinessNarrative,
        )
        judgement.validate_refs({f"rollout:{args.strategy_family}"})
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

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
    payload["llm_judgement"] = judgement.model_dump(mode="json")
    payload.update(runtime.metadata())
    return payload


def _handle_plan_experiments(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        result = plan_next_experiments(
            db_path=args.db,
            memory_path=args.memory,
            strategy_family=args.strategy_family,
            max_proposals=args.max_proposals,
            current_capital_usd=args.current_capital_usd,
            llm=runtime.llm,
        )
    except LLMProviderError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

    payload = {
        "command": "plan-experiments",
        "current_capital_usd": args.current_capital_usd,
        "proposals": [
            proposal.model_dump(mode="json")
            for proposal in result.proposals
        ],
        "strategy_template_proposals": [
            proposal.model_dump(mode="json")
            for proposal in result.strategy_template_proposals
        ],
        "degraded_strategy_families": result.degraded_strategy_families,
        "accepted": result.accepted,
        "rejected_reason_codes": result.rejected_reason_codes,
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
    }
    response_metadata = result.__dict__.get("_response_metadata")
    if response_metadata is not None:
        payload["llm_response_metadata"] = response_metadata
    return payload


def _handle_iteration_cycle(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        report = build_iteration_cycle_report(
            db_path=args.db,
            memory_path=args.memory,
            llm=runtime.llm,
            strategy_family=args.strategy_family,
            current_capital_usd=args.current_capital_usd,
            max_candidates=args.max_candidates,
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_iteration_cycle_markdown(report), encoding="utf-8")
    payload = {
        "command": "iteration-cycle",
        "exit_code": 0 if report.accepted else 2,
        "iteration_cycle_report_out": str(args.out),
        "json_out": str(args.json_out),
        "report": report.model_dump(mode="json"),
        "accepted": report.accepted,
        "reason_code": None if report.accepted else "iteration_cycle_rejected",
        "llm_required": report.llm_required,
        "auto_executes_changes": report.auto_executes_changes,
        "scheduler_executes_commands": report.scheduler_executes_commands,
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
    }
    response_metadata = report.__dict__.get("_response_metadata")
    if response_metadata is not None:
        payload["llm_response_metadata"] = response_metadata
    write_json_artifact(args.json_out, payload)
    return payload


def _handle_creation_cycle(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        report = run_creation_cycle(
            repo_root=args.repo_root,
            db_path=args.db,
            memory_path=args.memory,
            reports_root=args.reports_root,
            autonomy_root=args.autonomy_root,
            llm_runtime=runtime,
            codex=CodexRunner(),
            max_creations=args.max_creations,
            run_commands=not args.no_run_commands,
            write_latest_json=False,
        )
    except LLMProviderError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="llm_provider_unavailable",
            failure=str(exc),
        )
    except LLMRuntimeError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code=exc.reason_code,
            failure=str(exc),
        )
    except CodexUnavailableError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="codex_unavailable",
            failure=str(exc),
        )
    except ValueError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="creation_cycle_invalid",
            failure=str(exc),
        )
    except OSError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="creation_cycle_io_failed",
            failure=str(exc),
        )
    except subprocess.SubprocessError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="creation_cycle_subprocess_failed",
            failure=_subprocess_failure_text(exc),
        )
    except RuntimeError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="creation_cycle_failed",
            failure=str(exc),
        )

    payload = {
        "command": "creation-cycle",
        "exit_code": 0 if report.accepted else 2,
        "report": report.model_dump(mode="json"),
        "creation_report_out": report.report_path,
        "json_out": report.json_path,
        "accepted": report.accepted,
        "reason_code": None if report.accepted else "creation_cycle_rejected",
        "llm_required": report.llm_required,
        "codex_required": report.codex_required,
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
    }
    response_metadata = report.__dict__.get("_response_metadata")
    if response_metadata is not None:
        payload["llm_response_metadata"] = response_metadata
    try:
        _write_creation_cli_payload(report.json_path, payload)
    except OSError as exc:
        return _creation_cycle_failure_payload(
            runtime=runtime,
            reason_code="creation_cycle_io_failed",
            failure=str(exc),
        )
    return payload


def _creation_cycle_failure_payload(
    *,
    runtime: RealLLMRuntime,
    reason_code: str,
    failure: str,
) -> dict[str, Any]:
    return {
        "command": "creation-cycle",
        "exit_code": 2,
        "accepted": False,
        "reason_code": reason_code,
        "llm_required": True,
        "codex_required": True,
        "uses_real_capital": False,
        "live_order_routing": False,
        "failure": redact_text(failure),
        **runtime.metadata(),
    }


def _write_creation_cli_payload(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    if target.exists():
        target.unlink()
    write_json_artifact(target, payload)


def _subprocess_failure_text(exc: subprocess.SubprocessError) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        detail = str(exc)
        stderr = getattr(exc, "stderr", None)
        stdout = getattr(exc, "stdout", None)
        if stderr:
            detail = f"{detail}; stderr={stderr}"
        if stdout:
            detail = f"{detail}; stdout={stdout}"
        return detail
    return str(exc)


def _handle_evidence_report(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.daily:
        try:
            report = build_daily_evidence_report(
                db_path=args.db,
                memory_path=args.memory,
                llm=runtime.llm,
                strategy_families=args.strategy_family,
            )
        except LLMProviderError as exc:
            args.parser.error(str(exc))
            raise AssertionError("argparse parser.error should exit") from exc
        report, summary_payload = _apply_evidence_report_summary(
            args,
            report,
            report_type="daily",
            llm=runtime.llm,
        )
        args.out.write_text(render_daily_evidence_report_markdown(report), encoding="utf-8")
        return {
            "command": "evidence-report",
            "daily_report_out": str(args.out),
            "report": report.model_dump(mode="json"),
            "uses_real_capital": False,
            "live_order_routing": False,
            **runtime.metadata(),
            **summary_payload,
        }

    report = build_weekly_evidence_report(db_path=args.db, memory_path=args.memory)
    report, summary_payload = _apply_evidence_report_summary(
        args,
        report,
        report_type="weekly",
        llm=runtime.llm,
    )
    args.out.write_text(render_weekly_evidence_report_markdown(report), encoding="utf-8")
    return {
        "command": "evidence-report",
        "weekly_report_out": str(args.out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
        **summary_payload,
    }


def _handle_governance_report(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    report = build_profit_governance_report(
        db_path=args.db,
        memory_path=args.memory,
        current_capital_usd=args.current_capital_usd,
    )
    evidence_refs = [
        f"governance:{row.strategy_family}"
        for row in report.family_scoreboard
    ] or ["governance:empty-scoreboard"]
    try:
        judgement = run_runtime_command_judgement(
            runtime,
            command="governance-report",
            facts=report.model_dump(mode="json"),
            evidence_refs=evidence_refs,
            objective=(
                "Explain the deterministic governance report without changing its actions."
            ),
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_profit_governance_report_markdown(report), encoding="utf-8")
    return {
        "command": "governance-report",
        "governance_report_out": str(args.out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        "llm_judgement": judgement.model_dump(mode="json"),
        **runtime.metadata(),
    }


def _handle_historical_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        report = build_historical_bootstrap_report(
            db_path=args.db,
            memory_path=args.memory,
            run_id=args.run_id,
            current_capital_usd=args.current_capital_usd,
            price_symbol=args.price_symbol,
            funding_symbol=args.funding_symbol,
            timeframe=args.timeframe,
            bootstrap_windows=args.bootstrap_window,
            strategy_families=args.strategy_family,
            allow_network=args.allow_network,
            binance_symbol=args.binance_symbol,
            ccxt_exchange=args.ccxt_exchange,
            limit=args.limit,
            notional_usd=args.notional_usd,
            report_path=args.out,
            json_path=args.json_out,
            manifest_path=args.manifest_out,
        )
    except ValueError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

    evidence_refs = _historical_bootstrap_evidence_refs(report)
    try:
        judgement = runtime.structured_call(
            LLMJudgementTask(
                command="historical-bootstrap",
                schema_name="BootstrapInterpretation",
                objective=(
                    "Interpret bootstrap evidence while preserving that historical evidence is not profit proof."
                ),
                facts=report.model_dump(mode="json"),
                evidence_refs=evidence_refs,
                constraints=[
                    "historical_is_profit_proof must be false",
                    "uses_real_capital must be false",
                    "live_order_routing must be false",
                ],
            ),
            BootstrapInterpretation,
        )
        judgement.validate_refs(set(evidence_refs))
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

    write_text_artifact(args.out, render_historical_bootstrap_markdown(report))
    payload = {
        "command": "historical-bootstrap",
        "status": report.manifest.status,
        "exit_code": 0 if report.manifest.status == "success" else 2,
        "historical_bootstrap_report_out": str(args.out),
        "json_out": str(args.json_out),
        "manifest_out": str(args.manifest_out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        "llm_judgement": judgement.model_dump(mode="json"),
        **runtime.metadata(),
    }
    write_json_artifact(args.json_out, payload)
    write_json_artifact(args.manifest_out, report.manifest.model_dump(mode="json"))
    return payload


def _historical_bootstrap_evidence_refs(report: Any) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    def add(ref: str) -> None:
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)

    add(f"bootstrap:{report.manifest.run_id}")
    for result in report.strategy_results:
        for ref in result.evidence_refs:
            add(ref)
    return refs


def _handle_ai_research_memo(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        memo = build_ai_research_memo(
            db_path=args.db,
            memory_path=args.memory,
            llm=runtime.llm,
            strategy_family=args.strategy_family,
            current_capital_usd=args.current_capital_usd,
        )
    except LLMProviderError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    try:
        judgement = run_runtime_command_judgement(
            runtime,
            command="ai-research-memo",
            facts=memo.model_dump(mode="json"),
            evidence_refs=[f"ai-research-memo:{args.strategy_family or 'all'}"],
            objective="Review the research memo under the LLM-native runtime policy.",
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_ai_research_memo_markdown(memo), encoding="utf-8")
    return {
        "command": "ai-research-memo",
        "ai_research_memo_out": str(args.out),
        "memo": memo.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        "llm_judgement": judgement.model_dump(mode="json"),
        **runtime.metadata(),
    }


def _handle_expansion_prep_report(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    report = build_expansion_preparation_report(
        db_path=args.db,
        memory_path=args.memory,
        current_capital_usd=args.current_capital_usd,
    )
    try:
        judgement = run_runtime_command_judgement(
            runtime,
            command="expansion-prep-report",
            facts=report.model_dump(mode="json"),
            evidence_refs=["expansion-prep:registry"],
            objective="Review the expansion preparation report under the LLM-native runtime policy.",
        )
    except (LLMProviderError, LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_expansion_preparation_markdown(report), encoding="utf-8")
    return {
        "command": "expansion-prep-report",
        "expansion_prep_report_out": str(args.out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
        "llm_judgement": judgement.model_dump(mode="json"),
        **runtime.metadata(),
    }


def _parse_derivatives_symbol_map(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_value in values:
        if "=" not in raw_value:
            raise ValueError(
                f"invalid --derivatives-symbol {raw_value!r}; expected SYMBOL=DERIVATIVES_SYMBOL"
            )
        symbol, derivatives_symbol = raw_value.split("=", maxsplit=1)
        symbol = symbol.strip()
        derivatives_symbol = derivatives_symbol.strip()
        if not symbol or not derivatives_symbol:
            raise ValueError(
                f"invalid --derivatives-symbol {raw_value!r}; symbol and derivatives symbol must be non-empty"
            )
        parsed[symbol] = derivatives_symbol
    return parsed


_DERIVATIVES_FEASIBILITY_CANDIDATES = {
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
}


def _validate_derivatives_feasibility_candidates(
    parser: argparse.ArgumentParser,
    candidates: list[str],
) -> None:
    invalid = [
        candidate
        for candidate in candidates
        if candidate not in _DERIVATIVES_FEASIBILITY_CANDIDATES
    ]
    if invalid:
        parser.error(
            "invalid derivatives-conditioned candidate(s): "
            + ", ".join(invalid)
            + "; expected one of "
            + ", ".join(sorted(_DERIVATIVES_FEASIBILITY_CANDIDATES))
        )


def _resolve_cli_universe_symbols(args: argparse.Namespace) -> list[str]:
    try:
        symbols = resolve_universe_symbols(
            args.symbol,
            universe_preset=getattr(args, "universe_preset", None),
            max_symbols=getattr(args, "max_symbols", None),
        )
    except ValueError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    if not symbols:
        args.parser.error("--symbol or --universe-preset is required")
        raise AssertionError("argparse parser.error should exit")
    return symbols


def _has_multi_hypothesis_only_policy_args(args: argparse.Namespace) -> bool:
    return bool(
        args.cost_aware_execution
        or args.min_edge_over_cost_multiplier != 1.0
        or args.max_turnover is not None
    )


def _handle_strategy_feasibility(args: argparse.Namespace) -> dict[str, Any]:
    candidate_state_memory_records = []
    symbols = _resolve_cli_universe_symbols(args)
    if args.mode != "multi-hypothesis-lab" and _has_multi_hypothesis_only_policy_args(args):
        args.parser.error(
            "--cost-aware-execution, --min-edge-over-cost-multiplier, and "
            "--max-turnover are only supported for --mode multi-hypothesis-lab"
        )
        raise AssertionError("argparse parser.error should exit")
    if args.mode == "multi-hypothesis-lab":
        if args.memory is None:
            args.parser.error("--memory is required for --mode multi-hypothesis-lab")
            raise AssertionError("argparse parser.error should exit")
        try:
            report = build_multi_hypothesis_feasibility_report(
                args.db,
                memory_path=args.memory,
                symbols=symbols,
                timeframe=args.timeframe,
                current_capital_usd=args.current_capital_usd,
                cost_bps_grid=args.cost_bps_grid or None,
                min_split_count=args.min_split_count,
                candidates=args.candidate,
                feasibility_version=args.feasibility_version,
                purge_gap_bars=args.purge_gap_bars,
                min_unique_months=args.min_unique_months,
                min_asset_count=args.min_asset_count,
                cost_aware_execution=args.cost_aware_execution,
                min_edge_over_cost_multiplier=args.min_edge_over_cost_multiplier,
                max_turnover=args.max_turnover,
            )
        except ValueError as exc:
            args.parser.error(str(exc))
            raise AssertionError("argparse parser.error should exit") from exc
        if args.persist_candidate_state:
            candidate_state_memory_records = persist_candidate_state_memory(
                report,
                args.memory,
            )
        markdown = render_multi_hypothesis_feasibility_markdown(report)
    elif args.mode == "derivatives-conditioned-lab":
        if args.persist_candidate_state:
            args.parser.error("--persist-candidate-state is only supported for --mode multi-hypothesis-lab")
            raise AssertionError("argparse parser.error should exit")
        _validate_derivatives_feasibility_candidates(args.parser, args.candidate)
        try:
            derivatives_symbols = _parse_derivatives_symbol_map(args.derivatives_symbol)
        except ValueError as exc:
            args.parser.error(str(exc))
            raise AssertionError("argparse parser.error should exit") from exc
        report = build_derivatives_conditioned_lab_report(
            args.db,
            symbols=symbols,
            timeframe=args.timeframe,
            current_capital_usd=args.current_capital_usd,
            derivatives_symbols=derivatives_symbols,
            derivatives_period=args.derivatives_period,
            candidates=args.candidate,
            cost_bps=args.cost_bps,
            min_split_count=args.min_split_count,
        )
        markdown = render_derivatives_conditioned_lab_markdown(report)
    else:
        if args.persist_candidate_state:
            args.parser.error("--persist-candidate-state is only supported for --mode multi-hypothesis-lab")
            raise AssertionError("argparse parser.error should exit")
        if args.candidate:
            args.parser.error("--candidate is not supported for --mode large-liquid-momentum-regime")
            raise AssertionError("argparse parser.error should exit")
        report = build_large_liquid_momentum_feasibility_report(
            args.db,
            symbols=symbols,
            timeframe=args.timeframe,
            current_capital_usd=args.current_capital_usd,
            cost_bps=args.cost_bps,
            min_split_count=args.min_split_count,
        )
        markdown = render_strategy_feasibility_markdown(report)
    payload = {
        "command": "strategy-feasibility",
        "out": str(args.out),
        "json_out": str(args.json_out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    if candidate_state_memory_records:
        payload["candidate_state_memory_records"] = len(candidate_state_memory_records)
    write_text_artifact(args.out, markdown)
    write_json_artifact(args.json_out, payload)
    return payload


def _handle_data_depth_campaign(args: argparse.Namespace) -> dict[str, Any]:
    if args.collect and not args.allow_network:
        args.parser.error("--allow-network is required when --collect is provided")
        raise AssertionError("argparse parser.error should exit")
    symbols = _resolve_cli_universe_symbols(args)
    try:
        spec = DataDepthCampaignSpec(
            symbols=symbols,
            timeframe=args.timeframe,
            market="um-futures",
            start=CampaignMonth(year=args.start_year, month=args.start_month),
            end=CampaignMonth(year=args.end_year, month=args.end_month),
            min_unique_months=args.min_unique_months,
        )
        report = build_data_depth_campaign_report(args.db, spec=spec)
        if args.collect:
            report = _collect_data_depth_missing_jobs(args.db, report=report, spec=spec)
    except ValueError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

    markdown = render_data_depth_campaign_markdown(report)
    payload = {
        "command": "data-depth-campaign",
        "out": str(args.out),
        "json_out": str(args.json_out),
        "report": report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    write_text_artifact(args.out, markdown)
    write_json_artifact(args.json_out, payload)
    return payload


def _handle_evidence_universe_lab(args: argparse.Namespace) -> dict[str, Any]:
    if args.collect and not args.allow_network:
        args.parser.error("--allow-network is required when --collect is provided")
        raise AssertionError("argparse parser.error should exit")
    symbols = _resolve_cli_universe_symbols(args)
    try:
        spec = DataDepthCampaignSpec(
            symbols=symbols,
            timeframe=args.timeframe,
            market="um-futures",
            start=CampaignMonth(year=args.start_year, month=args.start_month),
            end=CampaignMonth(year=args.end_year, month=args.end_month),
            min_unique_months=args.min_unique_months,
        )
        data_depth_report = build_data_depth_campaign_report(args.db, spec=spec)
        if args.collect:
            data_depth_report = _collect_data_depth_missing_jobs(
                args.db,
                report=data_depth_report,
                spec=spec,
            )
    except ValueError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc

    requested_months = [
        (month.year, month.month)
        for month in expand_campaign_months(spec.start, spec.end)
    ]
    feasibility_report = build_multi_hypothesis_feasibility_report(
        args.db,
        memory_path=args.memory,
        symbols=list(spec.symbols),
        timeframe=spec.timeframe,
        current_capital_usd=args.current_capital_usd,
        cost_bps_grid=args.cost_bps_grid or None,
        min_split_count=args.min_split_count,
        candidates=args.candidate or None,
        feasibility_version="v2",
        purge_gap_bars=args.purge_gap_bars,
        requested_months=requested_months,
        min_unique_months=args.min_unique_months,
        min_asset_count=args.min_asset_count,
        cost_aware_execution=args.cost_aware_execution,
        min_edge_over_cost_multiplier=args.min_edge_over_cost_multiplier,
        max_turnover=args.max_turnover,
    )
    candidate_state_memory_records = []
    if args.persist_candidate_state:
        candidate_state_memory_records = persist_candidate_state_memory(
            feasibility_report,
            args.memory,
        )

    out_dir = args.out_dir
    artifacts = {
        "summary_markdown": str(out_dir / "evidence-universe-lab.md"),
        "summary_json": str(args.json_out),
        "data_depth_markdown": str(out_dir / "data-depth-campaign.md"),
        "data_depth_json": str(out_dir / "data-depth-campaign.json"),
        "feasibility_markdown": str(out_dir / "multi-hypothesis-feasibility.md"),
        "feasibility_json": str(out_dir / "multi-hypothesis-feasibility.json"),
        "candidate_memory": str(args.memory),
    }
    data_depth_payload = {
        "command": "data-depth-campaign",
        "report": data_depth_report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    feasibility_payload = {
        "command": "strategy-feasibility",
        "report": feasibility_report.model_dump(mode="json"),
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    if candidate_state_memory_records:
        feasibility_payload["candidate_state_memory_records"] = len(
            candidate_state_memory_records
        )

    summary_report = {
        "data_depth_readiness": data_depth_report.readiness,
        "data_depth_reason_codes": list(data_depth_report.reason_codes),
        "collection_job_count": len(data_depth_report.collection_results),
        "collection_succeeded_count": sum(
            1 for job in data_depth_report.collection_results if job.status == "succeeded"
        ),
        "collection_failed_count": sum(
            1 for job in data_depth_report.collection_results if job.status == "failed"
        ),
        "feasibility_readiness": feasibility_report.readiness,
        "feasibility_reason_codes": feasibility_report.reason_codes,
        "feasibility_version": feasibility_report.validation_policy.version,
        "purge_gap_bars": feasibility_report.validation_policy.purge_gap_bars,
        "min_unique_months": feasibility_report.validation_policy.min_unique_months,
        "min_asset_count": feasibility_report.validation_policy.min_asset_count,
        "candidate_count": len(feasibility_report.candidate_metrics),
        "feasible_candidate_count": (
            feasibility_report.multiple_testing_summary.feasible_candidate_count
        ),
        "blocked_candidate_count": (
            feasibility_report.multiple_testing_summary.blocked_candidate_count
        ),
        "candidate_state_memory_records": len(candidate_state_memory_records),
        "eligible_for_backtest": (
            feasibility_report.multiple_testing_summary.feasible_candidate_count > 0
        ),
    }
    payload = {
        "command": "evidence-universe-lab",
        "artifacts": artifacts,
        "report": summary_report,
        "uses_real_capital": False,
        "live_order_routing": False,
    }

    write_text_artifact(
        artifacts["data_depth_markdown"],
        render_data_depth_campaign_markdown(data_depth_report),
    )
    write_json_artifact(artifacts["data_depth_json"], data_depth_payload)
    write_text_artifact(
        artifacts["feasibility_markdown"],
        render_multi_hypothesis_feasibility_markdown(feasibility_report),
    )
    write_json_artifact(artifacts["feasibility_json"], feasibility_payload)
    write_text_artifact(
        artifacts["summary_markdown"],
        _render_evidence_universe_lab_markdown(payload),
    )
    write_json_artifact(args.json_out, payload)
    return payload


def _collect_data_depth_missing_jobs(
    db_path: Path,
    *,
    report: DataDepthCampaignReport,
    spec: DataDepthCampaignSpec,
) -> DataDepthCampaignReport:
    collection_results = []
    for job in report.missing_collection_jobs:
        try:
            summary = ingest_binance_public_um_futures_month(
                db_path,
                symbol=campaign_symbol_to_binance_symbol(job.symbol),
                interval=job.timeframe,
                year=job.month.year,
                month=job.month.month,
                allow_network=True,
            )
            collection_results.append(
                job.model_copy(
                    update={
                        "status": "succeeded",
                        "records_written": summary.records_written,
                        "error": None,
                    }
                )
            )
        except Exception as exc:
            collection_results.append(
                job.model_copy(
                    update={
                        "status": "failed",
                        "records_written": 0,
                        "error": str(exc),
                    }
                )
            )
    refreshed_report = build_data_depth_campaign_report(db_path, spec=spec)
    return refreshed_report.model_copy(
        update={"collection_results": tuple(collection_results)}
    )


def _render_evidence_universe_lab_markdown(payload: dict[str, Any]) -> str:
    report = payload["report"]
    artifacts = payload["artifacts"]
    lines = [
        "# Evidence Universe Lab",
        "",
        "## Safety",
        f"Real capital: {str(payload['uses_real_capital']).lower()}",
        f"Live order routing: {str(payload['live_order_routing']).lower()}",
        "",
        "## Decision",
        f"Data-depth readiness: {report['data_depth_readiness']}",
        f"Feasibility readiness: {report['feasibility_readiness']}",
        f"Eligible for backtest: {str(report['eligible_for_backtest']).lower()}",
        f"Feasible candidates: {report['feasible_candidate_count']}",
        f"Blocked candidates: {report['blocked_candidate_count']}",
        "",
        "## Validation Policy",
        f"Feasibility version: {report['feasibility_version']}",
        f"Purge gap bars: {report['purge_gap_bars']}",
        f"Minimum unique months: {report['min_unique_months']}",
        f"Minimum asset count: {report['min_asset_count']}",
        "",
        "## Artifacts",
    ]
    lines.extend(f"- `{path}`" for path in artifacts.values())
    return "\n".join(lines) + "\n"


def _apply_evidence_report_summary(
    args: argparse.Namespace,
    report: Any,
    *,
    report_type: ReportType,
    llm: Any,
) -> tuple[Any, dict[str, Any]]:
    try:
        summary_result = summarize_evidence_report(
            report,
            report_type=report_type,
            llm=llm,
        )
    except LLMProviderError as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    if not summary_result.accepted or summary_result.summary is None:
        rejected_reason_codes = ",".join(summary_result.rejected_reason_codes) or "invalid_summary"
        args.parser.error(f"LLM evidence report summary rejected: {rejected_reason_codes}")
        raise AssertionError("argparse parser.error should exit")

    enriched_report = report.model_copy(
        update={
            "llm_summary": summary_result.summary,
            "llm_summary_rejected_reason_codes": summary_result.rejected_reason_codes,
            "llm_summary_metadata": summary_result.llm_response_metadata,
        }
    )
    return enriched_report, {
        "llm_summary_accepted": summary_result.accepted,
        "llm_summary_rejected_reason_codes": summary_result.rejected_reason_codes,
        "llm_summary_metadata": summary_result.llm_response_metadata,
    }


def _handle_evidence_run(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    started_at = datetime.now(tz=UTC)
    run_id = _resolve_evidence_run_id(args)
    strategy_families = args.strategy_family or ["funding_extremity_price_confirmation"]
    paths = _resolve_evidence_run_paths(args, run_id)
    report = None
    try:
        _validate_evidence_run_artifact_paths(args, paths)
        lock_context = (
            nullcontext()
            if args.no_lock
            else EvidenceRunLock(paths["lock_path"], run_id=run_id)
        )
        with lock_context:
            report = run_daily_evidence_pipeline(
                db_path=args.db,
                memory_path=args.memory,
                report_out=paths["research_report_out"],
                current_capital_usd=args.current_capital_usd,
                allow_network=args.allow_network,
                ccxt_exchange=args.ccxt_exchange,
                symbol=args.symbol,
                funding_symbol=args.funding_symbol,
                timeframe=args.timeframe,
                limit=args.limit,
                strategy_families=strategy_families,
                run_id=run_id,
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
                graph_variables=(
                    _key_value_pairs_to_dict(args.graph_variable)
                    if args.graph_variable
                    else None
                ),
                allow_stopped_family=args.allow_stopped_family,
            )

            evidence_refs = [
                f"evidence-run:{run_id}",
                *[f"step:{step.name}" for step in report.steps],
            ]
            try:
                interpretation = runtime.structured_call(
                    LLMJudgementTask(
                        command="evidence-run",
                        schema_name="EvidenceRunInterpretation",
                        objective=(
                            "Interpret evidence-run results and propose the next bounded experiment."
                        ),
                        facts=report.model_dump(mode="json"),
                        evidence_refs=evidence_refs,
                        constraints=[
                            "Use only supplied evidence_refs.",
                            "uses_real_capital must be false.",
                            "live_order_routing must be false.",
                        ],
                    ),
                    EvidenceRunInterpretation,
                )
                interpretation.validate_refs(set(evidence_refs))
            except LLMProviderError as exc:
                return _finalize_evidence_run_failure(
                    args=args,
                    run_id=run_id,
                    strategy_families=strategy_families,
                    paths=paths,
                    started_at=started_at,
                    reason_code="llm_provider_unavailable",
                    failure=redacted_failure(
                        str(exc),
                        secrets=_evidence_run_secret_values(args),
                    ),
                    report=report,
                    lock_exists=False,
                )
            except LLMRuntimeError as exc:
                return _finalize_evidence_run_failure(
                    args=args,
                    run_id=run_id,
                    strategy_families=strategy_families,
                    paths=paths,
                    started_at=started_at,
                    reason_code=exc.reason_code,
                    failure=redacted_failure(
                        str(exc),
                        secrets=_evidence_run_secret_values(args),
                    ),
                    report=report,
                    lock_exists=False,
                )
            except ValueError as exc:
                return _finalize_evidence_run_failure(
                    args=args,
                    run_id=run_id,
                    strategy_families=strategy_families,
                    paths=paths,
                    started_at=started_at,
                    reason_code="llm_interpretation_invalid",
                    failure=redacted_failure(
                        str(exc),
                        secrets=_evidence_run_secret_values(args),
                    ),
                    report=report,
                    lock_exists=False,
                )

            report = report.model_copy(
                update={
                    "llm_interpretation": interpretation.model_dump(mode="json"),
                    **runtime.metadata(),
                }
            )

            daily_evidence_report = build_daily_evidence_report(
                db_path=args.db,
                memory_path=args.memory,
                llm=runtime.llm,
                strategy_families=strategy_families,
            )
            write_text_artifact(
                args.report_out,
                render_daily_evidence_report_markdown(daily_evidence_report),
                latest_path=paths["latest_report_out"],
            )

            if args.weekly_report_out is not None:
                weekly_evidence_report = build_weekly_evidence_report(
                    db_path=args.db,
                    memory_path=args.memory,
                )
                write_text_artifact(
                    args.weekly_report_out,
                    render_weekly_evidence_report_markdown(weekly_evidence_report),
                )

            status = _evidence_run_status(report)
            reason_code, failure = _evidence_run_status_reason(report, status=status)
            manifest = _build_evidence_run_manifest(
                args=args,
                run_id=run_id,
                strategy_families=strategy_families,
                paths=paths,
                started_at=started_at,
                status=status,
                reason_code=reason_code,
                failure=failure,
                report=report,
                lock_exists=False,
            )
            payload = _build_evidence_run_payload(
                args=args,
                run_id=run_id,
                paths=paths,
                status=status,
                exit_code=2 if status == "failed" else 0,
                reason_code=reason_code,
                failure=failure,
                report=report,
                manifest=manifest,
            )
            _write_evidence_run_payload_artifacts(
                paths=paths,
                payload=payload,
                manifest=manifest,
                lock_exists=False,
                write_failed_marker=status == "failed",
            )
            return payload
    except EvidenceRunConfigurationError as exc:
        return _finalize_evidence_run_failure(
            args=args,
            run_id=run_id,
            strategy_families=strategy_families,
            paths=paths,
            started_at=started_at,
            reason_code=exc.reason_code,
            failure=redacted_failure(str(exc), secrets=_evidence_run_secret_values(args)),
            report=report,
            lock_exists=False,
            write_artifacts=False,
        )
    except EvidenceRunLockError as exc:
        return _finalize_evidence_run_failure(
            args=args,
            run_id=run_id,
            strategy_families=strategy_families,
            paths=paths,
            started_at=started_at,
            reason_code=exc.reason_code,
            failure=redacted_failure(str(exc), secrets=_evidence_run_secret_values(args)),
            report=report,
            lock_exists=True,
        )
    except Exception as exc:
        return _finalize_evidence_run_failure(
            args=args,
            run_id=run_id,
            strategy_families=strategy_families,
            paths=paths,
            started_at=started_at,
            reason_code="evidence_run_failed",
            failure=redacted_failure(str(exc), secrets=_evidence_run_secret_values(args)),
            report=report,
            lock_exists=False,
        )


def _resolve_evidence_run_id(args: argparse.Namespace) -> str:
    if args.run_id is not None and args.run_id.strip():
        return args.run_id.strip()
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"evidence-run-{timestamp}-{uuid.uuid4().hex[:8]}"


def _resolve_evidence_run_paths(args: argparse.Namespace, run_id: str) -> dict[str, Path]:
    report_out = args.report_out
    operation_root = args.db.parent
    run_id_fragment = _run_id_path_fragment(run_id)
    json_out = args.json_out or _default_evidence_run_json_out(report_out)
    manifest_out = args.manifest_out or _default_evidence_run_manifest_out(operation_root, run_id_fragment)
    return {
        "research_report_out": args.research_report_out
        or _default_evidence_run_research_report_out(report_out),
        "json_out": json_out,
        "manifest_out": manifest_out,
        "latest_report_out": args.latest_report_out
        or _default_evidence_run_latest_report_out(report_out),
        "latest_json_out": args.latest_json_out
        or _default_evidence_run_latest_json_out(json_out),
        "latest_manifest_out": args.latest_manifest_out
        or _default_evidence_run_latest_manifest_out(manifest_out),
        "lock_path": args.lock_path or _default_evidence_run_lock_path(operation_root),
        "failed_marker_out": args.failed_marker_out
        or _default_evidence_run_failed_marker_out(operation_root, run_id_fragment),
    }


def _run_id_path_fragment(run_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", run_id).strip("-_")
    if not cleaned:
        cleaned = "run"
    cleaned = cleaned[:48]
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned}-{digest}"


def _validate_evidence_run_artifact_paths(
    args: argparse.Namespace,
    paths: dict[str, Path],
) -> None:
    named_paths: list[tuple[str, Path]] = [
        ("daily_report", args.report_out),
        ("research_report", paths["research_report_out"]),
        ("json_payload", paths["json_out"]),
        ("manifest", paths["manifest_out"]),
        ("latest_report", paths["latest_report_out"]),
        ("latest_json", paths["latest_json_out"]),
        ("latest_manifest", paths["latest_manifest_out"]),
        ("failed_marker", paths["failed_marker_out"]),
        ("lock", paths["lock_path"]),
    ]
    if args.weekly_report_out is not None:
        named_paths.append(("weekly_report", args.weekly_report_out))

    by_path: dict[Path, list[str]] = {}
    for name, path in named_paths:
        by_path.setdefault(_normalized_artifact_path(path), []).append(name)
    collisions = [
        f"{', '.join(names)} -> {path}"
        for path, names in by_path.items()
        if len(names) > 1
    ]
    if collisions:
        raise EvidenceRunConfigurationError(
            "evidence-run artifact path collision: " + "; ".join(collisions)
        )


def _normalized_artifact_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _default_evidence_run_research_report_out(report_out: Path) -> Path:
    suffix = report_out.suffix or ".md"
    return report_out.with_name(f"{report_out.stem}.research{suffix}")


def _default_evidence_run_json_out(report_out: Path) -> Path:
    return report_out.with_name(f"{report_out.stem}.json")


def _default_evidence_run_manifest_out(operation_root: Path, run_id: str) -> Path:
    return operation_root / "run-manifests" / "evidence-run" / f"{run_id}.json"


def _default_evidence_run_latest_report_out(report_out: Path) -> Path:
    suffix = report_out.suffix or ".md"
    return report_out.with_name(f"latest{suffix}")


def _default_evidence_run_latest_json_out(json_out: Path) -> Path:
    return json_out.with_name("latest.evidence-run.json")


def _default_evidence_run_latest_manifest_out(manifest_out: Path) -> Path:
    return manifest_out.with_name("latest.manifest.json")


def _default_evidence_run_lock_path(operation_root: Path) -> Path:
    return operation_root / "locks" / "evidence-run.lock"


def _default_evidence_run_failed_marker_out(operation_root: Path, run_id: str) -> Path:
    return operation_root / "run-manifests" / "failed" / f"{run_id}.json"


def _evidence_run_status(report: Any) -> str:
    step_statuses = [step.status for step in report.steps]
    if "failed" in step_statuses:
        return "failed"
    if "blocked" in step_statuses:
        return "blocked"
    return "success"


def _evidence_run_status_reason(report: Any, *, status: str) -> tuple[str | None, str | None]:
    if status == "success":
        return None, None
    target_status = "failed" if status == "failed" else "blocked"
    step = next((item for item in report.steps if item.status == target_status), None)
    reason_code = None if step is None else step.reason_code
    if status == "blocked":
        return reason_code or "evidence_run_blocked", None
    failure = next(
        (
            item.failure
            for item in report.source_health.failures
            if item.failure
        ),
        None,
    )
    if failure is None and step is not None:
        failure = f"failed step {step.name}: {reason_code or 'unknown'}"
    return reason_code or "evidence_run_failed", failure


def _evidence_run_artifacts(args: argparse.Namespace, paths: dict[str, Path]) -> dict[str, str | None]:
    artifacts: dict[str, str | None] = {
        "research_report": str(paths["research_report_out"]),
        "daily_report": str(args.report_out),
        "json_payload": str(paths["json_out"]),
        "manifest": str(paths["manifest_out"]),
        "latest_report": str(paths["latest_report_out"]),
        "latest_json": str(paths["latest_json_out"]),
        "latest_manifest": str(paths["latest_manifest_out"]),
        "lock": str(paths["lock_path"]),
        "failed_marker": str(paths["failed_marker_out"]),
    }
    if args.weekly_report_out is not None:
        artifacts["weekly_report"] = str(args.weekly_report_out)
    return artifacts


def _evidence_run_artifact_status(
    artifacts: dict[str, str | None],
    *,
    lock_exists: bool,
) -> dict[str, EvidenceRunArtifact]:
    statuses: dict[str, EvidenceRunArtifact] = {}
    for name, raw_path in artifacts.items():
        if raw_path is None:
            continue
        path = Path(raw_path)
        statuses[name] = EvidenceRunArtifact(
            path=str(path),
            exists=lock_exists if name == "lock" else path.exists(),
        )
    return statuses


def _build_evidence_run_manifest(
    *,
    args: argparse.Namespace,
    run_id: str,
    strategy_families: Sequence[str],
    paths: dict[str, Path],
    started_at: datetime,
    status: str,
    reason_code: str | None,
    failure: str | None,
    report: Any | None,
    lock_exists: bool,
) -> EvidenceRunManifest:
    report_payload = report.model_dump(mode="json") if report is not None else {}
    llm_metadata = {
        key: report_payload[key]
        for key in (
            "llm_provider",
            "used_fake_llm",
            "llm_role",
            "llm_provider_verified",
            "llm_model",
            "llm_health_schema",
        )
        if report_payload.get(key) is not None
    }
    artifacts = _evidence_run_artifacts(args, paths)
    run_started_at = report_payload.get("started_at", started_at.isoformat())
    return EvidenceRunManifest(
        run_id=run_id,
        status=status,
        started_at=run_started_at,
        completed_at=datetime.now(tz=UTC).isoformat(),
        inputs=_evidence_run_inputs(args, run_id, strategy_families, paths),
        network_route=network_route_from_environment(allow_network=args.allow_network),
        artifacts=artifacts,
        artifact_status=_evidence_run_artifact_status(
            artifacts,
            lock_exists=lock_exists,
        ),
        source_health=report_payload.get("source_health", {}),
        steps=report_payload.get("steps", []),
        decision_reason_codes=report_payload.get("decision_reason_codes", []),
        reason_code=reason_code,
        failure=failure,
        llm_interpretation=report_payload.get("llm_interpretation"),
        **llm_metadata,
    )


def _evidence_run_inputs(
    args: argparse.Namespace,
    run_id: str,
    strategy_families: Sequence[str],
    paths: dict[str, Path],
) -> dict[str, Any]:
    return redacted_evidence_run_inputs(
        {
            "run_id": run_id,
            "db_path": args.db,
            "memory_path": args.memory,
            "report_out": args.report_out,
            "research_report_out": paths["research_report_out"],
            "json_out": paths["json_out"],
            "manifest_out": paths["manifest_out"],
            "weekly_report_out": args.weekly_report_out,
            "current_capital_usd": args.current_capital_usd,
            "allow_network": args.allow_network,
            "ccxt_exchange": args.ccxt_exchange,
            "symbol": args.symbol,
            "funding_symbol": args.funding_symbol,
            "timeframe": args.timeframe,
            "limit": args.limit,
            "strategy_families": list(strategy_families),
            "allow_stopped_family": args.allow_stopped_family,
            "include_defillama": args.include_defillama,
            "include_dexscreener": args.include_dexscreener,
            "dex_query": args.dex_query,
            "min_tvl_usd": args.min_tvl_usd,
            "include_dune": args.include_dune,
            "dune_query_id": args.dune_query_id,
            "dune_api_key": args.dune_api_key,
            "dune_params": list(args.dune_param or []),
            "include_thegraph": args.include_thegraph,
            "subgraph_url": args.subgraph_url,
            "graph_query": args.graph_query,
            "graph_variables": list(args.graph_variable or []),
            "no_lock": args.no_lock,
        }
    )


def _build_evidence_run_payload(
    *,
    args: argparse.Namespace,
    run_id: str,
    paths: dict[str, Path],
    status: str,
    exit_code: int,
    reason_code: str | None,
    failure: str | None,
    report: Any | None,
    manifest: EvidenceRunManifest,
) -> dict[str, Any]:
    report_payload = report.model_dump(mode="json") if report is not None else None
    payload: dict[str, Any] = {
        "command": "evidence-run",
        "status": status,
        "exit_code": exit_code,
        "run_id": run_id,
        "uses_real_capital": False,
        "live_order_routing": False,
        "network_route": manifest.network_route,
        "memory_records_written": 0 if report is None else report.memory_records_written,
        "report_artifact": None if report is None else report.report_artifact,
        "daily_report_out": str(args.report_out),
        "research_report_out": str(paths["research_report_out"]),
        "json_out": str(paths["json_out"]),
        "manifest_out": str(paths["manifest_out"]),
        "latest_report_out": str(paths["latest_report_out"]),
        "latest_json_out": str(paths["latest_json_out"]),
        "latest_manifest_out": str(paths["latest_manifest_out"]),
        "lock_path": str(paths["lock_path"]),
        "failed_marker_out": str(paths["failed_marker_out"]),
        "reason_code": reason_code,
        "failure": failure,
        "steps": [] if report is None else [step.model_dump(mode="json") for step in report.steps],
        "report": report_payload,
        "manifest": manifest.model_dump(mode="json"),
        "stopped_family_override_used": False
        if report is None
        else report.stopped_family_override_used,
    }
    if args.weekly_report_out is not None:
        payload["weekly_report_out"] = str(args.weekly_report_out)
    if report_payload is not None:
        llm_interpretation = report_payload.get("llm_interpretation")
        if llm_interpretation is not None:
            payload["llm_interpretation"] = llm_interpretation
        for key in (
            "llm_provider",
            "used_fake_llm",
            "llm_role",
            "llm_provider_verified",
            "llm_model",
            "llm_health_schema",
        ):
            value = report_payload.get(key)
            if value is not None:
                payload[key] = value
    return payload


def _write_evidence_run_payload_artifacts(
    *,
    paths: dict[str, Path],
    payload: dict[str, Any],
    manifest: EvidenceRunManifest,
    lock_exists: bool,
    write_failed_marker: bool,
) -> EvidenceRunManifest:
    def write_once(current_manifest: EvidenceRunManifest) -> None:
        manifest_payload = current_manifest.model_dump(mode="json")
        payload["manifest"] = manifest_payload
        write_json_artifact(paths["json_out"], payload, latest_path=paths["latest_json_out"])
        write_json_artifact(
            paths["manifest_out"],
            manifest_payload,
            latest_path=paths["latest_manifest_out"],
        )
        if write_failed_marker:
            write_json_artifact(paths["failed_marker_out"], manifest_payload)

    write_once(manifest)
    final_manifest = manifest.model_copy(
        update={
            "completed_at": datetime.now(tz=UTC).isoformat(),
            "artifact_status": _evidence_run_artifact_status(
                manifest.artifacts,
                lock_exists=lock_exists,
            ),
        }
    )
    write_once(final_manifest)
    return final_manifest


def _finalize_evidence_run_failure(
    *,
    args: argparse.Namespace,
    run_id: str,
    strategy_families: Sequence[str],
    paths: dict[str, Path],
    started_at: datetime,
    reason_code: str,
    failure: str,
    report: Any | None,
    lock_exists: bool,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    manifest = _build_evidence_run_manifest(
        args=args,
        run_id=run_id,
        strategy_families=strategy_families,
        paths=paths,
        started_at=started_at,
        status="failed",
        reason_code=reason_code,
        failure=failure,
        report=report,
        lock_exists=lock_exists,
    )
    payload = _build_evidence_run_payload(
        args=args,
        run_id=run_id,
        paths=paths,
        status="failed",
        exit_code=2,
        reason_code=reason_code,
        failure=failure,
        report=report,
        manifest=manifest,
    )
    if write_artifacts:
        try:
            _write_evidence_run_payload_artifacts(
                paths=paths,
                payload=payload,
                manifest=manifest,
                lock_exists=lock_exists,
                write_failed_marker=True,
            )
        except OSError as exc:
            payload["artifact_write_failure"] = redacted_failure(
                str(exc),
                secrets=_evidence_run_secret_values(args),
            )
    return payload


def _evidence_run_secret_values(args: argparse.Namespace) -> list[str | None]:
    secrets: list[str | None] = [args.dune_api_key, args.subgraph_url, args.graph_query]
    secrets.extend(value for _key, value in args.dune_param or [])
    secrets.extend(value for _key, value in args.graph_variable or [])
    return secrets


def _has_binance_usdm_ingestion_intent(args: argparse.Namespace) -> bool:
    sources = set(args.source)
    return bool("binance-usdm" in sources or _has_binance_usdm_specific_flags(args))


def _has_binance_public_ingestion_intent(args: argparse.Namespace) -> bool:
    sources = set(args.source)
    if args.public_data_market is not None or args.year is not None or args.month is not None:
        return True
    return bool("binance-public" in sources and (args.symbol is not None or args.timeframe is not None))


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
    if _has_binance_usdm_specific_flags(args):
        args.parser.error("Dune/TheGraph ingestion flags cannot be combined with Binance USD-M flags")
    if _has_binance_public_specific_flags(args):
        args.parser.error("Dune/TheGraph ingestion flags cannot be combined with Binance Public Data flags")

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
    if _has_binance_usdm_specific_flags(args):
        args.parser.error("Binance USD-M flags cannot be combined with DEX/DeFi sources")
    if _has_binance_public_specific_flags(args):
        args.parser.error("Binance Public Data flags cannot be combined with DEX/DeFi sources")

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


def _has_ccxt_only_flags(args: argparse.Namespace) -> bool:
    return bool(args.ccxt_feed is not None or args.exchange != "binance" or args.timeframe is not None or args.since is not None)


def _has_binance_public_specific_flags(args: argparse.Namespace) -> bool:
    return bool(
        args.public_data_market is not None
        or args.year is not None
        or args.month is not None
    )


def _has_binance_usdm_specific_flags(args: argparse.Namespace) -> bool:
    return bool(
        args.binance_usdm_feed is not None
        or args.pair is not None
        or args.contract_type is not None
        or args.period is not None
        or args.interval is not None
        or args.start_time_ms is not None
        or args.end_time_ms is not None
    )


def _has_dex_or_defi_specific_flags(args: argparse.Namespace) -> bool:
    return bool(
        args.query is not None
        or args.chain is not None
        or args.token_address
        or args.min_tvl_usd is not None
    )


def _has_onchain_specific_flags(args: argparse.Namespace) -> bool:
    return bool(
        args.dune_query_id is not None
        or args.dune_api_key is not None
        or args.dune_param
        or args.subgraph_url is not None
        or args.graph_query is not None
        or args.graph_variable
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
    if _has_binance_usdm_specific_flags(args):
        args.parser.error("Binance USD-M flags cannot be combined with --source ccxt")
    if _has_binance_public_specific_flags(args):
        args.parser.error("Binance Public Data flags cannot be combined with --source ccxt")

    missing = [
        option
        for option, value in (
            ("--ccxt-feed", args.ccxt_feed),
            ("--symbol", args.symbol),
        )
        if value is None
    ]
    if args.ccxt_feed in {"ohlcv", "open-interest-history"} and args.timeframe is None:
        missing.append("--timeframe")
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source ccxt is provided")
    if args.ccxt_feed == "funding-rate-history" and args.timeframe is not None:
        args.parser.error("--timeframe cannot be combined with --ccxt-feed funding-rate-history")


def _validate_binance_usdm_ingest_args(args: argparse.Namespace) -> None:
    if set(args.source) != {"binance-usdm"}:
        args.parser.error(
            "Binance USD-M ingestion flags require --source binance-usdm and cannot be combined with other sources"
        )
    if not args.allow_network:
        args.parser.error("--allow-network is required when --source binance-usdm is provided")
    if _has_ccxt_only_flags(args):
        args.parser.error("CCXT-only flags cannot be combined with --source binance-usdm")
    if _has_binance_public_specific_flags(args):
        args.parser.error("Binance Public Data flags cannot be combined with --source binance-usdm")
    if _has_dex_or_defi_specific_flags(args):
        args.parser.error("DEX/DeFi flags cannot be combined with --source binance-usdm")
    if _has_onchain_specific_flags(args):
        args.parser.error("Dune/TheGraph flags cannot be combined with --source binance-usdm")

    if args.binance_usdm_feed is None:
        args.parser.error("--binance-usdm-feed required when --source binance-usdm is provided")

    if args.binance_usdm_feed == "premium-index-klines":
        _require_binance_usdm_args(args, "--symbol", args.symbol, "--interval", args.interval)
        _reject_binance_usdm_args(args, "--pair", args.pair, "--contract-type", args.contract_type, "--period", args.period)
        return
    if args.binance_usdm_feed == "basis":
        _require_binance_usdm_args(
            args,
            "--pair",
            args.pair,
            "--contract-type",
            args.contract_type,
            "--period",
            args.period,
        )
        _reject_binance_usdm_args(args, "--symbol", args.symbol, "--interval", args.interval)
        return

    _require_binance_usdm_args(args, "--symbol", args.symbol, "--period", args.period)
    _reject_binance_usdm_args(args, "--pair", args.pair, "--contract-type", args.contract_type, "--interval", args.interval)


def _validate_binance_public_ingest_args(args: argparse.Namespace) -> None:
    if set(args.source) != {"binance-public"}:
        args.parser.error(
            "Binance Public Data ingestion flags require --source binance-public and cannot be combined with other sources"
        )
    if not args.allow_network:
        args.parser.error("--allow-network is required when --source binance-public is provided")
    if args.ccxt_feed is not None or args.exchange != "binance" or args.since is not None or args.limit is not None:
        args.parser.error("CCXT-only flags cannot be combined with --source binance-public")
    if _has_binance_usdm_specific_flags(args):
        args.parser.error("Binance USD-M flags cannot be combined with --source binance-public")
    if _has_dex_or_defi_specific_flags(args):
        args.parser.error("DEX/DeFi flags cannot be combined with --source binance-public")
    if _has_onchain_specific_flags(args):
        args.parser.error("Dune/TheGraph flags cannot be combined with --source binance-public")

    missing = [
        option
        for option, value in (
            ("--public-data-market", args.public_data_market),
            ("--symbol", args.symbol),
            ("--timeframe", args.timeframe),
            ("--year", args.year),
            ("--month", args.month),
        )
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source binance-public is provided")


def _require_binance_usdm_args(args: argparse.Namespace, *name_value_pairs) -> None:
    missing = [
        name
        for name, value in zip(name_value_pairs[0::2], name_value_pairs[1::2], strict=True)
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        args.parser.error(f"{', '.join(missing)} required when --source binance-usdm is provided")


def _reject_binance_usdm_args(args: argparse.Namespace, *name_value_pairs) -> None:
    present = [
        name
        for name, value in zip(name_value_pairs[0::2], name_value_pairs[1::2], strict=True)
        if value is not None and (not isinstance(value, str) or bool(value.strip()))
    ]
    if present:
        args.parser.error(f"{', '.join(present)} cannot be combined with {args.binance_usdm_feed}")


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
    if args.ccxt_feed == "open-interest-history":
        return ingest_ccxt_open_interest_history(
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


def _run_binance_public_ingestion(args: argparse.Namespace):
    if args.public_data_market == "um-futures":
        return ingest_binance_public_um_futures_month(
            args.db,
            symbol=args.symbol,
            interval=args.timeframe,
            year=args.year,
            month=args.month,
            allow_network=True,
        )
    return ingest_binance_public_month(
        args.db,
        symbol=args.symbol,
        interval=args.timeframe,
        year=args.year,
        month=args.month,
        allow_network=True,
    )


def _run_binance_usdm_ingestion(args: argparse.Namespace):
    if args.binance_usdm_feed == "premium-index-klines":
        return ingest_binance_usdm_premium_index_klines(
            args.db,
            symbol=args.symbol,
            interval=args.interval,
            limit=args.limit,
            start_time_ms=args.start_time_ms,
            end_time_ms=args.end_time_ms,
            allow_network=True,
        )
    if args.binance_usdm_feed == "basis":
        return ingest_binance_usdm_basis(
            args.db,
            pair=args.pair,
            contract_type=args.contract_type,
            period=args.period,
            limit=args.limit,
            start_time_ms=args.start_time_ms,
            end_time_ms=args.end_time_ms,
            allow_network=True,
        )
    if args.binance_usdm_feed == "global-long-short-account-ratio":
        return ingest_binance_usdm_global_long_short_account_ratio(
            args.db,
            symbol=args.symbol,
            period=args.period,
            limit=args.limit,
            start_time_ms=args.start_time_ms,
            end_time_ms=args.end_time_ms,
            allow_network=True,
        )
    return ingest_binance_usdm_taker_buy_sell_volume(
        args.db,
        symbol=args.symbol,
        period=args.period,
        limit=args.limit,
        start_time_ms=args.start_time_ms,
        end_time_ms=args.end_time_ms,
        allow_network=True,
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
    runtime: RealLLMRuntime = args.llm_runtime
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
    payload = plan.model_dump(mode="json")
    schedule_ref = _schedule_plan_reference(payload)
    payload["run_id"] = schedule_ref
    try:
        judgement = run_runtime_command_judgement(
            runtime,
            command="schedule",
            facts=payload,
            evidence_refs=[f"schedule:{schedule_ref}"],
            objective="Review the planned evidence-run schedule before operator use.",
        )
    except LLMProviderError as exc:
        args.parser.error(str(_llm_provider_runtime_error(exc)))
        raise AssertionError("argparse parser.error should exit") from exc
    except (LLMRuntimeError, ValueError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    payload["llm_judgement"] = judgement.model_dump(mode="json")
    payload.update(runtime.metadata())
    return payload


def _schedule_plan_reference(payload: dict[str, Any]) -> str:
    for command in payload.get("planned_commands", []):
        if not isinstance(command, dict) or command.get("name") != "evidence-run":
            continue
        argv = command.get("argv", [])
        if isinstance(argv, list) and "--run-id" in argv:
            index = argv.index("--run-id")
            if index + 1 < len(argv):
                value = argv[index + 1]
                if isinstance(value, str) and value.strip():
                    return value.strip()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"schedule-plan-{digest}"


if __name__ == "__main__":
    raise SystemExit(main())
