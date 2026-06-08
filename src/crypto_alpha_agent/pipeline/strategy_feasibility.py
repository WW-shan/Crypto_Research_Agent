from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore

StrategyFeasibilityMode = Literal["large-liquid-momentum-regime"]
StrategyFeasibilityReadiness = Literal["feasible", "blocked"]

_DERIVATIVE_RECORD_TYPES = (
    "basis",
    "long_short_account_ratio",
    "premium_index_kline",
    "taker_buy_sell_volume",
)


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
    mode: StrategyFeasibilityMode
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


def build_large_liquid_momentum_feasibility_report(
    db_path: str | Path,
    *,
    symbols: list[str],
    timeframe: str,
    current_capital_usd: float,
    cost_bps: float = 10.0,
    min_split_count: int = 3,
) -> StrategyFeasibilityReport:
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
        split_metrics=[] if reason_codes else split_metrics,
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
