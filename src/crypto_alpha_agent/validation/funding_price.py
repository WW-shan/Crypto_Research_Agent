from __future__ import annotations

import json
import math
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.gates import evaluate_walk_forward_gate
from crypto_alpha_agent.validation.market_history import CandleBar, load_candle_history
from crypto_alpha_agent.validation.walk_forward import generate_walk_forward_windows


class FundingPriceValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    symbol: str
    funding_symbol: str
    timeframe: str
    bar_count: int
    funding_sample_count: int
    extreme_count: int
    trade_count: int
    gross_expectancy: float
    net_return: float
    max_drawdown: float
    fee_adjusted_expectancy: float
    slippage_adjusted_expectancy: float
    walk_forward_split_count: int
    walk_forward_pass_rate: float
    approved: bool
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class FundingPriceTrade:
    funding: FundingRateRecord
    entry_bar: CandleBar
    exit_bar: CandleBar
    entry_index: int
    exit_index: int
    direction: Literal["short_price", "long_price"]
    raw_return: float

    @property
    def funding_symbol(self) -> str:
        return self.funding.symbol

    @property
    def funding_timestamp(self) -> datetime:
        return self.funding.timestamp

    @property
    def funding_rate(self) -> float:
        return float(self.funding.funding_rate)

    @property
    def entry_timestamp(self) -> datetime:
        return self.entry_bar.timestamp

    @property
    def exit_timestamp(self) -> datetime:
        return self.exit_bar.timestamp

    @property
    def entry_price(self) -> float:
        return float(self.entry_bar.close)

    @property
    def exit_price(self) -> float:
        return float(self.exit_bar.close)


def extract_funding_price_trades(
    bars: Sequence[CandleBar],
    funding_rates: Sequence[FundingRateRecord],
    *,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
) -> list[FundingPriceTrade]:
    if not math.isfinite(threshold_abs) or threshold_abs <= 0:
        raise ValueError("threshold_abs must be finite and greater than 0")
    _require_positive_int("hold_bars", hold_bars)

    timestamps = [bar.timestamp for bar in bars]
    trades: list[FundingPriceTrade] = []
    for funding in funding_rates:
        funding_rate = float(funding.funding_rate)
        if not math.isfinite(funding_rate):
            raise ValueError("funding_rate must be finite")
        if abs(funding_rate) < threshold_abs:
            continue

        entry_index = bisect_left(timestamps, funding.timestamp)
        exit_index = entry_index + hold_bars
        if entry_index >= len(bars) or exit_index >= len(bars):
            continue

        entry_bar = bars[entry_index]
        exit_bar = bars[exit_index]
        entry_price = float(entry_bar.close)
        exit_price = float(exit_bar.close)
        if entry_price <= 0 or exit_price <= 0:
            continue

        price_return = (exit_price / entry_price) - 1.0
        direction: Literal["short_price", "long_price"]
        if funding_rate >= 0:
            direction = "short_price"
            raw_return = -price_return
        else:
            direction = "long_price"
            raw_return = price_return
        trades.append(
            FundingPriceTrade(
                funding=funding,
                entry_bar=entry_bar,
                exit_bar=exit_bar,
                entry_index=entry_index,
                exit_index=exit_index,
                direction=direction,
                raw_return=raw_return,
            )
        )

    return trades


def extract_funding_price_trades_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
) -> list[FundingPriceTrade]:
    if not math.isfinite(threshold_abs) or threshold_abs <= 0:
        raise ValueError("threshold_abs must be finite and greater than 0")
    _require_positive_int("hold_bars", hold_bars)

    bars, funding_rates = _funding_price_history_from_records(
        records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
    )
    if _has_duplicate_timestamps(bars) or _has_duplicate_timestamps(funding_rates):
        return []

    extremes = [
        funding
        for funding in funding_rates
        if abs(float(funding.funding_rate)) >= threshold_abs
    ]
    if _has_non_positive_trade_price(bars, extremes, hold_bars=hold_bars):
        return []

    return extract_funding_price_trades(
        bars,
        funding_rates,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
    )


def latest_funding_price_observed_at_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> datetime | None:
    bars, funding_rates = _funding_price_history_from_records(
        records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
    )
    observed = [bar.timestamp for bar in bars]
    observed.extend(funding.timestamp for funding in funding_rates)
    return max(observed) if observed else None


