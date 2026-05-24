from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.ingestion import (
    ingest_binance_public_month,
    ingest_ccxt_funding_rate_history,
    ingest_ccxt_open_interest_history,
)
from crypto_alpha_agent.data.source_probe import probe_target
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.pipeline.evidence_reports import build_weekly_evidence_report
from crypto_alpha_agent.pipeline.evidence_run_ops import (
    NetworkRoute,
    network_route_from_environment,
    redacted_evidence_run_inputs,
    redacted_failure,
)
from crypto_alpha_agent.pipeline.governance_reports import build_profit_governance_report
from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
from crypto_alpha_agent.pipeline.research_loop import ValidationSummary, run_stored_research_loop
from crypto_alpha_agent.strategy import default_strategy_registry

Classification = Literal[
    "usable",
    "blocked",
    "negative_after_costs",
    "observe_out_of_sample",
    "research_only",
]

_SOURCE_PROBE_TARGETS = (
    "binance_usdm_open_interest_history",
    "binance_usdm_basis",
    "binance_usdm_global_long_short_account_ratio",
)


class _StrictBootstrapModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class HistoricalBootstrapWindow(_StrictBootstrapModel):
    window_id: str = Field(min_length=1)
    start_at: datetime
    end_at: datetime
    price_symbol: str = Field(min_length=1)
    funding_symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    record_count: int = Field(ge=0)


class HistoricalBootstrapSourceStep(_StrictBootstrapModel):
    source_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    feed: str = Field(min_length=1)
    status: Literal["completed", "blocked", "failed", "skipped"]
    network_route: NetworkRoute
    records_written: int = Field(ge=0)
    window_id: str | None = None
    reason_code: str | None = None
    failure: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class HistoricalBootstrapStrategyResult(_StrictBootstrapModel):
    window_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    paper_simulation_supported: bool
    validation_status: Literal["passed", "blocked", "unsupported"]
    validation_trade_count: int = Field(ge=0)
    validation_blocked_reasons: list[str] = Field(default_factory=list)
    validation_metrics: dict[str, Any] = Field(default_factory=dict)
    paper_outcome_count: int = Field(ge=0)
    paper_net_pnl_usd: float = Field(default=0.0)
    paper_statuses: list[str] = Field(default_factory=list)
    paper_blocked_reasons: list[str] = Field(default_factory=list)
    cost_model_modes: list[str] = Field(default_factory=list)
    governance_action: str = Field(min_length=1)
    classification: Classification
    evidence_refs: list[str] = Field(default_factory=list)


class HistoricalBootstrapSampleTargets(_StrictBootstrapModel):
    paper_observation_targets: list[int] = Field(default_factory=lambda: [30, 60])
    calendar_day_target: int = 90
    current_observations_by_family: dict[str, int] = Field(default_factory=dict)
    current_calendar_days_by_family: dict[str, int] = Field(default_factory=dict)


