from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from math import isfinite
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.pipeline.candidate_screens import (
    CandidateScreenId,
    candidate_screen_catalog,
    evaluate_candidate_screen,
)
from crypto_alpha_agent.pipeline.evidence_universe import (
    EvidenceUniverseReport,
    build_evidence_universe_report,
)

CandidateFeasibilityReadiness = Literal["feasible", "blocked"]
CandidateStateTarget = Literal[
    "candidate",
    "source_qualified",
    "feasibility_passed",
    "backtest_passed",
    "paper_collecting",
    "stopped",
    "redesign_required",
]
MultiHypothesisBlockedReason = Literal[
    "insufficient_universe_coverage",
    "insufficient_samples",
    "insufficient_walk_forward_splits",
    "non_positive_cost_adjusted_expectancy",
    "unstable_walk_forward_performance",
    "cost_sensitivity_fragile",
    "single_asset_or_time_window_dependency",
    "lookahead_risk",
    "watchlist_only_source",
]

MULTI_HYPOTHESIS_BLOCKED_REASONS: tuple[MultiHypothesisBlockedReason, ...] = (
    "insufficient_universe_coverage",
    "insufficient_samples",
    "insufficient_walk_forward_splits",
    "non_positive_cost_adjusted_expectancy",
    "unstable_walk_forward_performance",
    "cost_sensitivity_fragile",
    "single_asset_or_time_window_dependency",
    "lookahead_risk",
    "watchlist_only_source",
)
DEFAULT_COST_BPS_GRID: tuple[float, ...] = (5.0, 10.0, 20.0, 50.0)
_BASELINE_COST_BPS = 10.0
_MARKET_EXECUTION_SCREENS = {
    "short_horizon_momentum_volatility_filter",
    "short_horizon_reversal_volatility_filter",
    "cross_asset_ranking_turnover_cap",
}


class _StrictMultiHypothesisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class CostSensitivityMetric(_StrictMultiHypothesisModel):
    cost_bps: float = Field(ge=0)
    gross_mean: float
    net_mean: float
    win_rate: float = Field(ge=0, le=1)


class CandidateSplitMetric(_StrictMultiHypothesisModel):
    split_index: int = Field(ge=1)
    train_observations: int = Field(ge=0)
    test_observations: int = Field(ge=0)
    test_start: datetime
    test_end: datetime
    selected_symbol_counts: dict[str, int] = Field(default_factory=dict)
    gross_mean: float
    net_mean: float
    win_rate: float = Field(ge=0, le=1)


class CandidateFeasibilityMetric(_StrictMultiHypothesisModel):
    candidate: CandidateScreenId
    readiness: CandidateFeasibilityReadiness
    sample_count: int = Field(ge=0)
    asset_coverage: dict[str, int] = Field(default_factory=dict)
    split_coverage: int = Field(ge=0)
    gross_mean: float | None = None
    net_mean: float | None = None
    win_rate: float | None = Field(default=None, ge=0, le=1)
    turnover: float = Field(ge=0)
    selected_symbol_counts: dict[str, int] = Field(default_factory=dict)
    cost_sensitivity: list[CostSensitivityMetric] = Field(default_factory=list)
    split_metrics: list[CandidateSplitMetric] = Field(default_factory=list)
    reason_codes: list[MultiHypothesisBlockedReason] = Field(default_factory=list)
    candidate_state_target: CandidateStateTarget


class MultiHypothesisFeasibilityReport(_StrictMultiHypothesisModel):
    command: Literal["strategy-feasibility"] = "strategy-feasibility"
    mode: Literal["multi-hypothesis-lab"] = "multi-hypothesis-lab"
    generated_at: datetime
    timeframe: str
    symbols: list[str]
    current_capital_usd: float = Field(ge=0)
    cost_bps_grid: list[float]
    readiness: CandidateFeasibilityReadiness
    reason_codes: list[MultiHypothesisBlockedReason] = Field(default_factory=list)
    universe: EvidenceUniverseReport
    candidate_metrics: list[CandidateFeasibilityMetric]
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


