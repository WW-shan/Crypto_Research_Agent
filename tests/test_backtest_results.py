import pytest
from pydantic import ValidationError


def _toy_prices_and_signals():
    return {
        "prices": [100.0, 110.0, 105.0, 115.0, 120.0, 108.0, 112.0],
        "entries": [True, False, False, True, False, False, False],
        "exits": [False, False, True, False, False, True, False],
    }


def _required_result_keys():
    return {
        "net_return",
        "max_drawdown",
        "win_rate",
        "trade_count",
        "average_holding_time",
        "fee_adjusted_expectancy",
        "slippage_adjusted_expectancy",
    }


def test_backtest_result_requires_all_metrics_and_rejects_type_coercion():
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    with pytest.raises(ValidationError):
        BacktestResult(
            net_return=0.1,
            max_drawdown=-0.05,
            win_rate=0.5,
            trade_count=2,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.01,
        )

    with pytest.raises(ValidationError):
        BacktestResult(
            net_return="0.1",
            max_drawdown=-0.05,
            win_rate=0.5,
            trade_count=2,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.01,
            slippage_adjusted_expectancy=0.01,
        )


def test_vectorbt_adapter_returns_normalized_result_for_toy_strategy():
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult, run_vectorbt_backtest

    result = run_vectorbt_backtest(**_toy_prices_and_signals(), fee_rate=0.001, slippage_rate=0.002)

    assert isinstance(result, BacktestResult)
    dumped = result.model_dump()
    assert set(dumped) == _required_result_keys()
    assert all(isinstance(dumped[key], float) for key in dumped if key != "trade_count")
    assert isinstance(result.trade_count, int)
    assert result.trade_count == 2
    assert result.average_holding_time == pytest.approx(2.0)
    assert result.win_rate == pytest.approx(0.5)


def test_backtrader_adapter_returns_normalized_result_for_toy_strategy():
    from crypto_alpha_agent.backtest.backtrader_runner import run_backtrader_backtest
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    result = run_backtrader_backtest(**_toy_prices_and_signals(), fee_rate=0.001, slippage_rate=0.002)

    assert isinstance(result, BacktestResult)
    dumped = result.model_dump()
    assert set(dumped) == _required_result_keys()
    assert all(isinstance(dumped[key], float) for key in dumped if key != "trade_count")
    assert isinstance(result.trade_count, int)
    assert result.trade_count == 2
    assert result.average_holding_time == pytest.approx(2.0)
    assert result.win_rate == pytest.approx(0.5)


def test_adapters_normalize_to_comparable_keys_and_types():
    from crypto_alpha_agent.backtest.backtrader_runner import run_backtrader_backtest
    from crypto_alpha_agent.backtest.vectorbt_runner import run_vectorbt_backtest

    vectorbt_result = run_vectorbt_backtest(**_toy_prices_and_signals())
    backtrader_result = run_backtrader_backtest(**_toy_prices_and_signals())

    vectorbt_dump = vectorbt_result.model_dump()
    backtrader_dump = backtrader_result.model_dump()

    assert vectorbt_dump.keys() == backtrader_dump.keys()
    assert {key: type(value) for key, value in vectorbt_dump.items()} == {
        key: type(value) for key, value in backtrader_dump.items()
    }


def test_fee_and_slippage_adjust_expectancy_deterministically():
    from crypto_alpha_agent.backtest.backtrader_runner import run_backtrader_backtest
    from crypto_alpha_agent.backtest.vectorbt_runner import run_vectorbt_backtest

    no_costs = run_vectorbt_backtest(**_toy_prices_and_signals())
    vectorbt_costs = run_vectorbt_backtest(**_toy_prices_and_signals(), fee_rate=0.001, slippage_rate=0.002)
    backtrader_costs = run_backtrader_backtest(**_toy_prices_and_signals(), fee_rate=0.001, slippage_rate=0.002)

    assert vectorbt_costs.fee_adjusted_expectancy == pytest.approx(
        no_costs.fee_adjusted_expectancy - 0.002
    )
    assert vectorbt_costs.slippage_adjusted_expectancy == pytest.approx(
        no_costs.slippage_adjusted_expectancy - 0.004
    )
    assert backtrader_costs.fee_adjusted_expectancy == pytest.approx(
        vectorbt_costs.fee_adjusted_expectancy
    )
    assert backtrader_costs.slippage_adjusted_expectancy == pytest.approx(
        vectorbt_costs.slippage_adjusted_expectancy
    )