def validate_funding_price_confirmation(
    db_path: str | Path,
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
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
) -> FundingPriceValidationResult:
    if not math.isfinite(threshold_abs) or threshold_abs <= 0:
        raise ValueError("threshold_abs must be finite and greater than 0")
    _require_positive_int("hold_bars", hold_bars)
    _require_non_negative_int("min_trades", min_trades)
    if not math.isfinite(fee_rate) or fee_rate < 0:
        raise ValueError("fee_rate must be finite and non-negative")
    if not math.isfinite(slippage_rate) or slippage_rate < 0:
        raise ValueError("slippage_rate must be finite and non-negative")
    _validate_max_drawdown_limit(max_drawdown_limit)
    _validate_max_age_hours(max_age_hours)
    normalized_supported_price_symbols = _normalize_supported_symbols(
        supported_price_symbols,
        "supported_price_symbols",
    )
    normalized_supported_funding_symbols = _normalize_supported_symbols(
        supported_funding_symbols,
        "supported_funding_symbols",
    )

    bars = load_candle_history(db_path, symbol=price_symbol, timeframe=timeframe)
    funding_rates = _load_funding_history(db_path, funding_symbol=funding_symbol)
    return _validate_funding_price_confirmation_from_history(
        bars,
        funding_rates,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
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
        supported_price_symbols=normalized_supported_price_symbols,
        supported_funding_symbols=normalized_supported_funding_symbols,
    )


def validate_funding_price_confirmation_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
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
) -> FundingPriceValidationResult:
    if not math.isfinite(threshold_abs) or threshold_abs <= 0:
        raise ValueError("threshold_abs must be finite and greater than 0")
    _require_positive_int("hold_bars", hold_bars)
    _require_non_negative_int("min_trades", min_trades)
    if not math.isfinite(fee_rate) or fee_rate < 0:
        raise ValueError("fee_rate must be finite and non-negative")
    if not math.isfinite(slippage_rate) or slippage_rate < 0:
        raise ValueError("slippage_rate must be finite and non-negative")
    _validate_max_drawdown_limit(max_drawdown_limit)
    _validate_max_age_hours(max_age_hours)
    normalized_supported_price_symbols = _normalize_supported_symbols(
        supported_price_symbols,
        "supported_price_symbols",
    )
    normalized_supported_funding_symbols = _normalize_supported_symbols(
        supported_funding_symbols,
        "supported_funding_symbols",
    )

    bars, funding_rates = _funding_price_history_from_records(
        records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
    )
    return _validate_funding_price_confirmation_from_history(
        bars,
        funding_rates,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
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
        supported_price_symbols=normalized_supported_price_symbols,
        supported_funding_symbols=normalized_supported_funding_symbols,
    )


def _validate_funding_price_confirmation_from_history(
    bars: list[CandleBar],
    funding_rates: list[FundingRateRecord],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    threshold_abs: float,
    hold_bars: int,
    fee_rate: float,
    slippage_rate: float,
    min_trades: int,
    require_walk_forward: bool,
    walk_forward_train_size: int,
    walk_forward_test_size: int,
    walk_forward_min_splits: int,
    walk_forward_min_pass_rate: float,
    max_drawdown_limit: float,
    now: datetime | None,
    max_age_hours: float | None,
    supported_price_symbols: set[str] | None,
    supported_funding_symbols: set[str] | None,
) -> FundingPriceValidationResult:
    duplicate_price_timestamp = _has_duplicate_timestamps(bars)
    duplicate_funding_timestamp = _has_duplicate_timestamps(funding_rates)
    unsupported_symbol = _is_unsupported_symbol(
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        supported_price_symbols=supported_price_symbols,
        supported_funding_symbols=supported_funding_symbols,
    )
    stale_source = _is_stale_source(
        bars,
        funding_rates,
        now=now,
        max_age_hours=max_age_hours,
    )
    extremes = [
        funding
        for funding in funding_rates
        if abs(float(funding.funding_rate)) >= threshold_abs
    ]
    non_positive_price = False
    if not duplicate_price_timestamp and not duplicate_funding_timestamp:
        non_positive_price = _has_non_positive_trade_price(
            bars,
            extremes,
            hold_bars=hold_bars,
        )

    trades: list[FundingPriceTrade] = []
    if (
        not duplicate_price_timestamp
        and not duplicate_funding_timestamp
        and not non_positive_price
    ):
        trades = extract_funding_price_trades(
            bars,
            funding_rates,
            threshold_abs=threshold_abs,
            hold_bars=hold_bars,
        )
    indexed_trades = [
        (trade.entry_index, trade.exit_index, trade.raw_return) for trade in trades
    ]
    raw_returns = [trade.raw_return for trade in trades]
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
            total_bars=len(bars),
            trades=indexed_trades,
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
        bar_count=len(bars),
        funding_sample_count=len(funding_rates),
        extreme_count=len(extremes),
        trade_count=len(raw_returns),
        hold_bars=hold_bars,
        min_trades=min_trades,
        expectancy=slippage_adjusted_expectancy,
        net_return=net_return,
        max_drawdown=max_drawdown,
        max_drawdown_limit=max_drawdown_limit,
        duplicate_price_timestamp=duplicate_price_timestamp,
        duplicate_funding_timestamp=duplicate_funding_timestamp,
        non_positive_price=non_positive_price,
        unsupported_symbol=unsupported_symbol,
        stale_source=stale_source,
    )
    blocked_reasons.extend(walk_forward_blocked_reasons)

    return FundingPriceValidationResult(
        strategy_family="funding_extremity_price_confirmation",
        symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        bar_count=len(bars),
        funding_sample_count=len(funding_rates),
        extreme_count=len(extremes),
        trade_count=len(raw_returns),
        gross_expectancy=float(gross_expectancy),
        net_return=float(net_return),
        max_drawdown=float(max_drawdown),
        fee_adjusted_expectancy=float(fee_adjusted_expectancy),
        slippage_adjusted_expectancy=float(slippage_adjusted_expectancy),
        walk_forward_split_count=walk_forward_split_count,
        walk_forward_pass_rate=walk_forward_pass_rate,
        approved=not blocked_reasons,
        blocked_reasons=blocked_reasons,
    )


