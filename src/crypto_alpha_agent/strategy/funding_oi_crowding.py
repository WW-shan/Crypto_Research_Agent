from __future__ import annotations

import json
import math
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from crypto_alpha_agent.data.models import OpenInterestRecord, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.strategy.models import StrategyValidationReport
from crypto_alpha_agent.validation.funding_price import (
    FundingPriceTrade,
    extract_funding_price_trades_from_records,
    validate_funding_price_confirmation_from_records,
)
from crypto_alpha_agent.validation.gates import evaluate_walk_forward_gate
from crypto_alpha_agent.validation.walk_forward import generate_walk_forward_windows

STRATEGY_FAMILY = "funding_open_interest_crowding"
VALIDATOR_NAME = "funding_oi_crowding"


@dataclass(frozen=True, slots=True)
class _OiFilterResult:
    trades: list[FundingPriceTrade]
    insufficient_history_count: int
    non_positive_open_interest_count: int
    no_expansion_count: int
    open_interest_changes: list[float]


def validate_funding_oi_crowding(
    db_path: str | Path,
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    open_interest_symbol: str | None = None,
    open_interest_timeframe: str | None = None,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
    min_open_interest_change_pct: float = 0.05,
    open_interest_lookback_bars: int = 1,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    min_trades: int = 3,
    require_walk_forward: bool = True,
    walk_forward_train_size: int = 24,
    walk_forward_test_size: int = 8,
    walk_forward_min_splits: int = 3,
    walk_forward_min_pass_rate: float = 1.0,
    max_drawdown_limit: float = 0.20,
    now: datetime | None = None,
    max_age_hours: float | None = None,
    supported_price_symbols: Sequence[str] | None = ("BTC/USDT",),
    supported_funding_symbols: Sequence[str] | None = ("BTC/USDT:USDT",),
    supported_open_interest_symbols: Sequence[str] | None = ("BTC/USDT:USDT",),
) -> StrategyValidationReport:
    records = tuple(
        record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records()
    )
    return validate_funding_oi_crowding_from_records(
        records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        open_interest_symbol=open_interest_symbol,
        open_interest_timeframe=open_interest_timeframe,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
        min_open_interest_change_pct=min_open_interest_change_pct,
        open_interest_lookback_bars=open_interest_lookback_bars,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        min_trades=min_trades,
        require_walk_forward=require_walk_forward,
        walk_forward_train_size=walk_forward_train_size,
        walk_forward_test_size=walk_forward_test_size,
        walk_forward_min_splits=walk_forward_min_splits,
        walk_forward_min_pass_rate=walk_forward_min_pass_rate,
        max_drawdown_limit=max_drawdown_limit,
        now=now,
        max_age_hours=max_age_hours,
        supported_price_symbols=supported_price_symbols,
        supported_funding_symbols=supported_funding_symbols,
        supported_open_interest_symbols=supported_open_interest_symbols,
    )


