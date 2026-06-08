from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore

StrategyFeasibilityMode = Literal[
    "large-liquid-momentum-regime",
    "derivatives-conditioned-lab",
]
StrategyFeasibilityReadiness = Literal["feasible", "blocked"]
DerivativesLabCandidate = Literal[
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
]

_ALL_DERIVATIVES_LAB_CANDIDATES: tuple[DerivativesLabCandidate, ...] = (
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
)

_DERIVATIVE_RECORD_TYPES = (
    "basis",
    "long_short_account_ratio",
    "premium_index_kline",
    "taker_buy_sell_volume",
)
_DERIVATIVES_SIGNAL_LOOKBACK = 24


class _StrictFeasibilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SymbolFeasibility(_StrictFeasibilityModel):
    symbol: str
    records: int = Field(ge=0)
    aligned_records: int = Field(ge=0)
    duplicate_timestamps: int = Field(ge=0)
    blocked_reasons: list[str] = Field(default_factory=list)


class WalkForwardSplitMetric(_StrictFeasibilityModel):
    split_index: int = Field(ge=1)
    train_observations: int = Field(ge=0)
    test_observations: int = Field(ge=0)
    test_start: datetime
    test_end: datetime
    selected_symbol_counts: dict[str, int] = Field(default_factory=dict)
    gross_return_mean: float
    cost_adjusted_return_mean: float
    win_rate: float = Field(ge=0, le=1)


class StrategyFeasibilityReport(_StrictFeasibilityModel):
    command: Literal["strategy-feasibility"] = "strategy-feasibility"
    mode: Literal["large-liquid-momentum-regime"]
    generated_at: datetime
    timeframe: str
    symbols: list[str]
    current_capital_usd: float = Field(ge=0)
    readiness: StrategyFeasibilityReadiness
    reason_codes: list[str] = Field(default_factory=list)
    symbol_reports: list[SymbolFeasibility]
    split_metrics: list[WalkForwardSplitMetric] = Field(default_factory=list)
    derivatives_record_counts: dict[str, int]
    cost_bps: float = Field(ge=0)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class DerivativesCoverage(_StrictFeasibilityModel):
    symbol: str
    derivatives_symbol: str
    market_records: int = Field(ge=0)
    premium_index_kline_records: int = Field(ge=0)
    basis_records: int = Field(ge=0)
    long_short_account_ratio_records: int = Field(ge=0)
    taker_buy_sell_volume_records: int = Field(ge=0)
    aligned_records: int = Field(ge=0)
    duplicate_timestamps: int = Field(ge=0)
    blocked_reasons: list[str] = Field(default_factory=list)


class DerivativesCandidateMetric(_StrictFeasibilityModel):
    candidate: DerivativesLabCandidate
    readiness: StrategyFeasibilityReadiness
    reason_codes: list[str] = Field(default_factory=list)
    observations: int = Field(ge=0)
    selected_symbol_counts: dict[str, int] = Field(default_factory=dict)
    gross_return_mean: float | None = None
    cost_adjusted_return_mean: float | None = None
    win_rate: float | None = Field(default=None, ge=0, le=1)
    split_metrics: list[WalkForwardSplitMetric] = Field(default_factory=list)


class DerivativesConditionedLabReport(_StrictFeasibilityModel):
    command: Literal["strategy-feasibility"] = "strategy-feasibility"
    mode: Literal["derivatives-conditioned-lab"] = "derivatives-conditioned-lab"
    generated_at: datetime
    timeframe: str
    derivatives_period: str
    symbols: list[str]
    derivatives_symbols: dict[str, str]
    current_capital_usd: float = Field(ge=0)
    readiness: StrategyFeasibilityReadiness
    reason_codes: list[str] = Field(default_factory=list)
    coverage: list[DerivativesCoverage]
    candidate_metrics: list[DerivativesCandidateMetric]
    derivatives_record_counts: dict[str, int]
    cost_bps: float = Field(ge=0)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


@dataclass(frozen=True)
class _MarketRow:
    symbol: str
    timestamp: datetime
    close: float
    high: float
    volume: float


@dataclass(frozen=True)
class _Observation:
    timestamp: datetime
    selected_symbol: str
    gross_return: float
    cost_adjusted_return: float