def _funding_price_history_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> tuple[list[CandleBar], list[FundingRateRecord]]:
    bars: list[CandleBar] = []
    funding_rates: list[FundingRateRecord] = []
    for record in records:
        source_record = SourceRecord.model_validate_json(json.dumps(record))
        if source_record.record_type == "market_candle":
            candle = MarketCandle.model_validate_json(json.dumps(source_record.payload))
            if candle.symbol != price_symbol or candle.timeframe != timeframe:
                continue
            bars.append(
                CandleBar(
                    source=candle.source,
                    venue=candle.venue,
                    symbol=candle.symbol,
                    timestamp=candle.timestamp,
                    timeframe=candle.timeframe,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
            )
            continue
        if source_record.record_type == "funding_rate":
            funding = FundingRateRecord.model_validate_json(json.dumps(source_record.payload))
            if funding.symbol != funding_symbol:
                continue
            funding_rate = float(funding.funding_rate)
            if not math.isfinite(funding_rate):
                raise ValueError("funding_rate must be finite")
            funding_rates.append(funding)

    bars.sort(key=lambda bar: (bar.timestamp, bar.source, bar.venue, bar.symbol))
    funding_rates.sort(
        key=lambda funding: (
            funding.timestamp,
            funding.source,
            funding.venue,
            funding.symbol,
        )
    )
    return bars, funding_rates


def _require_positive_int(name: str, value: int) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _require_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_max_drawdown_limit(max_drawdown_limit: float) -> None:
    if not math.isfinite(max_drawdown_limit) or max_drawdown_limit < 0:
        raise ValueError("max_drawdown_limit must be finite and non-negative")


def _validate_max_age_hours(max_age_hours: float | None) -> None:
    if max_age_hours is None:
        return
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be finite and greater than 0")


def _normalize_supported_symbols(
    supported_symbols: Sequence[str] | None,
    name: str,
) -> set[str] | None:
    if supported_symbols is None:
        return None
    if isinstance(supported_symbols, str):
        raise ValueError(f"{name} must be a sequence of symbols")
    normalized: set[str] = set()
    for symbol in supported_symbols:
        if not isinstance(symbol, str):
            raise ValueError(f"{name} must contain symbols")
        stripped = symbol.strip()
        if not stripped:
            raise ValueError(f"{name} must not contain blank symbols")
        normalized.add(stripped)
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _load_funding_history(
    db_path: str | Path,
    *,
    funding_symbol: str,
) -> list[FundingRateRecord]:
    store = ResearchDataStore(db_path)
    funding_rates: list[FundingRateRecord] = []
    for record in store.load_records(record_type="funding_rate"):
        funding = FundingRateRecord.model_validate_json(json.dumps(record.payload))
        if funding.symbol != funding_symbol:
            continue
        funding_rate = float(funding.funding_rate)
        if not math.isfinite(funding_rate):
            raise ValueError("funding_rate must be finite")
        funding_rates.append(funding)
    return sorted(
        funding_rates,
        key=lambda funding: (
            funding.timestamp,
            funding.source,
            funding.venue,
            funding.symbol,
        ),
    )


def _has_duplicate_timestamps(records: list[CandleBar] | list[FundingRateRecord]) -> bool:
    timestamps = set()
    for record in records:
        if record.timestamp in timestamps:
            return True
        timestamps.add(record.timestamp)
    return False


def _has_non_positive_trade_price(
    bars: list[CandleBar],
    extremes: list[FundingRateRecord],
    *,
    hold_bars: int,
) -> bool:
    timestamps = [bar.timestamp for bar in bars]

    for funding in extremes:
        entry_index = bisect_left(timestamps, funding.timestamp)
        exit_index = entry_index + hold_bars
        if entry_index >= len(bars) or exit_index >= len(bars):
            continue

        entry_price = float(bars[entry_index].close)
        exit_price = float(bars[exit_index].close)
        if entry_price <= 0 or exit_price <= 0:
            return True

    return False


def _is_unsupported_symbol(
    *,
    price_symbol: str,
    funding_symbol: str,
    supported_price_symbols: set[str] | None,
    supported_funding_symbols: set[str] | None,
) -> bool:
    if supported_price_symbols is not None and price_symbol not in supported_price_symbols:
        return True
    return supported_funding_symbols is not None and funding_symbol not in supported_funding_symbols


def _is_stale_source(
    bars: list[CandleBar],
    funding_rates: list[FundingRateRecord],
    *,
    now: datetime | None,
    max_age_hours: float | None,
) -> bool:
    if max_age_hours is None:
        return False
    reference_now = _coerce_utc(now) if now is not None else datetime.now(tz=UTC)
    freshness_floor = reference_now - timedelta(hours=max_age_hours)
    for timestamps in (
        [bar.timestamp for bar in bars],
        [funding.timestamp for funding in funding_rates],
    ):
        if not timestamps:
            continue
        latest_observed_at = max(_coerce_utc(value) for value in timestamps)
        if latest_observed_at < freshness_floor:
            return True
    return False


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _walk_forward_adjusted_expectancies(
    *,
    total_bars: int,
    trades: Sequence[tuple[int, int, float]],
    cost_per_trade: float,
    train_size: int,
    test_size: int,
) -> list[float]:
    train_size = _require_positive_int("walk_forward_train_size", train_size)
    test_size = _require_positive_int("walk_forward_test_size", test_size)
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
        expectancy = (
            math.fsum(split_returns) / len(split_returns) if split_returns else 0.0
        )
        expectancies.append(expectancy)

    return expectancies


def _cumulative_return_and_drawdown(returns: list[float]) -> tuple[float, float]:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0

    for trade_return in returns:
        equity *= 1.0 + trade_return
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)

    return equity - 1.0, max_drawdown