def validate_funding_oi_crowding_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    open_interest_symbol: str | None = None,
    open_interest_timeframe: str | None = None,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
    min_open_interest_change_pct: float = 0.05,
    open_interest_lookback_bars: int = 1,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    min_trades: int = 3,
    require_walk_forward: bool = True,
    walk_forward_train_size: int = 24,
    walk_forward_test_size: int = 8,
    walk_forward_min_splits: int = 3,
    walk_forward_min_pass_rate: float = 1.0,
    max_drawdown_limit: float = 0.20,
    now: datetime | None = None,
    max_age_hours: float | None = None,
    supported_price_symbols: Sequence[str] | None = ("BTC/USDT",),
    supported_funding_symbols: Sequence[str] | None = ("BTC/USDT:USDT",),
    supported_open_interest_symbols: Sequence[str] | None = ("BTC/USDT:USDT",),
) -> StrategyValidationReport:
    _validate_parameters(
        min_open_interest_change_pct=min_open_interest_change_pct,
        open_interest_lookback_bars=open_interest_lookback_bars,
        min_trades=min_trades,
    )
    oi_symbol = _nonblank(open_interest_symbol) or funding_symbol
    oi_timeframe = _nonblank(open_interest_timeframe) or timeframe
    normalized_supported_open_interest_symbols = _normalize_supported_symbols(
        supported_open_interest_symbols,
        "supported_open_interest_symbols",
    )
    unsupported_open_interest_symbol = (
        normalized_supported_open_interest_symbols is not None
        and oi_symbol not in normalized_supported_open_interest_symbols
    )
    base_result = validate_funding_price_confirmation_from_records(
        records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        min_trades=0,
        require_walk_forward=False,
        max_drawdown_limit=max_drawdown_limit,
        now=now,
        max_age_hours=max_age_hours,
        supported_price_symbols=supported_price_symbols,
        supported_funding_symbols=supported_funding_symbols,
    )
    open_interest = _open_interest_history_from_records(
        records,
        symbol=oi_symbol,
        timeframe=oi_timeframe,
    )
    duplicate_open_interest_timestamp = _has_duplicate_open_interest_timestamps(
        open_interest
    )
    if duplicate_open_interest_timestamp:
        filter_result = _OiFilterResult([], 0, 0, 0, [])
    else:
        all_trades = extract_funding_price_trades_from_records(
            records,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            threshold_abs=threshold_abs,
            hold_bars=hold_bars,
        )
        filter_result = _filter_open_interest_confirmed_trades(
            all_trades,
            open_interest,
            min_open_interest_change_pct=min_open_interest_change_pct,
            open_interest_lookback_bars=open_interest_lookback_bars,
        )

    raw_returns = [trade.raw_return for trade in filter_result.trades]
    cost_per_trade = (float(fee_rate) + float(slippage_rate)) * 2.0
    fee_cost_per_trade = float(fee_rate) * 2.0
    adjusted_returns = [trade_return - cost_per_trade for trade_return in raw_returns]
    gross_expectancy = math.fsum(raw_returns) / len(raw_returns) if raw_returns else 0.0
    fee_adjusted_expectancy = (
        math.fsum(trade_return - fee_cost_per_trade for trade_return in raw_returns)
        / len(raw_returns)
        if raw_returns
        else 0.0
    )
    slippage_adjusted_expectancy = (
        math.fsum(adjusted_returns) / len(adjusted_returns) if adjusted_returns else 0.0
    )
    net_return, max_drawdown = _cumulative_return_and_drawdown(adjusted_returns)
    walk_forward_split_count = 0
    walk_forward_pass_rate = 0.0
    walk_forward_blocked_reasons: list[str] = []
    if require_walk_forward:
        walk_forward_expectancies = _walk_forward_adjusted_expectancies(
            total_bars=base_result.bar_count,
            trades=[
                (trade.entry_index, trade.exit_index, trade.raw_return)
                for trade in filter_result.trades
            ],
            cost_per_trade=cost_per_trade,
            train_size=walk_forward_train_size,
            test_size=walk_forward_test_size,
        )
        walk_forward_gate = evaluate_walk_forward_gate(
            walk_forward_expectancies,
            min_splits=walk_forward_min_splits,
            min_pass_rate=walk_forward_min_pass_rate,
        )
        walk_forward_split_count = walk_forward_gate.split_count
        walk_forward_pass_rate = walk_forward_gate.pass_rate
        walk_forward_blocked_reasons = walk_forward_gate.blocked_reasons

    blocked_reasons = _blocked_reasons(
        base_blocked_reasons=base_result.blocked_reasons,
        open_interest_sample_count=len(open_interest),
        duplicate_open_interest_timestamp=duplicate_open_interest_timestamp,
        insufficient_history_count=filter_result.insufficient_history_count,
        non_positive_open_interest_count=filter_result.non_positive_open_interest_count,
        no_expansion_count=filter_result.no_expansion_count,
        trade_count=len(raw_returns),
        min_trades=min_trades,
        expectancy=slippage_adjusted_expectancy,
        net_return=net_return,
        max_drawdown=max_drawdown,
        max_drawdown_limit=max_drawdown_limit,
        unsupported_open_interest_symbol=unsupported_open_interest_symbol,
        stale_open_interest=_is_stale_open_interest(
            open_interest,
            now=now,
            max_age_hours=max_age_hours,
        ),
        walk_forward_blocked_reasons=walk_forward_blocked_reasons,
    )

    return StrategyValidationReport(
        strategy_family=STRATEGY_FAMILY,
        validator_name=VALIDATOR_NAME,
        approved=not blocked_reasons,
        blocked_reasons=blocked_reasons,
        metrics={
            "symbol": price_symbol,
            "funding_symbol": funding_symbol,
            "open_interest_symbol": oi_symbol,
            "timeframe": timeframe,
            "open_interest_timeframe": oi_timeframe,
            "bar_count": base_result.bar_count,
            "funding_sample_count": base_result.funding_sample_count,
            "open_interest_sample_count": len(open_interest),
            "extreme_count": base_result.extreme_count,
            "trade_count": len(raw_returns),
            "open_interest_confirmed_trade_count": len(raw_returns),
            "gross_expectancy": float(gross_expectancy),
            "net_return": float(net_return),
            "max_drawdown": float(max_drawdown),
            "fee_adjusted_expectancy": float(fee_adjusted_expectancy),
            "slippage_adjusted_expectancy": float(slippage_adjusted_expectancy),
            "walk_forward_split_count": walk_forward_split_count,
            "walk_forward_pass_rate": walk_forward_pass_rate,
            "fee_rate": float(fee_rate),
            "slippage_rate": float(slippage_rate),
            "min_open_interest_change_pct": float(min_open_interest_change_pct),
            "open_interest_lookback_bars": int(open_interest_lookback_bars),
            "open_interest_changes": [
                float(value) for value in filter_result.open_interest_changes
            ],
        },
    )