@dataclass
class _DerivativesRow:
    symbol: str
    derivatives_symbol: str
    timestamp: datetime
    long_short_ratio: float | None = None
    taker_buy_sell_ratio: float | None = None
    premium_close: float | None = None
    basis_rate: float | None = None


@dataclass(frozen=True)
class _CandidateSignal:
    symbol: str
    score: float


def normalize_binance_usdm_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().split(":", maxsplit=1)[0]
    return normalized.replace("/", "")


def _validate_min_split_count(min_split_count: int) -> None:
    if min_split_count < 1:
        raise ValueError("min_split_count must be at least 1")


def build_large_liquid_momentum_feasibility_report(
    db_path: str | Path,
    *,
    symbols: list[str],
    timeframe: str,
    current_capital_usd: float,
    cost_bps: float = 10.0,
    min_split_count: int = 3,
) -> StrategyFeasibilityReport:
    _validate_min_split_count(min_split_count)
    normalized_symbols = _dedupe_preserving_order(symbols)
    records = ResearchDataStore(db_path).load_records()
    market_by_symbol = _market_rows_by_symbol(records, normalized_symbols, timeframe)
    derivative_counts = _derivative_record_counts(records)
    one_week_bars = _bars_for_days(timeframe, days=7)
    two_week_bars = _bars_for_days(timeframe, days=14)

    symbol_reports, duplicate_blocked = _symbol_reports(
        market_by_symbol,
        normalized_symbols,
        aligned_records=0,
    )
    reason_codes: list[str] = []
    if duplicate_blocked:
        reason_codes.append("duplicate_timestamps")

    aligned_timestamps = _aligned_timestamps(market_by_symbol, normalized_symbols)
    if symbol_reports:
        symbol_reports = [
            report.model_copy(update={"aligned_records": len(aligned_timestamps)})
            for report in symbol_reports
        ]

    min_required_rows = two_week_bars + min_split_count + 1
    if len(aligned_timestamps) < min_required_rows:
        reason_codes.append("insufficient_aligned_history")
        symbol_reports = _append_symbol_reason(
            symbol_reports,
            "insufficient_aligned_history",
        )

    split_metrics: list[WalkForwardSplitMetric] = []
    if not reason_codes:
        observations = _momentum_observations(
            market_by_symbol,
            aligned_timestamps,
            normalized_symbols,
            one_week_bars=one_week_bars,
            two_week_bars=two_week_bars,
            cost_bps=cost_bps,
        )
        if len(observations) < min_split_count * 2:
            reason_codes.append("insufficient_aligned_history")
        else:
            split_metrics = _walk_forward_metrics(observations, split_count=min_split_count)
            if len(split_metrics) < min_split_count:
                reason_codes.append("insufficient_walk_forward_splits")
            elif any(metric.cost_adjusted_return_mean <= 0 for metric in split_metrics):
                reason_codes.append("non_positive_cost_adjusted_expectancy")

    reason_codes = _dedupe_preserving_order(reason_codes)
    return StrategyFeasibilityReport(
        mode="large-liquid-momentum-regime",
        generated_at=datetime.now(tz=UTC),
        timeframe=timeframe,
        symbols=normalized_symbols,
        current_capital_usd=current_capital_usd,
        readiness="blocked" if reason_codes else "feasible",
        reason_codes=reason_codes,
        symbol_reports=symbol_reports,
        split_metrics=split_metrics,
        derivatives_record_counts=derivative_counts,
        cost_bps=cost_bps,
        uses_real_capital=False,
        live_order_routing=False,
    )


