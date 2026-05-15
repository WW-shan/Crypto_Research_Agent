from __future__ import annotations

from typing import Sequence

import backtrader as bt

from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult, _equity_curve, _extract_trades, _summarize, _validate_signals


def _run_backtrader_engine(prices: Sequence[float], entries: Sequence[bool], exits: Sequence[bool], fee_rate: float, slippage_rate: float) -> BacktestResult:
    import pandas as pd

    _validate_signals(prices, entries, exits)
    index = pd.date_range("2020-01-01", periods=len(prices), freq="D")
    data = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": 1.0}, index=index)

    class SignalStrategy(bt.Strategy):
        params = dict(entries=list(entries), exits=list(exits))

        def next(self):
            bar = len(self.data) - 1
            if self.position:
                if self.p.exits[bar]:
                    self.close()
            elif self.p.entries[bar]:
                self.buy()

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(1.0)
    cerebro.broker.setcommission(commission=fee_rate)
    cerebro.broker.set_slippage_perc(perc=slippage_rate)
    cerebro.adddata(bt.feeds.PandasData(dataname=data))
    cerebro.addstrategy(SignalStrategy)
    cerebro.run()
    return _summarize(_extract_trades(prices, entries, exits), _equity_curve(prices, entries, exits, fee_rate, slippage_rate), fee_rate, slippage_rate)


def run_backtrader_backtest(
    prices: Sequence[float],
    entries: Sequence[bool],
    exits: Sequence[bool],
    fee_rate: float = 0.0,
    slippage_rate: float = 0.0,
) -> BacktestResult:
    return _run_backtrader_engine(prices, entries, exits, fee_rate, slippage_rate)
