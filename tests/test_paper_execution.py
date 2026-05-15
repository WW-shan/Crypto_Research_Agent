import math

import pytest
from pydantic import ValidationError


def test_paper_round_trip_applies_slippage_fees_latency_and_realized_pnl():
    from crypto_alpha_agent.execution.paper import PaperAccount, PaperOrder

    account = PaperAccount(cash=1_000.0)

    buy = account.execute_order(
        PaperOrder(
            symbol="ETH-USD",
            side="buy",
            quantity=2.0,
            reference_price=100.0,
            fee_rate=0.001,
            slippage_bps=50.0,
            latency_ms=250.0,
        )
    )

    assert buy.fill.fill_price == pytest.approx(100.5)
    assert buy.fill.gross_value == pytest.approx(201.0)
    assert buy.fill.fee == pytest.approx(0.201)
    assert buy.realized_gross_pnl == pytest.approx(0.0)
    assert buy.realized_net_pnl == pytest.approx(0.0)
    assert buy.capital_used == pytest.approx(201.201)
    assert buy.fill.latency_ms == pytest.approx(250.0)
    assert buy.fill.external_order_id is None
    assert account.cash == pytest.approx(798.799)
    assert account.inventory["ETH-USD"] == pytest.approx(2.0)

    sell = account.execute_order(
        PaperOrder(
            symbol="ETH-USD",
            side="sell",
            quantity=2.0,
            reference_price=110.0,
            fee_rate=0.001,
            slippage_bps=50.0,
            latency_ms=125.0,
        )
    )

    assert sell.fill.fill_price == pytest.approx(109.45)
    assert sell.fill.gross_value == pytest.approx(218.9)
    assert sell.fill.fee == pytest.approx(0.2189)
    assert sell.realized_gross_pnl == pytest.approx(17.9)
    assert sell.realized_net_pnl == pytest.approx(17.4801)
    assert sell.capital_used == pytest.approx(201.201)
    assert sell.fill.latency_ms == pytest.approx(125.0)
    assert sell.fill.external_order_id is None
    assert account.cash == pytest.approx(1_017.4801)
    assert account.inventory["ETH-USD"] == pytest.approx(0.0)
    assert account.realized_gross_pnl == pytest.approx(17.9)
    assert account.realized_net_pnl == pytest.approx(17.4801)


def test_paper_round_trip_exports_backtest_result_contract_with_cost_adjustments():
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult, run_vectorbt_backtest
    from crypto_alpha_agent.execution.paper import PaperAccount, PaperOrder, paper_round_trip_to_backtest_result

    fee_rate = 0.001
    slippage_rate = 0.005
    prices = [100.0, 110.0]
    entries = [True, False]
    exits = [False, True]
    account = PaperAccount(cash=1_000.0)
    buy = account.execute_order(
        PaperOrder(
            symbol="ETH-USD",
            side="buy",
            quantity=2.0,
            reference_price=100.0,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )
    )
    sell = account.execute_order(
        PaperOrder(
            symbol="ETH-USD",
            side="sell",
            quantity=2.0,
            reference_price=110.0,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )
    )

    result = paper_round_trip_to_backtest_result(buy.fill, sell.fill, holding_time=1.0)
    vectorbt_result = run_vectorbt_backtest(
        prices=prices,
        entries=entries,
        exits=exits,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )

    assert isinstance(result, BacktestResult)
    assert result.net_return == pytest.approx(vectorbt_result.net_return)
    assert result.max_drawdown == pytest.approx(vectorbt_result.max_drawdown)
    assert result.win_rate == pytest.approx(vectorbt_result.win_rate)
    assert result.trade_count == vectorbt_result.trade_count
    assert result.average_holding_time == pytest.approx(vectorbt_result.average_holding_time)
    assert result.fee_adjusted_expectancy == pytest.approx(vectorbt_result.fee_adjusted_expectancy)
    assert result.slippage_adjusted_expectancy == pytest.approx(vectorbt_result.slippage_adjusted_expectancy)


def test_mark_to_market_reports_cash_inventory_unrealized_and_equity():
    from crypto_alpha_agent.execution.paper import PaperAccount, PaperOrder

    account = PaperAccount(cash=1_000.0)
    account.execute_order(
        PaperOrder(
            symbol="BTC-USD",
            side="buy",
            quantity=1.5,
            reference_price=200.0,
            fee_rate=0.002,
            slippage_rate=0.01,
        )
    )

    result = account.mark_to_market({"BTC-USD": 210.0})

    assert result.cash == pytest.approx(696.394)
    assert result.inventory_value == pytest.approx(315.0)
    assert result.equity == pytest.approx(1_011.394)
    assert result.unrealized_gross_pnl == pytest.approx(12.0)
    assert result.realized_net_pnl == pytest.approx(0.0)
    assert result.touched_real_capital is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", 0.0),
        ("quantity", -1.0),
        ("quantity", math.inf),
        ("reference_price", 0.0),
        ("reference_price", -100.0),
        ("reference_price", math.nan),
        ("fee_rate", -0.001),
        ("slippage_rate", -0.001),
        ("slippage_bps", -1.0),
        ("latency_ms", -1.0),
    ],
)
def test_paper_order_rejects_invalid_numeric_inputs(field, value):
    from crypto_alpha_agent.execution.paper import PaperOrder

    kwargs = {
        "symbol": "SOL-USD",
        "side": "buy",
        "quantity": 1.0,
        "reference_price": 10.0,
    }
    kwargs[field] = value

    with pytest.raises(ValidationError):
        PaperOrder(**kwargs)


def test_paper_order_rejects_type_coercion_and_ambiguous_slippage_units():
    from crypto_alpha_agent.execution.paper import PaperOrder

    with pytest.raises(ValidationError):
        PaperOrder(symbol="SOL-USD", side="buy", quantity="1.0", reference_price=10.0)

    with pytest.raises(ValidationError, match="only one slippage"):
        PaperOrder(
            symbol="SOL-USD",
            side="buy",
            quantity=1.0,
            reference_price=10.0,
            slippage_rate=0.001,
            slippage_bps=10.0,
        )


def test_paper_account_rejects_insufficient_cash_and_inventory():
    from crypto_alpha_agent.execution.paper import PaperAccount, PaperOrder

    account = PaperAccount(cash=100.0)

    with pytest.raises(ValueError, match="insufficient paper cash"):
        account.execute_order(
            PaperOrder(
                symbol="ETH-USD",
                side="buy",
                quantity=2.0,
                reference_price=100.0,
                fee_rate=0.001,
            )
        )

    with pytest.raises(ValueError, match="insufficient paper inventory"):
        account.execute_order(
            PaperOrder(
                symbol="ETH-USD",
                side="sell",
                quantity=1.0,
                reference_price=100.0,
            )
        )
