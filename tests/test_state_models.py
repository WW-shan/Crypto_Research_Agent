import pytest
from pydantic import ValidationError


def test_opportunity_event_fields():
    from crypto_alpha_agent.state import OpportunityEvent

    event = OpportunityEvent(
        source="dune",
        venue="binance",
        asset="BTC",
        edge_type="funding_rate",
        capital_required_usd=100.0,
        speed_dependency="low",
        rpc_dependency="none",
        expected_net_pnl_usd=12.5,
        confidence=0.74,
    )

    assert event.source == "dune"
    assert event.venue == "binance"
    assert event.asset == "BTC"
    assert event.edge_type == "funding_rate"
    assert event.capital_required_usd == 100.0
    assert event.speed_dependency == "low"
    assert event.rpc_dependency == "none"
    assert event.expected_net_pnl_usd == 12.5
    assert event.confidence > 0.7


def test_opportunity_event_rejects_unknown_fields():
    from crypto_alpha_agent.state import OpportunityEvent

    with pytest.raises(ValidationError):
        OpportunityEvent(
            source="dune",
            asset="BTC",
            edge_type="funding_rate",
            confidnce=0.74,
        )


def test_runtime_config_rejects_unknown_fields():
    from crypto_alpha_agent.config import RuntimeConfig

    with pytest.raises(ValidationError):
        RuntimeConfig(min_confidnce=0.7)


def test_opportunity_event_rejects_invalid_confidence():
    from crypto_alpha_agent.state import OpportunityEvent

    with pytest.raises(ValidationError):
        OpportunityEvent(
            source="dune",
            asset="BTC",
            edge_type="funding_rate",
            confidence=1.01,
        )


def test_opportunity_event_rejects_negative_capital_cost_and_risk_fields():
    from crypto_alpha_agent.state import OpportunityEvent

    base_event = {
        "source": "dune",
        "asset": "BTC",
        "edge_type": "funding_rate",
    }

    for field_name in (
        "capital_required_usd",
        "fee_estimate_usd",
        "gas_estimate_usd",
        "slippage_estimate_usd",
        "downside_usd",
    ):
        with pytest.raises(ValidationError):
            OpportunityEvent(**base_event, **{field_name: -0.01})


def test_opportunity_event_rejects_invalid_dependency_level():
    from crypto_alpha_agent.state import OpportunityEvent

    with pytest.raises(ValidationError):
        OpportunityEvent(
            source="dune",
            asset="BTC",
            edge_type="funding_rate",
            speed_dependency="urgent",
        )


def test_runtime_config_rejects_invalid_action_mode():
    from crypto_alpha_agent.config import RuntimeConfig

    with pytest.raises(ValidationError):
        RuntimeConfig(action_mode="live")