def extract_funding_oi_crowding_trades_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    open_interest_symbol: str | None = None,
    open_interest_timeframe: str | None = None,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
    min_open_interest_change_pct: float = 0.05,
    open_interest_lookback_bars: int = 1,
) -> list[FundingPriceTrade]:
    _validate_parameters(
        min_open_interest_change_pct=min_open_interest_change_pct,
        open_interest_lookback_bars=open_interest_lookback_bars,
        min_trades=0,
    )
    oi_symbol = _nonblank(open_interest_symbol) or funding_symbol
    oi_timeframe = _nonblank(open_interest_timeframe) or timeframe
    open_interest = _open_interest_history_from_records(
        records,
        symbol=oi_symbol,
        timeframe=oi_timeframe,
    )
    if not open_interest or _has_duplicate_open_interest_timestamps(open_interest):
        return []
    trades = extract_funding_price_trades_from_records(
        records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
    )
    return _filter_open_interest_confirmed_trades(
        trades,
        open_interest,
        min_open_interest_change_pct=min_open_interest_change_pct,
        open_interest_lookback_bars=open_interest_lookback_bars,
    ).trades


def _validate_parameters(
    *,
    min_open_interest_change_pct: float,
    open_interest_lookback_bars: int,
    min_trades: int,
) -> None:
    if not math.isfinite(min_open_interest_change_pct) or min_open_interest_change_pct < 0:
        raise ValueError("min_open_interest_change_pct must be finite and non-negative")
    if type(open_interest_lookback_bars) is not int or open_interest_lookback_bars <= 0:
        raise ValueError("open_interest_lookback_bars must be a positive integer")
    if type(min_trades) is not int or min_trades < 0:
        raise ValueError("min_trades must be a non-negative integer")


def _open_interest_history_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    symbol: str,
    timeframe: str,
) -> list[OpenInterestRecord]:
    open_interest: list[OpenInterestRecord] = []
    for record in records:
        try:
            source_record = SourceRecord.model_validate_json(json.dumps(record))
        except (ValidationError, TypeError, ValueError):
            continue
        if source_record.record_type != "open_interest":
            continue
        try:
            item = OpenInterestRecord.model_validate_json(
                json.dumps(source_record.payload)
            )
        except (ValidationError, TypeError, ValueError):
            continue
        if item.symbol != symbol or item.timeframe != timeframe:
            continue
        open_interest.append(item)
    return sorted(
        open_interest,
        key=lambda item: (
            item.timestamp,
            item.source,
            item.venue,
            item.symbol,
            item.timeframe,
        ),
    )


def _filter_open_interest_confirmed_trades(
    trades: Sequence[FundingPriceTrade],
    open_interest: Sequence[OpenInterestRecord],
    *,
    min_open_interest_change_pct: float,
    open_interest_lookback_bars: int,
) -> _OiFilterResult:
    timestamps = [item.timestamp for item in open_interest]
    confirmed: list[FundingPriceTrade] = []
    insufficient_history_count = 0
    non_positive_open_interest_count = 0
    no_expansion_count = 0
    open_interest_changes: list[float] = []

    for trade in trades:
        current_index = bisect_right(timestamps, trade.funding_timestamp) - 1
        previous_index = current_index - open_interest_lookback_bars
        if current_index < 0 or previous_index < 0:
            insufficient_history_count += 1
            continue
        previous_open_interest = float(open_interest[previous_index].open_interest)
        current_open_interest = float(open_interest[current_index].open_interest)
        if previous_open_interest <= 0.0 or current_open_interest <= 0.0:
            non_positive_open_interest_count += 1
            continue
        change_pct = (current_open_interest / previous_open_interest) - 1.0
        if not math.isfinite(change_pct):
            non_positive_open_interest_count += 1
            continue
        if change_pct < min_open_interest_change_pct:
            no_expansion_count += 1
            continue
        confirmed.append(trade)
        open_interest_changes.append(change_pct)

    return _OiFilterResult(
        trades=confirmed,
        insufficient_history_count=insufficient_history_count,
        non_positive_open_interest_count=non_positive_open_interest_count,
        no_expansion_count=no_expansion_count,
        open_interest_changes=open_interest_changes,
    )