def build_derivatives_conditioned_lab_report(
    db_path: str | Path,
    *,
    symbols: list[str],
    timeframe: str,
    current_capital_usd: float,
    derivatives_symbols: dict[str, str] | None = None,
    derivatives_period: str = "1h",
    candidates: list[DerivativesLabCandidate] | None = None,
    cost_bps: float = 10.0,
    min_split_count: int = 3,
) -> DerivativesConditionedLabReport:
    _validate_min_split_count(min_split_count)
    normalized_symbols = _dedupe_preserving_order(symbols)
    normalized_derivatives_symbols = _normalize_derivatives_symbol_map(
        normalized_symbols,
        derivatives_symbols,
    )
    normalized_candidates = _normalize_derivatives_candidates(candidates)

    records = ResearchDataStore(db_path).load_records()
    market_by_symbol = _market_rows_by_symbol(records, normalized_symbols, timeframe)
    derivative_counts = _derivative_record_counts(records)
    ambiguous_symbols = _ambiguous_derivatives_mapping_symbols(
        normalized_symbols,
        normalized_derivatives_symbols,
    )
    derivatives_by_symbol, derivative_duplicate_counts = _derivatives_rows_by_symbol(
        records,
        normalized_symbols,
        normalized_derivatives_symbols,
        derivatives_period,
    )
    coverage, duplicate_blocked = _derivatives_coverage(
        market_by_symbol,
        derivatives_by_symbol,
        normalized_symbols,
        normalized_derivatives_symbols,
        derivative_duplicate_counts,
        ambiguous_symbols,
    )

    pre_evaluation_reasons: list[str] = []
    if ambiguous_symbols:
        pre_evaluation_reasons.append("ambiguous_derivatives_symbol_mapping")
    if duplicate_blocked:
        pre_evaluation_reasons.append("duplicate_timestamps")

    if pre_evaluation_reasons:
        reason_codes = pre_evaluation_reasons
        candidate_metrics = [
            _blocked_derivatives_candidate_metric(candidate, reason_codes)
            for candidate in normalized_candidates
        ]
    else:
        aligned_timestamps = _aligned_timestamps(market_by_symbol, normalized_symbols)
        candidate_metrics = [
            _derivatives_candidate_metric(
                candidate,
                market_by_symbol,
                derivatives_by_symbol,
                aligned_timestamps,
                normalized_symbols,
                cost_bps=cost_bps,
                min_split_count=min_split_count,
            )
            for candidate in normalized_candidates
        ]
        feasible_candidates = [
            metric for metric in candidate_metrics if metric.readiness == "feasible"
        ]
        if feasible_candidates:
            reason_codes = []
        else:
            reason_codes = _dedupe_preserving_order(
                [
                    reason
                    for metric in candidate_metrics
                    for reason in metric.reason_codes
                ]
            )

    return DerivativesConditionedLabReport(
        generated_at=datetime.now(tz=UTC),
        timeframe=timeframe,
        derivatives_period=derivatives_period,
        symbols=normalized_symbols,
        derivatives_symbols=normalized_derivatives_symbols,
        current_capital_usd=current_capital_usd,
        readiness="blocked" if reason_codes else "feasible",
        reason_codes=reason_codes,
        coverage=coverage,
        candidate_metrics=candidate_metrics,
        derivatives_record_counts=derivative_counts,
        cost_bps=cost_bps,
        uses_real_capital=False,
        live_order_routing=False,
    )


def render_strategy_feasibility_markdown(report: StrategyFeasibilityReport) -> str:
    lines = [
        "# Large Liquid Momentum Feasibility",
        "",
        "## Safety",
        f"Real capital: {str(report.uses_real_capital).lower()}",
        f"Live order routing: {str(report.live_order_routing).lower()}",
        "",
        "## Decision",
        f"Readiness: {report.readiness}",
        f"Reason codes: {', '.join(report.reason_codes) or 'none'}",
        "",
        "## Symbols",
        "| Symbol | Records | Aligned records | Duplicate timestamps | Blocked reasons |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for symbol in report.symbol_reports:
        lines.append(
            "| "
            + " | ".join(
                [
                    symbol.symbol,
                    f"{symbol.records:g}",
                    f"{symbol.aligned_records:g}",
                    f"{symbol.duplicate_timestamps:g}",
                    ", ".join(symbol.blocked_reasons) or "none",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Walk Forward",
            "| Split | Train observations | Test observations | Test start | Test end | Net mean | Win rate |",
            "| ---: | ---: | ---: | --- | --- | ---: | ---: |",
        ]
    )
    if report.split_metrics:
        for metric in report.split_metrics:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"{metric.split_index:g}",
                        f"{metric.train_observations:g}",
                        f"{metric.test_observations:g}",
                        metric.test_start.isoformat(),
                        metric.test_end.isoformat(),
                        f"{metric.cost_adjusted_return_mean:.8f}",
                        f"{metric.win_rate:.4f}",
                    ]
                )
                + " |"
            )
    else:
        lines.append("| 0 | 0 | 0 | n/a | n/a | 0 | 0 |")
    lines.extend(
        [
            "",
            "## Derivatives Context",
            "| Record type | Count |",
            "| --- | ---: |",
        ]
    )
    for record_type, count in sorted(report.derivatives_record_counts.items()):
        lines.append(f"| {record_type} | {count:g} |")
    return "\n".join(lines) + "\n"


