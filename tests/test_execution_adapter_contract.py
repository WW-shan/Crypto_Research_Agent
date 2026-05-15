import pytest

from crypto_alpha_agent.execution.freqtrade_adapter import FreqtradeAdapter
from crypto_alpha_agent.execution.hummingbot_adapter import ExecutionIntent, HummingbotAdapter
from crypto_alpha_agent.risk.guardian import RiskDecision


def _paper_decision(**overrides) -> RiskDecision:
    data = {
        "opportunity_id": "opp-17",
        "approved": True,
        "execution_mode": "paper",
        "execution_allowed": True,
        "live_execution_allowed": False,
        "reason_codes": [],
    }
    data.update(overrides)
    return RiskDecision(**data)


def _paper_intent(**overrides) -> ExecutionIntent:
    data = {
        "opportunity_id": "opp-17",
        "venue": "binance",
        "symbol": "ETH-USDT",
        "side": "buy",
        "quantity": 1.25,
        "reference_price": 2_500.0,
        "max_capital_usd": 3_125.0,
        "execution_mode": "paper",
    }
    data.update(overrides)
    return ExecutionIntent(**data)


def test_hummingbot_adapter_builds_deterministic_paper_plan():
    adapter = HummingbotAdapter(connector="binance_paper_trade")

    plan = adapter.build_plan(_paper_intent(), _paper_decision())

    assert plan.model_dump() == {
        "engine": "hummingbot",
        "mode": "paper",
        "opportunity_id": "opp-17",
        "payload": {
            "connector": "binance_paper_trade",
            "market": "ETH-USDT",
            "paper_trade": True,
            "order": {
                "side": "buy",
                "type": "limit",
                "amount": 1.25,
                "price": 2_500.0,
                "notional_usd": 3_125.0,
            },
        },
    }


def test_freqtrade_adapter_builds_deterministic_dry_run_plan():
    adapter = FreqtradeAdapter(exchange_name="binance")

    plan = adapter.build_plan(_paper_intent(symbol="ETH/USDT"), _paper_decision())

    assert plan.model_dump() == {
        "engine": "freqtrade",
        "mode": "paper",
        "opportunity_id": "opp-17",
        "payload": {
            "dry_run": True,
            "exchange": {"name": "binance", "pair_whitelist": ["ETH/USDT"]},
            "order": {
                "pair": "ETH/USDT",
                "side": "buy",
                "order_type": "limit",
                "amount": 1.25,
                "rate": 2_500.0,
                "stake_amount": 3_125.0,
            },
        },
    }


@pytest.mark.parametrize("adapter", [HummingbotAdapter(), FreqtradeAdapter()])
def test_adapters_reject_blocked_risk_decisions(adapter):
    decision = _paper_decision(
        approved=False,
        execution_allowed=False,
        reason_codes=["capital_above_opportunity_limit"],
    )

    with pytest.raises(PermissionError, match="capital_above_opportunity_limit"):
        adapter.build_plan(_paper_intent(), decision)


@pytest.mark.parametrize("adapter", [HummingbotAdapter(), FreqtradeAdapter()])
def test_adapters_reject_live_execution_attempts(adapter):
    intent = _paper_intent(execution_mode="gated_live")
    decision = _paper_decision(
        execution_mode="gated_live",
        execution_allowed=True,
        live_execution_allowed=True,
    )

    with pytest.raises(PermissionError, match="live execution is not implemented"):
        adapter.build_plan(intent, decision)