def _blocked_reasons(
    *,
    base_blocked_reasons: Sequence[str],
    open_interest_sample_count: int,
    duplicate_open_interest_timestamp: bool,
    insufficient_history_count: int,
    non_positive_open_interest_count: int,
    no_expansion_count: int,
    trade_count: int,
    min_trades: int,
    expectancy: float,
    net_return: float,
    max_drawdown: float,
    max_drawdown_limit: float,
    stale_open_interest: bool,
    unsupported_open_interest_symbol: bool,
    walk_forward_blocked_reasons: Sequence[str],
) -> list[str]:
    reasons: list[str] = []
    base_reason_allowlist = {
        "unsupported_symbol",
        "stale_source",
        "duplicate_price_timestamp",
        "duplicate_funding_timestamp",
        "non_positive_price",
        "insufficient_price_bars",
        "insufficient_funding_samples",
        "no_extreme_funding",
    }
    reasons.extend(
        reason for reason in base_blocked_reasons if reason in base_reason_allowlist
    )
    if unsupported_open_interest_symbol:
        reasons.append("unsupported_symbol")
    if open_interest_sample_count == 0:
        reasons.append("missing_open_interest_records")
    if duplicate_open_interest_timestamp:
        reasons.append("duplicate_open_interest_timestamp")
    if stale_open_interest:
        reasons.append("stale_source")
    if insufficient_history_count > 0 and trade_count == 0:
        reasons.append("insufficient_open_interest_history")
    if non_positive_open_interest_count > 0:
        reasons.append("non_positive_open_interest")
    if no_expansion_count > 0 and trade_count == 0:
        reasons.append("no_open_interest_expansion")
    if trade_count < min_trades:
        reasons.append("insufficient_trades")
    if expectancy <= 0.0:
        reasons.append("non_positive_expectancy")
    if net_return <= 0.0:
        reasons.append("non_positive_net_return")
    if max_drawdown > max_drawdown_limit:
        reasons.append("excessive_drawdown")
    reasons.extend(walk_forward_blocked_reasons)
    return _dedupe(reasons)


def _has_duplicate_open_interest_timestamps(records: Sequence[OpenInterestRecord]) -> bool:
    timestamps: set[datetime] = set()
    for record in records:
        if record.timestamp in timestamps:
            return True
        timestamps.add(record.timestamp)
    return False


def _is_stale_open_interest(
    records: Sequence[OpenInterestRecord],
    *,
    now: datetime | None,
    max_age_hours: float | None,
) -> bool:
    if max_age_hours is None or not records:
        return False
    latest_observed_at = max(_coerce_utc(item.timestamp) for item in records)
    reference_now = _coerce_utc(now) if now is not None else datetime.now(tz=UTC)
    return latest_observed_at < reference_now - timedelta(hours=max_age_hours)


def _walk_forward_adjusted_expectancies(
    *,
    total_bars: int,
    trades: Sequence[tuple[int, int, float]],
    cost_per_trade: float,
    train_size: int,
    test_size: int,
) -> list[float]:
    if total_bars < train_size + test_size:
        return []
    windows = generate_walk_forward_windows(
        total_bars,
        train_size=train_size,
        test_size=test_size,
    )
    expectancies: list[float] = []
    for window in windows:
        split_returns = [
            trade_return - cost_per_trade
            for entry_index, exit_index, trade_return in trades
            if window.test_start <= entry_index and exit_index < window.test_end
        ]
        expectancies.append(
            math.fsum(split_returns) / len(split_returns) if split_returns else 0.0
        )
    return expectancies


def _cumulative_return_and_drawdown(returns: Sequence[float]) -> tuple[float, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for trade_return in returns:
        equity *= 1.0 + trade_return
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return equity - 1.0, max_drawdown


def _nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_supported_symbols(
    supported_symbols: Sequence[str] | None,
    parameter_name: str,
) -> set[str] | None:
    if supported_symbols is None:
        return None
    if isinstance(supported_symbols, str):
        raise ValueError(f"{parameter_name} must be a sequence of symbols")
    normalized: set[str] = set()
    for symbol in supported_symbols:
        if not isinstance(symbol, str):
            raise ValueError(f"{parameter_name} must contain only strings")
        stripped = symbol.strip()
        if not stripped:
            raise ValueError(f"{parameter_name} must contain non-empty symbols")
        normalized.add(stripped)
    if not normalized:
        raise ValueError(f"{parameter_name} must not be empty")
    return normalized


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dedupe(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized)
    return deduped