def _blocked_reasons(
    *,
    bar_count: int,
    funding_sample_count: int,
    extreme_count: int,
    trade_count: int,
    hold_bars: int,
    min_trades: int,
    expectancy: float,
    net_return: float,
    max_drawdown: float,
    max_drawdown_limit: float,
    duplicate_price_timestamp: bool,
    duplicate_funding_timestamp: bool,
    non_positive_price: bool,
    unsupported_symbol: bool,
    stale_source: bool,
) -> list[str]:
    reasons: list[str] = []
    if unsupported_symbol:
        reasons.append("unsupported_symbol")
    if stale_source:
        reasons.append("stale_source")
    if duplicate_price_timestamp:
        reasons.append("duplicate_price_timestamp")
    if duplicate_funding_timestamp:
        reasons.append("duplicate_funding_timestamp")
    if non_positive_price:
        reasons.append("non_positive_price")
    if bar_count < hold_bars + 1:
        reasons.append("insufficient_price_bars")
    if funding_sample_count == 0:
        reasons.append("insufficient_funding_samples")
    if extreme_count == 0:
        reasons.append("no_extreme_funding")
    if trade_count < min_trades:
        reasons.append("insufficient_trades")
    if expectancy <= 0.0:
        reasons.append("non_positive_expectancy")
    if net_return <= 0.0:
        reasons.append("non_positive_net_return")
    if max_drawdown > max_drawdown_limit:
        reasons.append("excessive_drawdown")
    return reasons