def _normalize_derivatives_symbol_map(
    symbols: list[str],
    derivatives_symbols: dict[str, str] | None,
) -> dict[str, str]:
    requested_derivatives_symbols = derivatives_symbols or {}
    return {
        symbol: normalize_binance_usdm_symbol(
            requested_derivatives_symbols.get(symbol, symbol)
        )
        for symbol in symbols
    }


def _ambiguous_derivatives_mapping_symbols(
    symbols: list[str],
    derivatives_symbols: dict[str, str],
) -> set[str]:
    derivative_symbol_counts = Counter(derivatives_symbols[symbol] for symbol in symbols)
    return {
        symbol
        for symbol in symbols
        if derivative_symbol_counts[derivatives_symbols[symbol]] > 1
    }


def _normalize_derivatives_candidates(
    candidates: list[DerivativesLabCandidate] | None,
) -> list[DerivativesLabCandidate]:
    if not candidates:
        return list(_ALL_DERIVATIVES_LAB_CANDIDATES)

    seen: set[DerivativesLabCandidate] = set()
    deduped: list[DerivativesLabCandidate] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _derivatives_rows_by_symbol(
    records: list[SourceRecord],
    symbols: list[str],
    derivatives_symbols: dict[str, str],
    derivatives_period: str,
) -> tuple[dict[str, list[_DerivativesRow]], dict[str, int]]:
    source_symbols: dict[str, list[str]] = defaultdict(list)
    for symbol in symbols:
        source_symbols[derivatives_symbols[symbol]].append(symbol)

    merged_rows: dict[tuple[str, datetime], _DerivativesRow] = {}
    duplicate_key_counts: Counter[tuple[str, datetime, str]] = Counter()
    for record in records:
        source_symbol = _derivatives_record_source_symbol(record, derivatives_period)
        if source_symbol is None or source_symbol not in source_symbols:
            continue

        duplicate_key_counts[(source_symbol, record.observed_at, record.record_type)] += 1
        key = (source_symbol, record.observed_at)
        row = merged_rows.get(key)
        if row is None:
            row = _DerivativesRow(
                symbol=source_symbols[source_symbol][0],
                derivatives_symbol=source_symbol,
                timestamp=record.observed_at,
            )
            merged_rows[key] = row
        _merge_derivatives_record(row, record)

    rows_by_symbol: dict[str, list[_DerivativesRow]] = defaultdict(list)
    for row in merged_rows.values():
        for symbol in source_symbols[row.derivatives_symbol]:
            rows_by_symbol[symbol].append(
                _DerivativesRow(
                    symbol=symbol,
                    derivatives_symbol=row.derivatives_symbol,
                    timestamp=row.timestamp,
                    long_short_ratio=row.long_short_ratio,
                    taker_buy_sell_ratio=row.taker_buy_sell_ratio,
                    premium_close=row.premium_close,
                    basis_rate=row.basis_rate,
                )
            )

    for symbol in symbols:
        rows_by_symbol[symbol] = sorted(
            rows_by_symbol[symbol],
            key=lambda derivative_row: derivative_row.timestamp,
        )

    duplicate_counts_by_symbol: dict[str, int] = defaultdict(int)
    for (
        source_symbol,
        _timestamp,
        _record_type,
    ), count in duplicate_key_counts.items():
        if count <= 1:
            continue
        for symbol in source_symbols[source_symbol]:
            duplicate_counts_by_symbol[symbol] += count - 1
    return rows_by_symbol, duplicate_counts_by_symbol


