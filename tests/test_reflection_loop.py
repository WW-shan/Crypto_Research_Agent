def _hypothesis():
    from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis, DisconfirmationCriterion, EvidenceBundle

    return AlphaHypothesis(
        source="thegraph",
        category="chain",
        asset="ARB",
        what_changed="holder concentration increased",
        why_it_might_be_edge="larger wallets may front-run passive flows",
        evidence=[
            EvidenceBundle(
                source="thegraph",
                category="chain",
                asset="ARB",
                metric="holder_concentration",
                value=0.84,
                signal_evidence=["top wallets accumulated"],
                raw={"query": "holders"},
                anomaly_classification="statistical_outlier",
                anomaly_score=18.0,
                executable=True,
                persistence_seconds=1_800,
            )
        ],
        expected_persistence_seconds=1_800,
        disconfirmation_tests=["invalidate if concentration normalizes on the next snapshot"],
        disconfirmation_criteria=[
            DisconfirmationCriterion(
                metric="holder_concentration",
                operator="lte",
                threshold=0.5,
                window_seconds=1_800,
                reason="invalidate if concentration normalizes",
            )
        ],
        action_mode="research_only",
        actionability="executable",
    )


def test_poor_backtest_rejects_with_concrete_reasons():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
    from crypto_alpha_agent.risk.feasibility import FeasibilityScore

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=-0.12,
            max_drawdown=-0.34,
            win_rate=0.33,
            trade_count=9,
            average_holding_time=4.0,
            fee_adjusted_expectancy=-0.03,
            slippage_adjusted_expectancy=-0.05,
        ),
        feasibility=FeasibilityScore(
            approved=False,
            score=28,
            reasons=["net_pnl_below_minimum", "downside_above_limit"],
            capital_required_usd=100.0,
            current_capital_usd=300.0,
            expected_net_pnl_usd=4.0,
            max_downside_usd=120.0,
            repeatable=True,
            speed_dependency="low",
            rpc_dependency="low",
        ),
    )

    assert decision.outcome in {"reject", "revise_strategy"}
    assert decision.assumption_failed is not None
    assert "drawdown" in decision.rejection_reasons or "insufficient_expectancy" in decision.rejection_reasons


def test_missing_evidence_hypothesis_revises_hypothesis_and_reports_gap():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
    from crypto_alpha_agent.risk.feasibility import FeasibilityScore

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.08,
            max_drawdown=-0.04,
            win_rate=0.6,
            trade_count=8,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.02,
            slippage_adjusted_expectancy=0.02,
        ),
        feasibility=FeasibilityScore(
            approved=False,
            score=35,
            reasons=["opportunity_not_repeatable"],
            capital_required_usd=100.0,
            current_capital_usd=300.0,
            expected_net_pnl_usd=15.0,
            max_downside_usd=30.0,
            repeatable=False,
            speed_dependency="low",
            rpc_dependency="low",
        ),
        missing_evidence=["independent venue data", "longer history"],
    )

    assert decision.outcome == "revise_hypothesis"
    assert decision.missing_evidence == ["independent venue data", "longer history"]
    assert decision.next_route == "generate_hypothesis"


def test_overfit_conditions_are_detected():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.72,
            max_drawdown=-0.03,
            win_rate=1.0,
            trade_count=2,
            average_holding_time=1.0,
            fee_adjusted_expectancy=0.31,
            slippage_adjusted_expectancy=0.30,
        ),
    )

    assert decision.overfit is True
    assert "overfit" in decision.rejection_reasons


def test_underestimated_costs_are_detected():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.20,
            max_drawdown=-0.05,
            win_rate=0.67,
            trade_count=6,
            average_holding_time=3.0,
            fee_adjusted_expectancy=-0.01,
            slippage_adjusted_expectancy=-0.04,
        ),
    )

    assert decision.costs_underestimated is True
    assert "costs_underestimated" in decision.rejection_reasons


def test_multi_trade_positive_strategy_does_not_compare_cumulative_return_to_expectancy_for_costs():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.28,
            max_drawdown=-0.05,
            win_rate=0.58,
            trade_count=18,
            average_holding_time=3.0,
            fee_adjusted_expectancy=0.018,
            slippage_adjusted_expectancy=0.016,
        ),
    )

    assert decision.costs_underestimated is False
    assert "costs_underestimated" not in decision.rejection_reasons


