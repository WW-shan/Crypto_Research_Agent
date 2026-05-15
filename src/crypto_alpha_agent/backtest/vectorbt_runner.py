from __future__ import annotations

from typing import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict


class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    net_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    average_holding_time: float
    fee_adjusted_expectancy: float
    slippage_adjusted_expectancy: float


class _Trade:
    def __init__(self, entry_index: int, exit_index: int, entry_price: float, exit_price: float) -> None:
        self.entry_index = entry_index
        self.exit_index = exit_index
        self.entry_price = entry_price
        self.exit_price = exit_price

    @property
    def holding_time(self) -> float:
        return float(self.exit_index - self.entry_index)

    def gross_return(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price


def _validate_signals(prices: Sequence[float], entries: Sequence[bool], exits: Sequence[bool]) -> None:
    if not (len(prices) == len(entries) == len(exits)):
        raise ValueError("prices, entries, and exits must have the same length")


def _extract_trades(prices: Sequence[float], entries: Sequence[bool], exits: Sequence[bool]) -> list[_Trade]:
    trades: list[_Trade] = []
    open_entry: int | None = None
    for index, (price, entry, exit_) in enumerate(zip(prices, entries, exits, strict=True)):
        if entry and open_entry is None:
            open_entry = index
        elif exit_ and open_entry is not None:
            trades.append(_Trade(open_entry, index, float(prices[open_entry]), float(price)))
            open_entry = None
    if open_entry is not None:
        trades.append(_Trade(open_entry, len(prices) - 1, float(prices[open_entry]), float(prices[-1])))
    return trades


def _equity_curve(prices: Sequence[float], entries: Sequence[bool], exits: Sequence[bool], fee_rate: float, slippage_rate: float) -> np.ndarray:
    equity = 1.0
    curve = [equity]
    in_position = False
    entry_price = 0.0
    for price, entry, exit_ in zip(prices, entries, exits, strict=True):
        if entry and not in_position:
            in_position = True
            entry_price = float(price) * (1.0 + slippage_rate)
            equity *= 1.0 - fee_rate
        elif exit_ and in_position:
            exit_price = float(price) * (1.0 - slippage_rate)
            equity *= (exit_price - entry_price) / entry_price + 1.0
            equity *= 1.0 - fee_rate
            in_position = False
        curve.append(equity)
    return np.asarray(curve, dtype=float)


def _max_drawdown(equity_curve: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peaks) / peaks
    return float(drawdowns.min())


def _summarize(trades: list[_Trade], equity_curve: np.ndarray, fee_rate: float, slippage_rate: float) -> BacktestResult:
    trade_count = len(trades)
    if trade_count == 0:
        return BacktestResult(
            net_return=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            trade_count=0,
            average_holding_time=0.0,
            fee_adjusted_expectancy=0.0,
            slippage_adjusted_expectancy=0.0,
        )

    gross_returns = np.array([trade.gross_return() for trade in trades], dtype=float)
    average_holding_time = float(np.mean([trade.holding_time for trade in trades]))
    win_rate = float(np.mean(gross_returns > 0))
    net_return = float(equity_curve[-1] - 1.0)
    max_drawdown = _max_drawdown(equity_curve)
    fee_penalty = fee_rate * 2.0
    slippage_penalty = slippage_rate * 2.0
    expectancy = float(np.mean(gross_returns))

    return BacktestResult(
        net_return=net_return,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        trade_count=trade_count,
        average_holding_time=average_holding_time,
        fee_adjusted_expectancy=expectancy - fee_penalty,
        slippage_adjusted_expectancy=expectancy - slippage_penalty,
    )


def run_vectorbt_backtest(
    prices: Sequence[float],
    entries: Sequence[bool],
    exits: Sequence[bool],
    fee_rate: float = 0.0,
    slippage_rate: float = 0.0,
) -> BacktestResult:
    _validate_signals(prices, entries, exits)
    trades = _extract_trades(prices, entries, exits)

    try:
        import vectorbt as vbt

        close = np.asarray(prices, dtype=float)
        entries_arr = np.asarray(entries, dtype=bool)
        exits_arr = np.asarray(exits, dtype=bool)
        portfolio = vbt.Portfolio.from_signals(
            close,
            entries_arr,
            exits_arr,
            fees=fee_rate,
            slippage=slippage_rate,
            init_cash=1.0,
            freq="1D",
        )
        equity_curve = np.asarray(portfolio.value().to_numpy(), dtype=float)
    except Exception:
        equity_curve = _equity_curve(prices, entries, exits, fee_rate, slippage_rate)

    return _summarize(trades, equity_curve, fee_rate, slippage_rate)