def _derivatives_record_source_symbol(
    record: SourceRecord,
    derivatives_period: str,
) -> str | None:
    payload = record.payload
    if record.record_type == "long_short_account_ratio":
        if payload.get("period") != derivatives_period:
            return None
        return normalize_binance_usdm_symbol(str(payload.get("symbol") or ""))
    if record.record_type == "taker_buy_sell_volume":
        if payload.get("period") != derivatives_period:
            return None
        return normalize_binance_usdm_symbol(str(payload.get("symbol") or ""))
    if record.record_type == "premium_index_kline":
        if payload.get("interval") != derivatives_period:
            return None
        return normalize_binance_usdm_symbol(str(payload.get("symbol") or ""))
    if record.record_type == "basis":
        if payload.get("period") != derivatives_period:
            return None
        if payload.get("contract_type") != "PERPETUAL":
            return None
        return normalize_binance_usdm_symbol(str(payload.get("pair") or ""))
    return None


def _merge_derivatives_record(row: _DerivativesRow, record: SourceRecord) -> None:
    payload = record.payload
    if record.record_type == "long_short_account_ratio":
        value = payload.get("long_short_ratio")
        if value is not None:
            row.long_short_ratio = float(value)
    elif record.record_type == "taker_buy_sell_volume":
        value = payload.get("buy_sell_ratio")
        if value is not None:
            row.taker_buy_sell_ratio = float(value)
    elif record.record_type == "premium_index_kline":
        value = payload.get("close")
        if value is not None:
            row.premium_close = float(value)
    elif record.record_type == "basis":
        value = payload.get("basis_rate")
        if value is not None:
            row.basis_rate = float(value)


def _derivatives_coverage(
    market_by_symbol: dict[str, list[_MarketRow]],
    derivatives_by_symbol: dict[str, list[_DerivativesRow]],
    symbols: list[str],
    derivatives_symbols: dict[str, str],
    derivative_duplicate_counts: dict[str, int],
    ambiguous_symbols: set[str],
) -> tuple[list[DerivativesCoverage], bool]:
    coverage: list[DerivativesCoverage] = []
    has_duplicates = False
    for symbol in symbols:
        market_rows = market_by_symbol.get(symbol, [])
        derivative_rows = derivatives_by_symbol.get(symbol, [])
        timestamp_counts = Counter(row.timestamp for row in market_rows)
        market_duplicate_timestamps = sum(
            count - 1 for count in timestamp_counts.values() if count > 1
        )
        duplicate_timestamps = (
            market_duplicate_timestamps + derivative_duplicate_counts.get(symbol, 0)
        )
        market_timestamps = set(timestamp_counts)
        derivative_timestamps = {row.timestamp for row in derivative_rows}
        aligned_records = len(market_timestamps & derivative_timestamps)

        blocked_reasons = []
        if not market_rows:
            blocked_reasons.append("missing_market_candles")
        if aligned_records < _DERIVATIVES_SIGNAL_LOOKBACK + 2:
            blocked_reasons.append("insufficient_derivatives_history")
        if duplicate_timestamps:
            has_duplicates = True
            blocked_reasons.append("duplicate_timestamps")
        if symbol in ambiguous_symbols:
            blocked_reasons.append("ambiguous_derivatives_symbol_mapping")

        coverage.append(
            DerivativesCoverage(
                symbol=symbol,
                derivatives_symbol=derivatives_symbols[symbol],
                market_records=len(market_rows),
                premium_index_kline_records=sum(
                    1 for row in derivative_rows if row.premium_close is not None
                ),
                basis_records=sum(
                    1 for row in derivative_rows if row.basis_rate is not None
                ),
                long_short_account_ratio_records=sum(
                    1 for row in derivative_rows if row.long_short_ratio is not None
                ),
                taker_buy_sell_volume_records=sum(
                    1
                    for row in derivative_rows
                    if row.taker_buy_sell_ratio is not None
                ),
                aligned_records=aligned_records,
                duplicate_timestamps=duplicate_timestamps,
                blocked_reasons=blocked_reasons,
            )
        )
    return coverage, has_duplicates


def _blocked_derivatives_candidate_metric(
    candidate: DerivativesLabCandidate,
    reason_codes: list[str],
) -> DerivativesCandidateMetric:
    return DerivativesCandidateMetric(
        candidate=candidate,
        readiness="blocked",
        reason_codes=_dedupe_preserving_order(reason_codes),
        observations=0,
        selected_symbol_counts={},
        gross_return_mean=None,
        cost_adjusted_return_mean=None,
        win_rate=None,
        split_metrics=[],
    )


