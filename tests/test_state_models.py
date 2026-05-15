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