@dataclass(frozen=True)
class _MarketRow:
    symbol: str
    timestamp: datetime
    close: float


@dataclass(frozen=True)
class _Observation:
    timestamp: datetime
    selected_symbol: str
    gross_return: float


def build_multi_hypothesis_feasibility_report(
    db_path: str | Path,
    *,
    memory_path: str | Path,
    symbols: list[str],
    timeframe: str,
    current_capital_usd: float,
    cost_bps_grid: list[float] | None = None,
    min_split_count: int = 3,
    candidates: list[str] | None = None,
    evaluation_start: datetime | None = None,
    evaluation_end: datetime | None = None,
) -> MultiHypothesisFeasibilityReport:
    del memory_path
    _validate_min_split_count(min_split_count)
    normalized_symbols = _dedupe_preserving_order(symbols)
    normalized_cost_grid = _normalize_cost_grid(cost_bps_grid)
    selected_candidates = _normalize_candidates(candidates)
    universe = build_evidence_universe_report(
        db_path,
        symbols=normalized_symbols,
        timeframe=timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
    )
    records = _load_records_read_only(db_path)
    market_by_symbol = _market_rows_by_symbol(
        records,
        normalized_symbols,
        timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
    )
    candidate_metrics = [
        _candidate_metric(
            db_path,
            screen_id,
            universe,
            market_by_symbol,
            symbols=normalized_symbols,
            timeframe=timeframe,
            cost_bps_grid=normalized_cost_grid,
            min_split_count=min_split_count,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        for screen_id in selected_candidates
    ]
    feasible_metrics = [
        metric for metric in candidate_metrics if metric.readiness == "feasible"
    ]
    reason_codes = (
        []
        if feasible_metrics
        else _dedupe_preserving_order(
            reason
            for metric in candidate_metrics
            for reason in metric.reason_codes
        )
    )
    return MultiHypothesisFeasibilityReport(
        generated_at=universe.generated_at,
        timeframe=timeframe,
        symbols=normalized_symbols,
        current_capital_usd=current_capital_usd,
        cost_bps_grid=normalized_cost_grid,
        readiness="feasible" if feasible_metrics else "blocked",
        reason_codes=reason_codes,
        universe=universe,
        candidate_metrics=candidate_metrics,
        uses_real_capital=False,
        live_order_routing=False,
    )


def render_multi_hypothesis_feasibility_markdown(
    report: MultiHypothesisFeasibilityReport,
) -> str:
    lines = [
        "# Multi-Hypothesis Feasibility Lab",
        "",
        "## Safety",
        f"Real capital: {str(report.uses_real_capital).lower()}",
        f"Live order routing: {str(report.live_order_routing).lower()}",
        "",
        "## Decision",
        f"Readiness: {report.readiness}",
        f"Reason codes: {', '.join(report.reason_codes) or 'none'}",
        "",
        "## Universe",
        f"Point in time: {str(report.universe.point_in_time_universe).lower()}",
        f"Universe reasons: {', '.join(report.universe.reason_codes) or 'none'}",
        "",
        "## Candidates",
        "| Candidate | Readiness | Samples | Assets | Splits | Gross mean | Net mean | Win rate | Turnover | State target | Reasons |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for metric in report.candidate_metrics:
        lines.append(
            "| "
            + " | ".join(
                [
                    metric.candidate,
                    metric.readiness,
                    f"{metric.sample_count:g}",
                    f"{len(metric.asset_coverage):g}",
                    f"{metric.split_coverage:g}",
                    _format_optional_mean(metric.gross_mean),
                    _format_optional_mean(metric.net_mean),
                    _format_optional_rate(metric.win_rate),
                    f"{metric.turnover:.4f}",
                    metric.candidate_state_target,
                    ", ".join(metric.reason_codes) or "none",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Cost Sensitivity",
            "| Candidate | Cost bps | Gross mean | Net mean | Win rate |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for metric in report.candidate_metrics:
        if not metric.cost_sensitivity:
            lines.append(f"| {metric.candidate} | 0 | 0 | 0 | 0 |")
            continue
        for cost_metric in metric.cost_sensitivity:
            lines.append(
                "| "
                + " | ".join(
                    [
                        metric.candidate,
                        f"{cost_metric.cost_bps:g}",
                        f"{cost_metric.gross_mean:.8f}",
                        f"{cost_metric.net_mean:.8f}",
                        f"{cost_metric.win_rate:.4f}",
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Walk Forward",
            "| Candidate | Split | Train observations | Test observations | Test start | Test end | Net mean | Win rate |",
            "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |",
        ]
    )
    for metric in report.candidate_metrics:
        if not metric.split_metrics:
            lines.append(f"| {metric.candidate} | 0 | 0 | 0 | n/a | n/a | 0 | 0 |")
            continue
        for split in metric.split_metrics:
            lines.append(
                "| "
                + " | ".join(
                    [
                        metric.candidate,
                        f"{split.split_index:g}",
                        f"{split.train_observations:g}",
                        f"{split.test_observations:g}",
                        split.test_start.isoformat(),
                        split.test_end.isoformat(),
                        f"{split.net_mean:.8f}",
                        f"{split.win_rate:.4f}",
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def _candidate_metric(
    db_path: str | Path,
    screen_id: CandidateScreenId,
    universe: EvidenceUniverseReport,
    market_by_symbol: dict[str, list[_MarketRow]],
    *,
    symbols: list[str],
    timeframe: str,
    cost_bps_grid: list[float],
    min_split_count: int,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> CandidateFeasibilityMetric:
    catalog = candidate_screen_catalog()
    definition = catalog[screen_id]
    screen_result = evaluate_candidate_screen(
        db_path,
        screen_id,
        symbols=symbols,
        timeframe=timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
    )

    reason_codes: list[MultiHypothesisBlockedReason] = []
    if not universe.point_in_time_universe or "lookahead_universe_risk" in universe.reason_codes:
        reason_codes.append("lookahead_risk")
    if (
        definition.execution_role == "watchlist_or_regime_only"
        or "watchlist_only_source" in screen_result.blocked_reasons
    ):
        reason_codes.append("watchlist_only_source")
    if _has_universe_coverage_gap(universe, screen_result):
        reason_codes.append("insufficient_universe_coverage")

    observations: list[_Observation] = []
    if not {"lookahead_risk", "watchlist_only_source"} & set(reason_codes):
        observations = _historical_observations(screen_id, market_by_symbol)
        if not observations and "insufficient_universe_coverage" not in reason_codes:
            reason_codes.append("insufficient_samples")

    baseline_cost_bps = _baseline_cost_bps(cost_bps_grid)
    cost_sensitivity = _cost_sensitivity(observations, cost_bps_grid)
    split_metrics = _walk_forward_metrics(
        observations,
        split_count=min_split_count,
        cost_bps=baseline_cost_bps,
    )
    if observations:
        if len(observations) < min_split_count * 2 or len(split_metrics) < min_split_count:
            reason_codes.append("insufficient_walk_forward_splits")
        baseline = _return_metric(observations, baseline_cost_bps)
        if baseline.net_mean <= 0:
            reason_codes.append("non_positive_cost_adjusted_expectancy")
        if any(split.net_mean <= 0 for split in split_metrics):
            reason_codes.append("unstable_walk_forward_performance")
        if any(metric.net_mean <= 0 for metric in cost_sensitivity):
            reason_codes.append("cost_sensitivity_fragile")
        gross_mean = baseline.gross_mean
        net_mean = baseline.net_mean
        win_rate = baseline.win_rate
    else:
        gross_mean = None
        net_mean = None
        win_rate = None

    reason_codes = _dedupe_preserving_order(reason_codes)
    asset_coverage = _asset_coverage(definition, market_by_symbol)
    selected_symbol_counts = dict(Counter(row.selected_symbol for row in observations))
    if (
        observations
        and len(asset_coverage) > 1
        and len(selected_symbol_counts) < 2
    ):
        reason_codes = _dedupe_preserving_order(
            [*reason_codes, "single_asset_or_time_window_dependency"]
        )
    return CandidateFeasibilityMetric(
        candidate=screen_id,
        readiness="blocked" if reason_codes else "feasible",
        sample_count=len(observations),
        asset_coverage=asset_coverage,
        split_coverage=len(split_metrics),
        gross_mean=gross_mean,
        net_mean=net_mean,
        win_rate=win_rate,
        turnover=_turnover(observations),
        selected_symbol_counts=selected_symbol_counts,
        cost_sensitivity=cost_sensitivity,
        split_metrics=split_metrics,
        reason_codes=reason_codes,
        candidate_state_target=_candidate_state_target(reason_codes),
    )


def _asset_coverage(
    definition,
    market_by_symbol: dict[str, list[_MarketRow]],
) -> dict[str, int]:
    if "market_candle" not in definition.required_record_types:
        return {}
    lookback = definition.min_history_bars
    coverage: dict[str, int] = {}
    for symbol, rows in market_by_symbol.items():
        count = max(0, len({row.timestamp for row in rows}) - lookback - 1)
        if count > 0:
            coverage[symbol] = count
    return coverage


def _historical_observations(
    screen_id: CandidateScreenId,
    market_by_symbol: dict[str, list[_MarketRow]],
) -> list[_Observation]:
    if screen_id not in _MARKET_EXECUTION_SCREENS:
        return []
    if screen_id == "cross_asset_ranking_turnover_cap":
        return _cross_asset_ranking_observations(market_by_symbol, lookback=72)
    direction_mode: Literal["momentum", "reversal"] = (
        "reversal" if screen_id == "short_horizon_reversal_volatility_filter" else "momentum"
    )
    return _per_symbol_return_observations(
        market_by_symbol,
        lookback=24,
        direction_mode=direction_mode,
    )


def _per_symbol_return_observations(
    market_by_symbol: dict[str, list[_MarketRow]],
    *,
    lookback: int,
    direction_mode: Literal["momentum", "reversal"],
) -> list[_Observation]:
    observations: list[_Observation] = []
    for symbol, rows in market_by_symbol.items():
        for index in range(lookback, len(rows) - 1):
            previous = rows[index - lookback]
            current = rows[index]
            next_row = rows[index + 1]
            if previous.close <= 0 or current.close <= 0:
                continue
            signal_return = current.close / previous.close - 1
            if direction_mode == "momentum" and signal_return <= 0:
                continue
            if direction_mode == "reversal" and signal_return >= 0:
                continue
            observations.append(
                _Observation(
                    timestamp=current.timestamp,
                    selected_symbol=symbol,
                    gross_return=next_row.close / current.close - 1,
                )
            )
    return sorted(observations, key=lambda row: (row.timestamp, row.selected_symbol))


def _cross_asset_ranking_observations(
    market_by_symbol: dict[str, list[_MarketRow]],
    *,
    lookback: int,
) -> list[_Observation]:
    timestamps = _aligned_timestamps(market_by_symbol)
    if len(timestamps) <= lookback + 1:
        return []
    by_symbol_time = {
        symbol: {row.timestamp: row for row in rows}
        for symbol, rows in market_by_symbol.items()
    }
    observations: list[_Observation] = []
    for index in range(lookback, len(timestamps) - 1):
        timestamp = timestamps[index]
        previous_timestamp = timestamps[index - lookback]
        next_timestamp = timestamps[index + 1]
        scored: list[tuple[float, str]] = []
        for symbol, rows_by_time in by_symbol_time.items():
            previous = rows_by_time.get(previous_timestamp)
            current = rows_by_time.get(timestamp)
            if previous is None or current is None or previous.close <= 0:
                continue
            score = current.close / previous.close - 1
            if score > 0:
                scored.append((score, symbol))
        if not scored:
            continue
        selected_symbol = max(scored)[1]
        selected_row = by_symbol_time[selected_symbol][timestamp]
        next_row = by_symbol_time[selected_symbol][next_timestamp]
        if selected_row.close <= 0:
            continue
        observations.append(
            _Observation(
                timestamp=timestamp,
                selected_symbol=selected_symbol,
                gross_return=next_row.close / selected_row.close - 1,
            )
        )
    return observations


def _cost_sensitivity(
    observations: list[_Observation],
    cost_bps_grid: list[float],
) -> list[CostSensitivityMetric]:
    if not observations:
        return []
    return [
        CostSensitivityMetric(
            cost_bps=cost_bps,
            gross_mean=_mean(row.gross_return for row in observations),
            net_mean=_mean(row.gross_return - cost_bps / 10_000 for row in observations),
            win_rate=_win_rate(
                row.gross_return - cost_bps / 10_000 for row in observations
            ),
        )
        for cost_bps in cost_bps_grid
    ]


def _walk_forward_metrics(
    observations: list[_Observation],
    *,
    split_count: int,
    cost_bps: float,
) -> list[CandidateSplitMetric]:
    test_size = len(observations) // (split_count + 1)
    if test_size <= 0:
        return []
    metrics: list[CandidateSplitMetric] = []
    first_test_start = len(observations) - test_size * split_count
    for split_index in range(split_count):
        start = first_test_start + split_index * test_size
        end = start + test_size
        test_rows = observations[start:end]
        if start <= 0 or not test_rows:
            continue
        gross_returns = [row.gross_return for row in test_rows]
        net_returns = [row.gross_return - cost_bps / 10_000 for row in test_rows]
        metrics.append(
            CandidateSplitMetric(
                split_index=split_index + 1,
                train_observations=start,
                test_observations=len(test_rows),
                test_start=test_rows[0].timestamp,
                test_end=test_rows[-1].timestamp,
                selected_symbol_counts=dict(Counter(row.selected_symbol for row in test_rows)),
                gross_mean=sum(gross_returns) / len(gross_returns),
                net_mean=sum(net_returns) / len(net_returns),
                win_rate=sum(1 for value in net_returns if value > 0) / len(net_returns),
            )
        )
    return metrics


def _return_metric(observations: list[_Observation], cost_bps: float) -> CostSensitivityMetric:
    return CostSensitivityMetric(
        cost_bps=cost_bps,
        gross_mean=_mean(row.gross_return for row in observations),
        net_mean=_mean(row.gross_return - cost_bps / 10_000 for row in observations),
        win_rate=_win_rate(row.gross_return - cost_bps / 10_000 for row in observations),
    )


def _has_universe_coverage_gap(universe: EvidenceUniverseReport, screen_result) -> bool:
    if {
        "missing_market_history",
        "insufficient_history_window",
        "duplicate_timestamps",
        "timestamp_alignment_gap",
        "source_probe_required",
    } & set(universe.reason_codes):
        return True
    return bool(
        {
            "missing_required_records",
            "insufficient_history_window",
        }
        & set(screen_result.blocked_reasons)
    )


def _candidate_state_target(
    reason_codes: list[MultiHypothesisBlockedReason],
) -> CandidateStateTarget:
    if not reason_codes:
        return "feasibility_passed"
    if set(reason_codes) <= {"insufficient_universe_coverage"}:
        return "candidate"
    if set(reason_codes) <= {"insufficient_samples", "insufficient_walk_forward_splits"}:
        return "source_qualified"
    return "redesign_required"


def _turnover(observations: list[_Observation]) -> float:
    if len(observations) < 2:
        return 0.0
    transitions = sum(
        1
        for previous, current in zip(observations, observations[1:])
        if previous.selected_symbol != current.selected_symbol
    )
    return transitions / (len(observations) - 1)


def _market_rows_by_symbol(
    records: list[SourceRecord],
    symbols: list[str],
    timeframe: str,
    *,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> dict[str, list[_MarketRow]]:
    requested = {_exchange_symbol(symbol): symbol for symbol in symbols}
    rows: dict[str, list[_MarketRow]] = {symbol: [] for symbol in symbols}
    for record in records:
        if record.record_type != "market_candle":
            continue
        if record.source not in {"binance_public", "ccxt"}:
            continue
        if not _in_window(record.observed_at, evaluation_start, evaluation_end):
            continue
        payload = record.payload
        if payload.get("timeframe") != timeframe:
            continue
        symbol = requested.get(_exchange_symbol(str(payload.get("symbol", ""))))
        if symbol is None:
            continue
        rows[symbol].append(
            _MarketRow(
                symbol=symbol,
                timestamp=_aware(record.observed_at),
                close=float(payload["close"]),
            )
        )
    for symbol in symbols:
        rows[symbol] = sorted(rows[symbol], key=lambda row: row.timestamp)
    return rows


def _aligned_timestamps(market_by_symbol: dict[str, list[_MarketRow]]) -> list[datetime]:
    timestamp_sets = [
        {row.timestamp for row in rows}
        for rows in market_by_symbol.values()
        if rows
    ]
    if not timestamp_sets:
        return []
    return sorted(set.intersection(*timestamp_sets))


def _normalize_candidates(candidates: list[str] | None) -> list[CandidateScreenId]:
    catalog = candidate_screen_catalog()
    if not candidates:
        return list(catalog)
    normalized: list[CandidateScreenId] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in catalog:
            raise ValueError(f"unknown multi-hypothesis candidate: {candidate}")
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _normalize_cost_grid(cost_bps_grid: list[float] | None) -> list[float]:
    raw_grid = list(DEFAULT_COST_BPS_GRID if not cost_bps_grid else cost_bps_grid)
    normalized: list[float] = []
    for value in raw_grid:
        cost_bps = float(value)
        if not isfinite(cost_bps) or cost_bps < 0:
            raise ValueError("cost_bps_grid values must be non-negative finite numbers")
        if cost_bps not in normalized:
            normalized.append(cost_bps)
    if not normalized:
        raise ValueError("cost_bps_grid must contain at least one value")
    return normalized


def _baseline_cost_bps(cost_bps_grid: list[float]) -> float:
    if _BASELINE_COST_BPS in cost_bps_grid:
        return _BASELINE_COST_BPS
    return cost_bps_grid[0]


def _validate_min_split_count(min_split_count: int) -> None:
    if min_split_count < 1:
        raise ValueError("min_split_count must be at least 1")


def _load_records_read_only(db_path: str | Path) -> list[SourceRecord]:
    path = Path(db_path)
    if not path.exists():
        return []
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(
                """
                SELECT record_id, source, record_type, observed_at, payload_json
                FROM source_records
                ORDER BY observed_at, record_id
                """
            ).fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"cannot read multi-hypothesis records from {path}: {exc}") from exc
    return [
        SourceRecord(
            record_id=record_id,
            source=source,
            record_type=record_type,
            observed_at=datetime.fromisoformat(observed_at),
            payload=json.loads(payload_json),
        )
        for record_id, source, record_type, observed_at, payload_json in rows
    ]


def _in_window(
    timestamp: datetime,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> bool:
    observed_at = _aware(timestamp)
    if evaluation_start is not None and observed_at < _aware(evaluation_start):
        return False
    if evaluation_end is not None and observed_at >= _aware(evaluation_end):
        return False
    return True


def _mean(values) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized)


def _win_rate(values) -> float:
    materialized = list(values)
    return sum(1 for value in materialized if value > 0) / len(materialized)


def _format_optional_mean(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.8f}"


def _format_optional_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _exchange_symbol(symbol: str) -> str:
    return symbol.strip().upper().split(":", maxsplit=1)[0].replace("/", "")


def _dedupe_preserving_order(values) -> list:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