def _derivatives_candidate_metric(
    candidate: DerivativesLabCandidate,
    market_by_symbol: dict[str, list[_MarketRow]],
    derivatives_by_symbol: dict[str, list[_DerivativesRow]],
    aligned_timestamps: list[datetime],
    symbols: list[str],
    *,
    cost_bps: float,
    min_split_count: int,
) -> DerivativesCandidateMetric:
    observations = _derivatives_candidate_observations(
        candidate,
        market_by_symbol,
        derivatives_by_symbol,
        aligned_timestamps,
        symbols,
        cost_bps=cost_bps,
    )
    if not observations:
        return _blocked_derivatives_candidate_metric(
            candidate,
            ["insufficient_derivatives_history"],
        )

    split_metrics = _walk_forward_metrics(observations, split_count=min_split_count)
    reason_codes: list[str] = []
    if len(observations) < min_split_count * 2 or len(split_metrics) < min_split_count:
        reason_codes.append("insufficient_walk_forward_splits")
    elif any(metric.cost_adjusted_return_mean <= 0 for metric in split_metrics):
        reason_codes.append("non_positive_cost_adjusted_expectancy")

    gross_returns = [row.gross_return for row in observations]
    net_returns = [row.cost_adjusted_return for row in observations]
    return DerivativesCandidateMetric(
        candidate=candidate,
        readiness="blocked" if reason_codes else "feasible",
        reason_codes=reason_codes,
        observations=len(observations),
        selected_symbol_counts=dict(Counter(row.selected_symbol for row in observations)),
        gross_return_mean=sum(gross_returns) / len(gross_returns),
        cost_adjusted_return_mean=sum(net_returns) / len(net_returns),
        win_rate=sum(1 for value in net_returns if value > 0) / len(net_returns),
        split_metrics=split_metrics,
    )


def _derivatives_candidate_observations(
    candidate: DerivativesLabCandidate,
    market_by_symbol: dict[str, list[_MarketRow]],
    derivatives_by_symbol: dict[str, list[_DerivativesRow]],
    aligned_timestamps: list[datetime],
    symbols: list[str],
    *,
    cost_bps: float,
) -> list[_Observation]:
    market_by_symbol_time = {
        symbol: {row.timestamp: row for row in market_by_symbol.get(symbol, [])}
        for symbol in symbols
    }
    derivatives_by_symbol_time = {
        symbol: {row.timestamp: row for row in derivatives_by_symbol.get(symbol, [])}
        for symbol in symbols
    }
    observations: list[_Observation] = []
    round_trip_cost = cost_bps / 10_000

    for index in range(_DERIVATIVES_SIGNAL_LOOKBACK, len(aligned_timestamps) - 1):
        timestamp = aligned_timestamps[index]
        previous_timestamp = aligned_timestamps[index - _DERIVATIVES_SIGNAL_LOOKBACK]
        next_timestamp = aligned_timestamps[index + 1]
        signals: list[_CandidateSignal] = []
        for symbol in symbols:
            current_row = market_by_symbol_time[symbol].get(timestamp)
            previous_row = market_by_symbol_time[symbol].get(previous_timestamp)
            derivative_row = derivatives_by_symbol_time[symbol].get(timestamp)
            if (
                current_row is None
                or previous_row is None
                or derivative_row is None
            ):
                continue
            signal = _derivatives_candidate_signal(
                candidate,
                symbol,
                current_row,
                previous_row,
                derivative_row,
            )
            if signal is not None:
                signals.append(signal)

        if not signals:
            continue
        # Equal scores intentionally preserve requested symbol order.
        selected_signal = max(signals, key=lambda signal: abs(signal.score))
        if selected_signal.score == 0:
            continue

        selected_row = market_by_symbol_time[selected_signal.symbol][timestamp]
        next_row = market_by_symbol_time[selected_signal.symbol][next_timestamp]
        price_return = next_row.close / selected_row.close - 1
        direction = 1.0 if selected_signal.score > 0 else -1.0
        gross_return = direction * price_return
        observations.append(
            _Observation(
                timestamp=timestamp,
                selected_symbol=selected_signal.symbol,
                gross_return=gross_return,
                cost_adjusted_return=gross_return - round_trip_cost,
            )
        )
    return observations


