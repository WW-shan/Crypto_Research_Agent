from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.execution.cost_model import (
    ExecutionCostAssumptions,
    ExecutionTradeSpec,
    SymbolMarketConstraints,
    estimate_execution_cost,
)


def _trade(**overrides):
    data = {
        "symbol": "ETH/USDT:USDT",
        "venue": "binance",
        "direction": "long_price",
        "signal_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "entry_timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "exit_timestamp": datetime(2026, 1, 1, 1, tzinfo=UTC),
        "entry_reference_price": 100.0,
        "exit_reference_price": 101.0,
        "raw_return": 0.01,
        "requested_notional_usd": 25.0,
        "entry_volume": 1000.0,
        "exit_volume": 1000.0,
    }
    data.update(overrides)
    return ExecutionTradeSpec(**data)


def test_pessimistic_binance_defaults_use_taker_fee_floor_and_record_assumptions():
    estimate = estimate_execution_cost(
        _trade(),
        ExecutionCostAssumptions(venue="binance", fee_rate_floor=0.001),
    )

    assert estimate.status == "tradeable"
    assert estimate.cost_model_mode == "pessimistic"
    assert estimate.venue == "binance"
    assert estimate.fee_model_id.startswith("binance:")
    assert estimate.maker_fee_rate >= 0
    assert estimate.taker_fee_rate >= estimate.maker_fee_rate
    assert estimate.applied_entry_fee_rate == pytest.approx(0.001)
    assert estimate.applied_exit_fee_rate == pytest.approx(0.001)
    assert estimate.fill_status == "full"
    assert estimate.fill_ratio == pytest.approx(1.0)
    assert estimate.fees_usd == pytest.approx(0.05)
    assert estimate.slippage_bps == pytest.approx(5.0)
    assert estimate.stale_signal_status == "fresh"
    assert estimate.failure_reasons == ()


def test_positive_gross_pnl_that_costs_turn_negative_is_blocked():
    estimate = estimate_execution_cost(
        _trade(raw_return=0.001),
        ExecutionCostAssumptions(venue="binance", fee_rate_floor=0.001),
    )

    assert estimate.gross_pnl_usd > 0
    assert estimate.net_pnl_usd <= 0
    assert estimate.status == "blocked"
    assert estimate.fill_status == "full"
    assert "pre_cost_only_profitable" in estimate.failure_reasons


def test_constraints_block_symbol_that_cannot_trade_under_25_usd():
    constraints = SymbolMarketConstraints(
        venue="binance",
        symbol="BTC/USDT:USDT",
        min_notional_usd=5.0,
        min_quantity=0.001,
        quantity_step=0.001,
        tick_size=0.1,
    )

    estimate = estimate_execution_cost(
        _trade(
            symbol="BTC/USDT:USDT",
            entry_reference_price=65000.0,
            exit_reference_price=65100.0,
            raw_return=100.0 / 65000.0,
        ),
        ExecutionCostAssumptions(
            venue="binance",
            max_notional_usd=25.0,
            symbol_constraints=constraints,
        ),
    )

    assert estimate.status == "blocked"
    assert "quantity_precision_not_tradeable" in estimate.failure_reasons
    assert "min_quantity_notional_exceeds_max_notional" in estimate.failure_reasons
    assert estimate.fill_status == "blocked"
    assert estimate.effective_notional_usd == 0.0


def test_stale_signal_and_low_liquidity_are_explicit_block_reasons():
    estimate = estimate_execution_cost(
        _trade(
            direction="short_price",
            entry_timestamp=datetime(2026, 1, 1, 2, tzinfo=UTC),
            exit_timestamp=datetime(2026, 1, 1, 3, tzinfo=UTC),
            exit_reference_price=99.0,
            raw_return=0.01,
            entry_volume=0.01,
            exit_volume=0.01,
        ),
        ExecutionCostAssumptions(
            venue="binance",
            max_signal_age_seconds=60.0,
            max_volume_participation_rate=0.05,
        ),
    )

    assert estimate.status == "blocked"
    assert estimate.stale_signal_status == "stale"
    assert estimate.fill_status == "missed"
    assert "stale_signal" in estimate.failure_reasons
    assert "missed_fill_assumed" in estimate.failure_reasons


def test_partial_fill_reduces_notional_when_enabled():
    estimate = estimate_execution_cost(
        _trade(entry_volume=1.0, exit_volume=1.0),
        ExecutionCostAssumptions(
            venue="binance",
            max_volume_participation_rate=0.10,
            allow_partial_fills=True,
        ),
    )

    assert estimate.status == "tradeable"
    assert estimate.fill_status == "partial"
    assert 0 < estimate.fill_ratio < 1
    assert estimate.effective_notional_usd == pytest.approx(10.0)
    assert estimate.net_pnl_usd < estimate.gross_pnl_usd


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_notional_usd", -1.0),
        ("fee_rate_floor", -0.001),
        ("fixed_slippage_bps", -1.0),
        ("max_volume_participation_rate", 0.0),
    ],
)
def test_execution_cost_assumptions_reject_invalid_numbers(field, value):
    with pytest.raises(ValidationError):
        ExecutionCostAssumptions(venue="binance", **{field: value})