def test_slippage_expectancy_materially_below_fee_expectancy_flags_underestimated_costs():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.08,
            max_drawdown=-0.03,
            win_rate=0.55,
            trade_count=12,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.071,
            slippage_adjusted_expectancy=0.015,
        ),
    )

    assert decision.costs_underestimated is True
    assert "costs_underestimated" in decision.rejection_reasons


def test_rejected_feasibility_routes_to_strategy_revision_with_machine_readable_reasons():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
    from crypto_alpha_agent.risk.feasibility import FeasibilityScore

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.14,
            max_drawdown=-0.06,
            win_rate=0.62,
            trade_count=14,
            average_holding_time=2.5,
            fee_adjusted_expectancy=0.03,
            slippage_adjusted_expectancy=0.028,
        ),
        feasibility=FeasibilityScore(
            approved=False,
            score=15,
            reasons=["capital_above_budget", "speed_dependency_too_high", "rpc_dependency_too_high"],
            capital_required_usd=700.0,
            current_capital_usd=300.0,
            expected_net_pnl_usd=25.0,
            max_downside_usd=70.0,
            repeatable=True,
            speed_dependency="high",
            rpc_dependency="high",
        ),
    )

    assert decision.outcome == "revise_strategy"
    assert decision.next_route == "code_strategy"
    assert "capital_above_budget" in decision.rejection_reasons
    assert "speed_dependency_too_high" in decision.rejection_reasons
    assert "rpc_dependency_too_high" in decision.rejection_reasons


def test_downside_feasibility_rejection_revises_strategy_even_when_backtest_is_positive():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
    from crypto_alpha_agent.risk.feasibility import FeasibilityScore

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.11,
            max_drawdown=-0.08,
            win_rate=0.57,
            trade_count=10,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.024,
            slippage_adjusted_expectancy=0.023,
        ),
        feasibility=FeasibilityScore(
            approved=False,
            score=45,
            reasons=["downside_above_limit"],
            capital_required_usd=120.0,
            current_capital_usd=300.0,
            expected_net_pnl_usd=20.0,
            max_downside_usd=150.0,
            repeatable=True,
            speed_dependency="low",
            rpc_dependency="low",
        ),
    )

    assert decision.outcome == "revise_strategy"
    assert "excessive_drawdown" in decision.rejection_reasons


def test_blocked_repeatable_opportunity_is_not_marked_non_repeatable_from_actionability():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult

    hypothesis = _hypothesis().model_copy(
        update={
            "actionability": "blocked",
            "action_mode": "research_only",
        }
    )

    decision = reflect_strategy(
        hypothesis=hypothesis,
        backtest=BacktestResult(
            net_return=0.09,
            max_drawdown=-0.04,
            win_rate=0.6,
            trade_count=9,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.022,
            slippage_adjusted_expectancy=0.021,
        ),
    )

    assert isinstance(hypothesis, AlphaHypothesis)
    assert decision.repeatable is True
    assert "opportunity_not_repeatable" not in decision.rejection_reasons


def test_non_repeatable_opportunity_is_detected_from_feasibility():
    from crypto_alpha_agent.agents.reflector import reflect_strategy
    from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
    from crypto_alpha_agent.risk.feasibility import FeasibilityScore

    decision = reflect_strategy(
        hypothesis=_hypothesis(),
        backtest=BacktestResult(
            net_return=0.05,
            max_drawdown=-0.02,
            win_rate=0.5,
            trade_count=7,
            average_holding_time=2.0,
            fee_adjusted_expectancy=0.01,
            slippage_adjusted_expectancy=0.01,
        ),
        feasibility=FeasibilityScore(
            approved=False,
            score=41,
            reasons=["opportunity_not_repeatable"],
            capital_required_usd=100.0,
            current_capital_usd=300.0,
            expected_net_pnl_usd=12.0,
            max_downside_usd=25.0,
            repeatable=False,
            speed_dependency="low",
            rpc_dependency="low",
        ),
    )

    assert decision.repeatable is False
    assert "opportunity_not_repeatable" in decision.rejection_reasons


def test_route_helper_maps_revise_outcomes_to_next_graph_nodes():
    from crypto_alpha_agent.agents.reflector import ReflectionDecision, route_reflection_decision

    assert route_reflection_decision(ReflectionDecision(outcome="revise_strategy")).next_route == "code_strategy"
    assert route_reflection_decision(ReflectionDecision(outcome="revise_hypothesis")).next_route == "generate_hypothesis"