def _derivatives_candidate_signal(
    candidate: DerivativesLabCandidate,
    symbol: str,
    current_row: _MarketRow,
    previous_row: _MarketRow,
    derivative_row: _DerivativesRow,
) -> _CandidateSignal | None:
    if candidate == "long_short_crowding_contrarian":
        if derivative_row.long_short_ratio is None:
            return None
        return _CandidateSignal(symbol=symbol, score=1.0 - derivative_row.long_short_ratio)

    if candidate == "taker_imbalance_reversal":
        if derivative_row.taker_buy_sell_ratio is None:
            return None
        return _CandidateSignal(
            symbol=symbol,
            score=1.0 - derivative_row.taker_buy_sell_ratio,
        )

    momentum = _market_momentum(current_row, previous_row)
    if candidate == "premium_basis_risk_filter":
        if derivative_row.premium_close is None or derivative_row.basis_rate is None:
            return None
        if abs(derivative_row.premium_close) > 0.001:
            return _CandidateSignal(symbol=symbol, score=0.0)
        if abs(derivative_row.basis_rate) > 0.002:
            return _CandidateSignal(symbol=symbol, score=0.0)
        return _CandidateSignal(symbol=symbol, score=momentum)

    if candidate == "momentum_derivatives_confirmation":
        if (
            derivative_row.taker_buy_sell_ratio is None
            or derivative_row.long_short_ratio is None
        ):
            return None
        if momentum == 0:
            return _CandidateSignal(symbol=symbol, score=0.0)
        taker_delta = derivative_row.taker_buy_sell_ratio - 1.0
        if momentum > 0 and taker_delta <= 0:
            return _CandidateSignal(symbol=symbol, score=0.0)
        if momentum < 0 and taker_delta >= 0:
            return _CandidateSignal(symbol=symbol, score=0.0)
        if abs(derivative_row.long_short_ratio - 1.0) > 0.75:
            return _CandidateSignal(symbol=symbol, score=0.0)
        return _CandidateSignal(symbol=symbol, score=momentum)

    return None


def _market_momentum(current_row: _MarketRow, previous_row: _MarketRow) -> float:
    if previous_row.close <= 0:
        return 0.0
    return current_row.close / previous_row.close - 1


def _market_rows_by_symbol(
    records: list[SourceRecord],
    symbols: list[str],
    timeframe: str,
) -> dict[str, list[_MarketRow]]:
    requested = set(symbols)
    rows: dict[str, list[_MarketRow]] = defaultdict(list)
    for record in records:
        if record.record_type != "market_candle":
            continue
        symbol = str(record.payload.get("symbol") or "")
        if symbol not in requested or record.payload.get("timeframe") != timeframe:
            continue
        rows[symbol].append(
            _MarketRow(
                symbol=symbol,
                timestamp=record.observed_at,
                close=float(record.payload["close"]),
                high=float(record.payload["high"]),
                volume=float(record.payload.get("volume") or 0.0),
            )
        )
    for symbol in symbols:
        rows[symbol] = sorted(rows[symbol], key=lambda row: row.timestamp)
    return rows


def _symbol_reports(
    market_by_symbol: dict[str, list[_MarketRow]],
    symbols: list[str],
    *,
    aligned_records: int,
) -> tuple[list[SymbolFeasibility], bool]:
    reports: list[SymbolFeasibility] = []
    has_duplicates = False
    for symbol in symbols:
        rows = market_by_symbol.get(symbol, [])
        timestamp_counts = Counter(row.timestamp for row in rows)
        duplicate_timestamps = sum(count - 1 for count in timestamp_counts.values() if count > 1)
        blocked_reasons = []
        if not rows:
            blocked_reasons.append("missing_market_candles")
        if duplicate_timestamps:
            has_duplicates = True
            blocked_reasons.append("duplicate_timestamps")
        reports.append(
            SymbolFeasibility(
                symbol=symbol,
                records=len(rows),
                aligned_records=aligned_records,
                duplicate_timestamps=duplicate_timestamps,
                blocked_reasons=blocked_reasons,
            )
        )
    return reports, has_duplicates


def _aligned_timestamps(
    market_by_symbol: dict[str, list[_MarketRow]],
    symbols: list[str],
) -> list[datetime]:
    timestamp_sets = [
        {row.timestamp for row in market_by_symbol.get(symbol, [])}
        for symbol in symbols
    ]
    if not timestamp_sets:
        return []
    return sorted(set.intersection(*timestamp_sets))


