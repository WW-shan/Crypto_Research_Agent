import pytest
from pydantic import ValidationError

from crypto_alpha_agent.risk.rollout import (
    PaperTradeObservation,
    RolloutPolicy,
    WalkForwardSplit,
    evaluate_rollout,
)


def _passing_observations() -> list[PaperTradeObservation]:
    return [
        PaperTradeObservation(
            trade_id=f"paper-{index}",
            gross_pnl_usd=12.0,
            total_cost_usd=2.0,
            failed=False,
            manual_override_violation=False,
        )
        for index in range(30)
    ]


def _passing_splits() -> list[WalkForwardSplit]:
    return [
        WalkForwardSplit(split_id="wf-1", cost_adjusted_expectancy_usd=2.4),
        WalkForwardSplit(split_id="wf-2", cost_adjusted_expectancy_usd=2.1),
        WalkForwardSplit(split_id="wf-3", cost_adjusted_expectancy_usd=2.3),
    ]


def _passing_evaluation(**overrides):
    data = {
        "policy": RolloutPolicy(),
        "observations": _passing_observations(),
        "walk_forward_splits": _passing_splits(),
        "max_observed_loss_usd": 75.0,
    }
    data.update(overrides)
    return evaluate_rollout(**data)


def test_default_policy_blocks_tiny_live_without_evidence():
    evaluation = evaluate_rollout(
        policy=RolloutPolicy(),
        observations=[],
        walk_forward_splits=[],
        max_observed_loss_usd=0.0,
    )

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == [
        "insufficient_sample_size",
        "insufficient_walk_forward_splits",
    ]


def test_insufficient_sample_size_blocks_tiny_live():
    evaluation = _passing_evaluation(observations=_passing_observations()[:29])

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == ["insufficient_sample_size"]


def test_non_positive_cost_adjusted_expectancy_blocks_tiny_live():
    observations = [
        PaperTradeObservation(
            trade_id=f"paper-{index}",
            gross_pnl_usd=1.0,
            total_cost_usd=1.0,
        )
        for index in range(30)
    ]

    evaluation = _passing_evaluation(observations=observations)

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == ["non_positive_cost_adjusted_expectancy"]
    assert evaluation.cost_adjusted_expectancy_usd == 0.0


def test_high_failure_rate_blocks_tiny_live():
    observations = _passing_observations()
    for observation in observations[:4]:
        observation.failed = True

    evaluation = _passing_evaluation(observations=observations)

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == ["failure_rate_above_limit"]
    assert evaluation.failure_rate == pytest.approx(4 / 30)


def test_unstable_walk_forward_split_blocks_tiny_live():
    splits = [
        WalkForwardSplit(split_id="wf-1", cost_adjusted_expectancy_usd=2.0),
        WalkForwardSplit(split_id="wf-2", cost_adjusted_expectancy_usd=-0.01),
        WalkForwardSplit(split_id="wf-3", cost_adjusted_expectancy_usd=2.0),
    ]

    evaluation = _passing_evaluation(walk_forward_splits=splits)

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == ["unstable_walk_forward_performance"]


def test_manual_override_violation_blocks_tiny_live():
    observations = _passing_observations()
    observations[0].manual_override_violation = True

    evaluation = _passing_evaluation(observations=observations)

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == ["manual_override_violation"]


def test_max_loss_budget_breach_blocks_tiny_live():
    evaluation = _passing_evaluation(max_observed_loss_usd=100.01)

    assert evaluation.eligible_for_tiny_live is False
    assert evaluation.reason_codes == ["max_loss_budget_breached"]


def test_all_rollout_gates_passing_allows_tiny_live_eligibility_only():
    evaluation = _passing_evaluation()

    assert evaluation.eligible_for_tiny_live is True
    assert evaluation.reason_codes == []
    assert evaluation.observation_count == 30
    assert evaluation.cost_adjusted_expectancy_usd == 10.0
    assert evaluation.failure_rate == 0.0
    assert evaluation.max_observed_loss_usd == 75.0


def test_rollout_models_are_strict_and_reject_coerced_values():
    with pytest.raises(ValidationError):
        RolloutPolicy(min_paper_trade_count="30")

    with pytest.raises(ValidationError):
        PaperTradeObservation(
            trade_id="paper-1",
            gross_pnl_usd="12.0",
            total_cost_usd=2.0,
        )
