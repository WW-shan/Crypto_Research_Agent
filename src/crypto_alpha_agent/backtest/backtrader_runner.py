from __future__ import annotations

from typing import Sequence

import backtrader as bt
import numpy as np

from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult, _extract_trades, _summarize, _validate_signals


class _BrokerValueAnalyzer(bt.Analyzer):
    def start(self):
        self.values = [float(self.strategy.broker.getvalue())]

    def next(self):
        self.values.append(float(self.strategy.broker.getvalue()))

    def get_analysis(self):
        return {"values": self.values}


def _run_backtrader_engine(
    prices: Sequence[float],
    entries: Sequence[bool],
    exits: Sequence[bool],
    fee_rate: float,
    slippage_rate: float,
) -> BacktestResult:
    import pandas as pd

    _validate_signals(prices, entries, exits, fee_rate, slippage_rate)
    index = pd.date_range("2020-01-01", periods=len(prices), freq="D")
    data = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": 1.0}, index=index)

    class SignalStrategy(bt.Strategy):
        params = dict(entries=list(entries), exits=list(exits), fee_rate=fee_rate, slippage_rate=slippage_rate)

        def __init__(self):
            self.order = None

        def notify_order(self, order):
            if order.status in {order.Completed, order.Canceled, order.Margin, order.Rejected}:
                self.order = None

        def next(self):
            if self.order is not None:
                return

            bar = len(self.data) - 1
            if self.position:
                if self.p.exits[bar]:
                    self.order = self.close()
            elif self.p.entries[bar]:
                close_price = float(self.data.close[0])
                cost_per_unit = close_price * (1.0 + self.p.slippage_rate)
                size = self.broker.getcash() / (cost_per_unit * (1.0 + self.p.fee_rate))
                if size > 0:
                    self.order = self.buy(size=size)

    initial_cash = 10_000.0
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=fee_rate)
    cerebro.broker.set_slippage_perc(perc=slippage_rate)
    cerebro.broker.set_coc(True)
    cerebro.adddata(bt.feeds.PandasData(dataname=data))
    cerebro.addstrategy(SignalStrategy)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(_BrokerValueAnalyzer, _name="broker_values")
    strategy = cerebro.run()[0]

    final_value = float(strategy.broker.getvalue())
    net_return = final_value / initial_cash - 1.0
    drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
    max_drawdown_percent = float(drawdown_analysis.get("max", {}).get("drawdown", 0.0))
    max_drawdown = -max_drawdown_percent / 100.0
    values = np.asarray(strategy.analyzers.broker_values.get_analysis()["values"], dtype=float) / initial_cash

    return _summarize(
        _extract_trades(prices, entries, exits),
        values,
        fee_rate,
        slippage_rate,
        net_return=net_return,
        max_drawdown=max_drawdown,
    )


def run_backtrader_backtest(
    prices: Sequence[float],
    entries: Sequence[bool],
    exits: Sequence[bool],
    fee_rate: float = 0.0,
    slippage_rate: float = 0.0,
) -> BacktestResult:
    return _run_backtrader_engine(prices, entries, exits, fee_rate, slippage_rate)