def _momentum_observations(
    market_by_symbol: dict[str, list[_MarketRow]],
    aligned_timestamps: list[datetime],
    symbols: list[str],
    *,
    one_week_bars: int,
    two_week_bars: int,
    cost_bps: float,
) -> list[_Observation]:
    by_symbol_time = {
        symbol: {row.timestamp: row for row in market_by_symbol[symbol]}
        for symbol in symbols
    }
    observations: list[_Observation] = []
    round_trip_cost = cost_bps / 10_000
    for index in range(two_week_bars, len(aligned_timestamps) - 1):
        timestamp = aligned_timestamps[index]
        next_timestamp = aligned_timestamps[index + 1]
        scored: list[tuple[float, str]] = []
        for symbol in symbols:
            row = by_symbol_time[symbol][timestamp]
            one_week_row = by_symbol_time[symbol][aligned_timestamps[index - one_week_bars]]
            two_week_row = by_symbol_time[symbol][aligned_timestamps[index - two_week_bars]]
            high_window = [
                by_symbol_time[symbol][aligned_timestamps[window_index]].high
                for window_index in range(index - one_week_bars + 1, index + 1)
            ]
            return_1w = row.close / one_week_row.close - 1
            return_2w = row.close / two_week_row.close - 1
            recent_high_distance = row.close / max(high_window) - 1
            liquidity_guard = 1.0 if row.volume > 0 else -1.0
            score = return_2w + 0.5 * return_1w + 0.1 * recent_high_distance + liquidity_guard
            scored.append((score, symbol))
        selected_symbol = max(scored)[1]
        selected_row = by_symbol_time[selected_symbol][timestamp]
        next_row = by_symbol_time[selected_symbol][next_timestamp]
        gross_return = next_row.close / selected_row.close - 1
        observations.append(
            _Observation(
                timestamp=timestamp,
                selected_symbol=selected_symbol,
                gross_return=gross_return,
                cost_adjusted_return=gross_return - round_trip_cost,
            )
        )
    return observations


def _walk_forward_metrics(
    observations: list[_Observation],
    *,
    split_count: int,
) -> list[WalkForwardSplitMetric]:
    test_size = len(observations) // (split_count + 1)
    if test_size <= 0:
        return []
    metrics: list[WalkForwardSplitMetric] = []
    first_test_start = len(observations) - test_size * split_count
    for split_index in range(split_count):
        start = first_test_start + split_index * test_size
        end = start + test_size
        test_rows = observations[start:end]
        if start <= 0 or not test_rows:
            continue
        gross_returns = [row.gross_return for row in test_rows]
        net_returns = [row.cost_adjusted_return for row in test_rows]
        metrics.append(
            WalkForwardSplitMetric(
                split_index=split_index + 1,
                train_observations=start,
                test_observations=len(test_rows),
                test_start=test_rows[0].timestamp,
                test_end=test_rows[-1].timestamp,
                selected_symbol_counts=dict(Counter(row.selected_symbol for row in test_rows)),
                gross_return_mean=sum(gross_returns) / len(gross_returns),
                cost_adjusted_return_mean=sum(net_returns) / len(net_returns),
                win_rate=sum(1 for value in net_returns if value > 0) / len(net_returns),
            )
        )
    return metrics


def _derivative_record_counts(records: list[SourceRecord]) -> dict[str, int]:
    counts = Counter(record.record_type for record in records)
    return {record_type: counts.get(record_type, 0) for record_type in _DERIVATIVE_RECORD_TYPES}


def _bars_for_days(timeframe: str, *, days: int) -> int:
    if timeframe.endswith("h") and timeframe[:-1].isdigit():
        hours = int(timeframe[:-1])
        return max(1, days * 24 // hours)
    if timeframe.endswith("d") and timeframe[:-1].isdigit():
        day_count = int(timeframe[:-1])
        return max(1, days // day_count)
    return days * 24


def _append_symbol_reason(
    reports: list[SymbolFeasibility],
    reason: str,
) -> list[SymbolFeasibility]:
    return [
        report.model_copy(
            update={"blocked_reasons": _dedupe_preserving_order([*report.blocked_reasons, reason])}
        )
        for report in reports
    ]


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
