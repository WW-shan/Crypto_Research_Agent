from __future__ import annotations

import json
import math
from bisect import bisect_left
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.models import FundingRateRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.market_history import CandleBar, load_candle_history


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
) -> FundingPriceValidationResult:
    if not math.isfinite(threshold_abs) or threshold_abs <= 0:
        raise ValueError("threshold_abs must be finite and greater than 0")
    _require_positive_int("hold_bars", hold_bars)
    _require_non_negative_int("min_trades", min_trades)
    if not math.isfinite(fee_rate) or fee_rate < 0:
        raise ValueError("fee_rate must be finite and non-negative")
    if not math.isfinite(slippage_rate) or slippage_rate < 0:
        raise ValueError("slippage_rate must be finite and non-negative")

    bars = load_candle_history(db_path, symbol=price_symbol, timeframe=timeframe)
    funding_rates = _load_funding_history(db_path, funding_symbol=funding_symbol)
    extremes = [
        funding
        for funding in funding_rates
        if abs(float(funding.funding_rate)) >= threshold_abs
    ]

    raw_returns = _extreme_reversion_returns(
        bars,
        extremes,
        hold_bars=hold_bars,
    )
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
    if require_walk_forward:
        walk_forward_split_count = 0

    blocked_reasons = _blocked_reasons(
        bar_count=len(bars),
        funding_sample_count=len(funding_rates),
        extreme_count=len(extremes),
        trade_count=len(raw_returns),
        hold_bars=hold_bars,
        min_trades=min_trades,
        expectancy=slippage_adjusted_expectancy,
        net_return=net_return,
    )

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


def _require_positive_int(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


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


def _extreme_reversion_returns(
    bars: list[CandleBar],
    extremes: list[FundingRateRecord],
    *,
    hold_bars: int,
) -> list[float]:
    timestamps = [bar.timestamp for bar in bars]
    returns: list[float] = []

    for funding in extremes:
        entry_index = bisect_left(timestamps, funding.timestamp)
        exit_index = entry_index + hold_bars
        if entry_index >= len(bars) or exit_index >= len(bars):
            continue

        entry_price = float(bars[entry_index].close)
        exit_price = float(bars[exit_index].close)
        if entry_price <= 0:
            continue

        price_return = (exit_price / entry_price) - 1.0
        if funding.funding_rate >= 0:
            returns.append(-price_return)
        else:
            returns.append(price_return)

    return returns


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
) -> list[str]:
    reasons: list[str] = []
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
    return reasons