class HistoricalBootstrapManifest(_StrictBootstrapModel):
    run_id: str = Field(min_length=1)
    status: Literal["success", "failed", "blocked"]
    started_at: str
    completed_at: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    network_route: NetworkRoute
    memory_path: str
    report_path: str | None = None
    json_path: str | None = None
    manifest_path: str | None = None
    source_health: list[dict[str, Any]] = Field(default_factory=list)
    records_written: int = Field(ge=0)
    reason_code: str | None = None
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class HistoricalBootstrapReport(_StrictBootstrapModel):
    command: Literal["historical-bootstrap"] = "historical-bootstrap"
    run_id: str = Field(min_length=1)
    db_path: str = Field(min_length=1)
    memory_path: str = Field(min_length=1)
    current_capital_usd: float = Field(ge=0)
    network_route: NetworkRoute
    bootstrap_windows: list[HistoricalBootstrapWindow]
    source_steps: list[HistoricalBootstrapSourceStep]
    strategy_results: list[HistoricalBootstrapStrategyResult]
    weekly_sample_progress: dict[str, int] = Field(default_factory=dict)
    governance_actions: dict[str, str] = Field(default_factory=dict)
    sample_targets: HistoricalBootstrapSampleTargets
    out_of_sample_policy: Literal["future_evidence_run_observations_only"] = (
        "future_evidence_run_observations_only"
    )
    manifest: HistoricalBootstrapManifest
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_historical_bootstrap_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    run_id: str | None = None,
    current_capital_usd: float = 300.0,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    bootstrap_windows: Sequence[str] = (),
    strategy_families: Sequence[str] | None = None,
    allow_network: bool = False,
    binance_symbol: str | None = None,
    ccxt_exchange: str = "binance",
    limit: int = 1000,
    notional_usd: float = 25.0,
    report_path: str | Path | None = None,
    json_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> HistoricalBootstrapReport:
    started_at = datetime.now(tz=UTC)
    resolved_run_id = run_id or f"historical-bootstrap-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    db = Path(db_path)
    memory = Path(memory_path)
    windows = _parse_windows(
        bootstrap_windows,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
    )
    if allow_network and not bootstrap_windows:
        raise ValueError("network bootstrap requires at least one explicit YYYY-MM-DD/YYYY-MM-DD window")
    route = network_route_from_environment(allow_network=allow_network)
    registry = default_strategy_registry(current_capital_usd=current_capital_usd)
    families = _normalize_families(strategy_families) or list(registry.list_families())
    registered_families = set(registry.list_families())
    unknown_families = [family for family in families if family not in registered_families]
    if unknown_families:
        raise ValueError(f"unknown strategy family: {', '.join(unknown_families)}")
    source_steps: list[HistoricalBootstrapSourceStep] = []
    strategy_results: list[HistoricalBootstrapStrategyResult] = []

    for window in windows:
        source_steps.extend(
            _collect_window_sources(
                db_path=db,
                window=window,
                allow_network=allow_network,
                network_route=route,
                binance_symbol=binance_symbol or price_symbol.replace("/", ""),
                ccxt_exchange=ccxt_exchange,
                funding_symbol=funding_symbol,
                timeframe=timeframe,
                limit=limit,
            )
        )
        strategy_results.extend(
            _run_window_strategies(
                db_path=db,
                run_id=resolved_run_id,
                window=window,
                current_capital_usd=current_capital_usd,
                price_symbol=price_symbol,
                funding_symbol=funding_symbol,
                timeframe=timeframe,
                families=families,
                notional_usd=notional_usd,
            )
        )

    source_steps.extend(
        _probe_required_sources(
            db_path=db,
            allow_network=allow_network,
        )
    )
    weekly_report = build_weekly_evidence_report(
        db_path=db,
        memory_path=memory,
        persist_degradation=False,
    )
    governance_report = build_profit_governance_report(
        db_path=db,
        memory_path=memory,
        current_capital_usd=current_capital_usd,
    )
    governance_actions = {
        row.strategy_family: row.governance_action
        for row in governance_report.family_scoreboard
    }
    enriched_results = [
        result.model_copy(
            update={
                "governance_action": governance_actions.get(
                    result.strategy_family,
                    result.governance_action,
                ),
                "classification": _classification(
                    governance_actions.get(result.strategy_family, result.governance_action),
                    result,
                ),
            }
        )
        for result in strategy_results
    ]
    sample_targets = _sample_targets(db)
    completed_at = datetime.now(tz=UTC)
    manifest_status = _manifest_status(source_steps, allow_network=allow_network)
    manifest = HistoricalBootstrapManifest(
        run_id=resolved_run_id,
        status=manifest_status,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        inputs=redacted_evidence_run_inputs(
            {
                "run_id": resolved_run_id,
                "db_path": db,
                "memory_path": memory,
                "price_symbol": price_symbol,
                "funding_symbol": funding_symbol,
                "timeframe": timeframe,
                "bootstrap_windows": list(bootstrap_windows),
                "strategy_families": families,
                "allow_network": allow_network,
                "binance_symbol": binance_symbol,
                "ccxt_exchange": ccxt_exchange,
                "limit": limit,
                "notional_usd": notional_usd,
            }
        ),
        network_route=route,
        memory_path=str(memory),
        report_path=None if report_path is None else str(report_path),
        json_path=None if json_path is None else str(json_path),
        manifest_path=None if manifest_path is None else str(manifest_path),
        source_health=[step.model_dump(mode="json") for step in source_steps],
        records_written=sum(step.records_written for step in source_steps),
        reason_code=None if manifest_status == "success" else "source_collection_incomplete",
    )
    return HistoricalBootstrapReport(
        run_id=resolved_run_id,
        db_path=str(db),
        memory_path=str(memory),
        current_capital_usd=current_capital_usd,
        network_route=route,
        bootstrap_windows=[
            window.model_copy(update={"record_count": _record_count(db, window)})
            for window in windows
        ],
        source_steps=source_steps,
        strategy_results=enriched_results,
        weekly_sample_progress=weekly_report.sample_size_progress,
        governance_actions=governance_actions,
        sample_targets=sample_targets,
        manifest=manifest,
    )


