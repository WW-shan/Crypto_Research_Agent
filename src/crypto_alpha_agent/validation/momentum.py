from __future__ import annotations

from collections.abc import Sequence
import math

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.backtest.vectorbt_runner import run_vectorbt_backtest
from crypto_alpha_agent.validation.market_history import CandleBar


class MomentumValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    symbol: str
    timeframe: str
    bar_count: int
    trade_count: int
    gross_expectancy: float
    net_return: float
    max_drawdown: float
    fee_adjusted_expectancy: float
    slippage_adjusted_expectancy: float
    approved: bool
    blocked_reasons: list[str]


def validate_close_momentum(
    bars: Sequence[CandleBar],
    *,
    lookback_bars: int = 3,
    hold_bars: int = 1,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    min_trades: int = 3,
) -> MomentumValidationResult:
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be greater than 0")
    if hold_bars <= 0:
        raise ValueError("hold_bars must be greater than 0")
    if min_trades < 0:
        raise ValueError("min_trades must be non-negative")
    if not math.isfinite(fee_rate) or fee_rate < 0:
        raise ValueError("fee_rate must be finite and non-negative")
    if not math.isfinite(slippage_rate) or slippage_rate < 0:
        raise ValueError("slippage_rate must be finite and non-negative")
    if not bars:
        raise ValueError("bars must be non-empty")

    symbols = {bar.symbol for bar in bars}
    if len(symbols) != 1:
        raise ValueError("bars must contain exactly one symbol")
    timeframes = {bar.timeframe for bar in bars}
    if len(timeframes) != 1:
        raise ValueError("bars must contain exactly one timeframe")

    sorted_bars = sorted(bars, key=lambda bar: bar.timestamp)
    prices = [float(bar.close) for bar in sorted_bars]
    entries, exits, raw_returns = _momentum_signals(prices, lookback_bars=lookback_bars, hold_bars=hold_bars)

    if len(prices) >= 2:
        backtest = run_vectorbt_backtest(
            prices,
            entries,
            exits,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )
        trade_count = backtest.trade_count
        net_return = backtest.net_return
        max_drawdown = backtest.max_drawdown
        fee_adjusted_expectancy = backtest.fee_adjusted_expectancy
        slippage_adjusted_expectancy = backtest.slippage_adjusted_expectancy
    else:
        trade_count = 0
        net_return = 0.0
        max_drawdown = 0.0
        fee_adjusted_expectancy = 0.0
        slippage_adjusted_expectancy = 0.0

    gross_expectancy = sum(raw_returns) / len(raw_returns) if raw_returns else 0.0
    blocked_reasons = _blocked_reasons(
        bar_count=len(sorted_bars),
        lookback_bars=lookback_bars,
        hold_bars=hold_bars,
        trade_count=trade_count,
        min_trades=min_trades,
        fee_adjusted_expectancy=fee_adjusted_expectancy,
        net_return=net_return,
    )

    return MomentumValidationResult(
        strategy_family="close_momentum",
        symbol=sorted_bars[0].symbol,
        timeframe=sorted_bars[0].timeframe,
        bar_count=len(sorted_bars),
        trade_count=trade_count,
        gross_expectancy=float(gross_expectancy),
        net_return=float(net_return),
        max_drawdown=float(max_drawdown),
        fee_adjusted_expectancy=float(fee_adjusted_expectancy),
        slippage_adjusted_expectancy=float(slippage_adjusted_expectancy),
        approved=not blocked_reasons,
        blocked_reasons=blocked_reasons,
    )


def _momentum_signals(
    prices: Sequence[float],
    *,
    lookback_bars: int,
    hold_bars: int,
) -> tuple[list[bool], list[bool], list[float]]:
    entries = [False] * len(prices)
    exits = [False] * len(prices)
    raw_returns: list[float] = []

    index = lookback_bars
    while index + hold_bars < len(prices):
        if prices[index] > prices[index - lookback_bars]:
            exit_index = index + hold_bars
            entries[index] = True
            exits[exit_index] = True
            raw_returns.append((prices[exit_index] - prices[index]) / prices[index])
            index = exit_index + 1
            continue
        index += 1

    return entries, exits, raw_returns


def _blocked_reasons(
    *,
    bar_count: int,
    lookback_bars: int,
    hold_bars: int,
    trade_count: int,
    min_trades: int,
    fee_adjusted_expectancy: float,
    net_return: float,
) -> list[str]:
    reasons: list[str] = []
    if bar_count < lookback_bars + hold_bars + 1:
        reasons.append("insufficient_bars")
    if trade_count < min_trades:
        reasons.append("insufficient_trades")
    if fee_adjusted_expectancy <= 0.0:
        reasons.append("non_positive_expectancy")
    if net_return <= 0.0:
        reasons.append("non_positive_net_return")
    return reasons
