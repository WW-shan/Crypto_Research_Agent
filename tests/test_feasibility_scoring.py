def test_low_capital_high_speed_trade_is_rejected():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=5000,
        current_capital_usd=300,
        speed_dependency="high",
        rpc_dependency="high",
        expected_net_pnl_usd=8,
    )

    assert score.approved is False


def test_opportunity_within_small_capital_constraints_is_approved():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=120,
        current_capital_usd=300,
        speed_dependency="low",
        rpc_dependency="low",
        expected_net_pnl_usd=35,
        max_downside_usd=40,
        repeatable=True,
    )

    assert score.approved is True
    assert score.reasons == []
    assert score.score > 0


def test_capital_above_budget_is_rejected():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=301,
        current_capital_usd=300,
        expected_net_pnl_usd=50,
    )

    assert score.approved is False
    assert "capital_above_budget" in score.reasons


def test_high_speed_dependency_is_rejected_by_default():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=100,
        current_capital_usd=300,
        speed_dependency="high",
        expected_net_pnl_usd=50,
    )

    assert score.approved is False
    assert "speed_dependency_too_high" in score.reasons


def test_high_rpc_dependency_is_rejected_by_default():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=100,
        current_capital_usd=300,
        rpc_dependency="high",
        expected_net_pnl_usd=50,
    )

    assert score.approved is False
    assert "rpc_dependency_too_high" in score.reasons


def test_net_pnl_below_minimum_cost_of_ownership_is_rejected():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=100,
        current_capital_usd=300,
        expected_net_pnl_usd=4.99,
        min_net_pnl_usd=5,
    )

    assert score.approved is False
    assert "net_pnl_below_minimum" in score.reasons


def test_non_repeatable_opportunity_is_rejected_by_default():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=100,
        current_capital_usd=300,
        expected_net_pnl_usd=50,
        repeatable=False,
    )

    assert score.approved is False
    assert "opportunity_not_repeatable" in score.reasons


def test_unbounded_downside_is_rejected():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=100,
        current_capital_usd=300,
        expected_net_pnl_usd=50,
        max_downside_usd=None,
    )

    assert score.approved is False
    assert "downside_unbounded" in score.reasons


def test_downside_above_threshold_is_rejected():
    from crypto_alpha_agent.risk.feasibility import score_feasibility

    score = score_feasibility(
        capital_required_usd=100,
        current_capital_usd=300,
        expected_net_pnl_usd=50,
        max_downside_usd=125,
        max_allowed_downside_usd=100,
    )

    assert score.approved is False
    assert "downside_above_limit" in score.reasons