def _parse_windows(
    windows: Sequence[str],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> list[HistoricalBootstrapWindow]:
    if not windows:
        return [
            HistoricalBootstrapWindow(
                window_id="stored_all",
                start_at=datetime(1970, 1, 1, tzinfo=UTC),
                end_at=datetime(9999, 1, 1, tzinfo=UTC),
                price_symbol=price_symbol,
                funding_symbol=funding_symbol,
                timeframe=timeframe,
                record_count=0,
            )
        ]
    parsed = [
        _parse_window(
            window,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
        )
        for window in windows
    ]
    return parsed


def _parse_window(
    raw_window: str,
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> HistoricalBootstrapWindow:
    start_text, separator, end_text = raw_window.partition("/")
    if not separator:
        raise ValueError("bootstrap windows must use YYYY-MM-DD/YYYY-MM-DD")
    start_at = _parse_utc_date(start_text)
    end_at = _parse_utc_date(end_text)
    if end_at <= start_at:
        raise ValueError("bootstrap window end must be after start")
    window_id = f"{start_text.strip()}_{end_text.strip()}"
    return HistoricalBootstrapWindow(
        window_id=window_id,
        start_at=start_at,
        end_at=end_at,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        record_count=0,
    )


def _parse_utc_date(text: str) -> datetime:
    try:
        parsed = date.fromisoformat(text.strip())
    except ValueError as exc:
        raise ValueError("bootstrap windows must use YYYY-MM-DD/YYYY-MM-DD") from exc
    return datetime.combine(parsed, time.min, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _WindowSegment:
    month_start: datetime
    start_at: datetime
    end_at: datetime


def _window_segments(window: HistoricalBootstrapWindow) -> list[_WindowSegment]:
    segments: list[_WindowSegment] = []
    cursor = datetime(window.start_at.year, window.start_at.month, 1, tzinfo=UTC)
    while cursor < window.end_at:
        month_end = _next_month_start(cursor)
        segment_start = max(window.start_at, cursor)
        segment_end = min(window.end_at, month_end)
        if segment_end > segment_start:
            segments.append(
                _WindowSegment(
                    month_start=cursor,
                    start_at=segment_start,
                    end_at=segment_end,
                )
            )
        cursor = month_end
    return segments


def _next_month_start(value: datetime) -> datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return datetime(year, month, 1, tzinfo=UTC)


def _collect_window_sources(
    *,
    db_path: Path,
    window: HistoricalBootstrapWindow,
    allow_network: bool,
    network_route: NetworkRoute,
    binance_symbol: str,
    ccxt_exchange: str,
    funding_symbol: str,
    timeframe: str,
    limit: int,
) -> list[HistoricalBootstrapSourceStep]:
    if not allow_network:
        return [
            _blocked_source_step(
                "binance_public_klines",
                source="binance_public",
                feed="klines",
                window=window,
                network_route=network_route,
                parameters={
                    "symbol": binance_symbol,
                    "timeframe": timeframe,
                    "start_at": window.start_at.isoformat(),
                    "end_at": window.end_at.isoformat(),
                },
            ),
            _blocked_source_step(
                "ccxt_funding_rate_history",
                source="ccxt",
                feed="funding_rate_history",
                window=window,
                network_route=network_route,
                parameters={
                    "exchange": ccxt_exchange,
                    "symbol": funding_symbol,
                    "since": _milliseconds(window.start_at),
                    "limit": limit,
                },
            ),
            _blocked_source_step(
                "ccxt_open_interest_history",
                source="ccxt",
                feed="open_interest_history",
                window=window,
                network_route=network_route,
                parameters={
                    "exchange": ccxt_exchange,
                    "symbol": funding_symbol,
                    "timeframe": timeframe,
                    "since": _milliseconds(window.start_at),
                    "limit": limit,
                },
            ),
        ]

    steps: list[HistoricalBootstrapSourceStep] = []
    for segment in _window_segments(window):
        steps.append(
            _ingest_source_step(
                "binance_public_klines",
                source="binance_public",
                feed="klines",
                window=window,
                network_route=network_route,
                parameters={
                    "symbol": binance_symbol,
                    "timeframe": timeframe,
                    "year": segment.month_start.year,
                    "month": segment.month_start.month,
                    "observed_at_start": segment.start_at.isoformat(),
                    "observed_at_end": segment.end_at.isoformat(),
                },
                run=lambda segment=segment: ingest_binance_public_month(
                    db_path,
                    symbol=binance_symbol,
                    interval=timeframe,
                    year=segment.month_start.year,
                    month=segment.month_start.month,
                    allow_network=True,
                    observed_at_start=segment.start_at,
                    observed_at_end=segment.end_at,
                ).records_written,
            )
        )
        steps.append(
            _ingest_source_step(
                "ccxt_funding_rate_history",
                source="ccxt",
                feed="funding_rate_history",
                window=window,
                network_route=network_route,
                parameters={
                    "exchange": ccxt_exchange,
                    "symbol": funding_symbol,
                    "since": _milliseconds(segment.start_at),
                    "observed_at_end": segment.end_at.isoformat(),
                    "limit": limit,
                },
                run=lambda segment=segment: ingest_ccxt_funding_rate_history(
                    db_path,
                    symbol=funding_symbol,
                    since=_milliseconds(segment.start_at),
                    limit=limit,
                    allow_network=True,
                    exchange_id=ccxt_exchange,
                    observed_at_start=segment.start_at,
                    observed_at_end=segment.end_at,
                ).records_written,
            )
        )
        steps.append(
            _ingest_source_step(
                "ccxt_open_interest_history",
                source="ccxt",
                feed="open_interest_history",
                window=window,
                network_route=network_route,
                parameters={
                    "exchange": ccxt_exchange,
                    "symbol": funding_symbol,
                    "timeframe": timeframe,
                    "since": _milliseconds(segment.start_at),
                    "observed_at_end": segment.end_at.isoformat(),
                    "limit": limit,
                },
                run=lambda segment=segment: ingest_ccxt_open_interest_history(
                    db_path,
                    symbol=funding_symbol,
                    timeframe=timeframe,
                    since=_milliseconds(segment.start_at),
                    limit=limit,
                    allow_network=True,
                    exchange_id=ccxt_exchange,
                    observed_at_start=segment.start_at,
                    observed_at_end=segment.end_at,
                ).records_written,
            )
        )
    return steps


def _blocked_source_step(
    source_id: str,
    *,
    source: str,
    feed: str,
    window: HistoricalBootstrapWindow,
    network_route: NetworkRoute,
    parameters: dict[str, Any],
) -> HistoricalBootstrapSourceStep:
    return HistoricalBootstrapSourceStep(
        source_id=source_id,
        source=source,
        feed=feed,
        status="blocked",
        network_route=network_route,
        records_written=0,
        window_id=window.window_id,
        reason_code="network_not_allowed",
        parameters=parameters,
    )


def _ingest_source_step(
    source_id: str,
    *,
    source: str,
    feed: str,
    window: HistoricalBootstrapWindow,
    network_route: NetworkRoute,
    parameters: dict[str, Any],
    run: Callable[[], int],
) -> HistoricalBootstrapSourceStep:
    try:
        records_written = int(run())
    except Exception as exc:
        return HistoricalBootstrapSourceStep(
            source_id=source_id,
            source=source,
            feed=feed,
            status="failed",
            network_route=network_route,
            records_written=0,
            window_id=window.window_id,
            reason_code="source_failed",
            failure=redacted_failure(str(exc)),
            parameters=parameters,
        )
    return HistoricalBootstrapSourceStep(
        source_id=source_id,
        source=source,
        feed=feed,
        status="completed",
        network_route=network_route,
        records_written=records_written,
        window_id=window.window_id,
        parameters=parameters,
    )


def _probe_required_sources(
    *,
    db_path: Path,
    allow_network: bool,
) -> list[HistoricalBootstrapSourceStep]:
    steps = []
    for target in _SOURCE_PROBE_TARGETS:
        try:
            result = probe_target(
                db_path=db_path,
                target_id=target,
                allow_network=allow_network,
                route="auto",
            )
        except Exception as exc:
            steps.append(
                HistoricalBootstrapSourceStep(
                    source_id=target,
                    source="source_probe",
                    feed=target,
                    status="failed",
                    network_route="unknown",
                    records_written=0,
                    reason_code="source_probe_failed",
                    failure=redacted_failure(str(exc)),
                )
            )
            continue
        status: Literal["completed", "blocked", "failed"] = (
            "completed" if result.exit_code == 0 else "blocked"
        )
        steps.append(
            HistoricalBootstrapSourceStep(
                source_id=target,
                source=result.source,
                feed=result.feed,
                status=status,
                network_route="blocked" if result.network_route == "unavailable" else result.network_route,
                records_written=0,
                reason_code=result.blocked_reason,
                parameters={
                    "provider_status": result.provider_status,
                    "typed_record_count": result.typed_record_count,
                    "endpoint_family": result.endpoint_family,
                },
            )
        )
    return steps


def _run_window_strategies(
    *,
    db_path: Path,
    run_id: str,
    window: HistoricalBootstrapWindow,
    current_capital_usd: float,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    families: Sequence[str],
    notional_usd: float,
) -> list[HistoricalBootstrapStrategyResult]:
    registry = default_strategy_registry(current_capital_usd=current_capital_usd)
    results = []
    for family in families:
        spec = registry.get(family)
        validation_report = run_stored_research_loop(
            db_path,
            current_capital_usd=current_capital_usd,
            run_id=f"{run_id}:{window.window_id}:{family}:validation",
            include_validation=True,
            strategy_family=family,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            validation_timeframe=timeframe,
            observed_at_start=window.start_at,
            observed_at_end=window.end_at,
            persist_validation_evidence=False,
        )
        validation_summary = (
            validation_report.validation_summaries[0]
            if validation_report.validation_summaries
            else _unsupported_validation_summary(family, price_symbol, timeframe)
        )
        if not spec.supports_paper_simulation:
            results.append(
                _strategy_result(
                    window=window,
                    family=family,
                    paper_supported=False,
                    validation_summary=validation_summary,
                    outcomes=[],
                    governance_action="add_data",
                    classification="research_only",
                    extra_blocked_reasons=["paper_simulation_not_supported"],
                )
            )
            continue
        try:
            paper_report = run_paper_sim_loop(
                db_path,
                run_id=f"{run_id}:{window.window_id}:{family}:paper",
                strategy_family=family,
                price_symbol=price_symbol,
                funding_symbol=funding_symbol,
                timeframe=timeframe,
                current_capital_usd=current_capital_usd,
                notional_usd=notional_usd,
                observed_at_start=window.start_at,
                observed_at_end=window.end_at,
                persist_outcomes=False,
            )
            outcomes = paper_report.outcomes
        except Exception as exc:
            outcomes = []
            validation_summary = validation_summary.model_copy(
                update={
                    "status": "blocked",
                    "blocked_reasons": [
                        *validation_summary.blocked_reasons,
                        "paper_simulation_error",
                    ],
                }
            )
            extra = [f"paper_simulation_error:{exc.__class__.__name__}"]
        else:
            extra = []
        results.append(
            _strategy_result(
                window=window,
                family=family,
                paper_supported=True,
                validation_summary=validation_summary,
                outcomes=outcomes,
                governance_action="add_data",
                classification="blocked",
                extra_blocked_reasons=extra,
            )
        )
    return results


def _strategy_result(
    *,
    window: HistoricalBootstrapWindow,
    family: str,
    paper_supported: bool,
    validation_summary: ValidationSummary,
    outcomes: Sequence[Any],
    governance_action: str,
    classification: Classification,
    extra_blocked_reasons: Sequence[str] = (),
) -> HistoricalBootstrapStrategyResult:
    paper_blocked_reasons = _dedupe(
        [
            reason
            for outcome in outcomes
            for reason in getattr(outcome, "failure_reasons", ())
        ]
    )
    paper_net_pnl_usd = sum(float(getattr(outcome, "net_pnl_usd", 0.0)) for outcome in outcomes)
    validation_metrics = {
        "trade_count": validation_summary.trade_count,
        "gross_expectancy": validation_summary.gross_expectancy,
        "net_return": validation_summary.net_return,
        "max_drawdown": validation_summary.max_drawdown,
        "fee_adjusted_expectancy": validation_summary.fee_adjusted_expectancy,
        "slippage_adjusted_expectancy": validation_summary.slippage_adjusted_expectancy,
        "walk_forward_split_count": validation_summary.walk_forward_split_count,
        "walk_forward_pass_rate": validation_summary.walk_forward_pass_rate,
    }
    return HistoricalBootstrapStrategyResult(
        window_id=window.window_id,
        strategy_family=family,
        paper_simulation_supported=paper_supported,
        validation_status=validation_summary.status if paper_supported else "unsupported",
        validation_trade_count=validation_summary.trade_count,
        validation_blocked_reasons=_dedupe(
            [*validation_summary.blocked_reasons, *extra_blocked_reasons]
        ),
        validation_metrics=validation_metrics,
        paper_outcome_count=len(outcomes),
        paper_net_pnl_usd=paper_net_pnl_usd,
        paper_statuses=_dedupe([str(getattr(outcome, "status", "")) for outcome in outcomes]),
        paper_blocked_reasons=paper_blocked_reasons,
        cost_model_modes=_dedupe(
            [
                str(getattr(outcome, "cost_model_mode", ""))
                for outcome in outcomes
                if getattr(outcome, "cost_model_mode", None)
            ]
        ),
        governance_action=governance_action,
        classification=classification,
        evidence_refs=[
            f"validation:{family}:{window.window_id}",
            *[
                f"paper:{getattr(outcome, 'outcome_id', '')}"
                for outcome in outcomes
                if getattr(outcome, "outcome_id", "")
            ],
        ],
    )


def _classification(
    governance_action: str,
    result: HistoricalBootstrapStrategyResult,
) -> Classification:
    if not result.paper_simulation_supported:
        return "research_only"
    if result.validation_status != "passed":
        return "blocked"
    if not result.paper_outcome_count:
        return "blocked"
    if "pre_cost_only_profitable" in result.paper_blocked_reasons:
        return "negative_after_costs"
    if result.paper_net_pnl_usd <= 0.0:
        if result.paper_outcome_count and any(status == "closed" for status in result.paper_statuses):
            return "negative_after_costs"
        return "blocked"
    if governance_action == "owner_decision_review":
        return "usable"
    if governance_action == "keep_collecting":
        return "observe_out_of_sample"
    if governance_action == "stop":
        return "negative_after_costs"
    if any(status == "closed" for status in result.paper_statuses):
        return "observe_out_of_sample"
    return "blocked"


def _sample_targets(db_path: Path) -> HistoricalBootstrapSampleTargets:
    observations: dict[str, int] = {}
    days: dict[str, set[str]] = {}
    for outcome in PaperOutcomeLedger(db_path).load_outcomes():
        observations[outcome.strategy_family] = observations.get(outcome.strategy_family, 0) + 1
        days.setdefault(outcome.strategy_family, set()).add(outcome.observed_at.date().isoformat())
    return HistoricalBootstrapSampleTargets(
        current_observations_by_family=observations,
        current_calendar_days_by_family={
            family: len(values)
            for family, values in sorted(days.items())
        },
    )


def _record_count(db_path: Path, window: HistoricalBootstrapWindow) -> int:
    from crypto_alpha_agent.data.store import ResearchDataStore

    return len(
        ResearchDataStore(db_path).load_records(
            observed_at_start=window.start_at,
            observed_at_end=window.end_at,
        )
    )


def _unsupported_validation_summary(
    family: str,
    price_symbol: str,
    timeframe: str,
) -> ValidationSummary:
    return ValidationSummary(
        strategy_family=family,
        asset=price_symbol,
        timeframe=timeframe,
        status="blocked",
        trade_count=0,
        validator_name="strategy_registry",
        blocked_reasons=["validation_summary_missing"],
    )


def _milliseconds(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _normalize_families(families: Sequence[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for family in families or []:
        stripped = family.strip()
        if stripped and stripped not in seen:
            normalized.append(stripped)
            seen.add(stripped)
    return normalized


def _manifest_status(
    source_steps: Sequence[HistoricalBootstrapSourceStep],
    *,
    allow_network: bool,
) -> Literal["success", "failed", "blocked"]:
    if not allow_network:
        return "success"
    for step in source_steps:
        if step.status == "failed":
            return "failed"
        if step.status == "blocked" and step.reason_code != "network_not_allowed":
            return "failed"
    return "success"


def _dedupe(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
