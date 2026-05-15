import pytest
from pydantic import ValidationError

from crypto_alpha_agent.risk.ranker import RankingCandidate, rank_candidate_ideas


def test_ranking_filters_bad_candidates_and_prefers_quality_over_noise():
    candidates = [
        RankingCandidate(
            idea_id="broad-but-capital-heavy",
            expected_net_value_usd=95.0,
            confidence=0.70,
            repeatability=0.75,
            capital_required_usd=900.0,
            max_drawdown_usd=40.0,
            feasible=True,
        ),
        RankingCandidate(
            idea_id="efficient-repeatable",
            expected_net_value_usd=55.0,
            confidence=0.90,
            repeatability=0.95,
            capital_required_usd=110.0,
            max_drawdown_usd=20.0,
            feasible=True,
        ),
        RankingCandidate(
            idea_id="small-but-reliable",
            expected_net_value_usd=30.0,
            confidence=0.95,
            repeatability=0.90,
            capital_required_usd=80.0,
            max_drawdown_usd=12.0,
            feasible=True,
        ),
        RankingCandidate(
            idea_id="rejected-by-feasibility",
            expected_net_value_usd=250.0,
            confidence=0.99,
            repeatability=1.0,
            capital_required_usd=75.0,
            max_drawdown_usd=10.0,
            feasible=False,
        ),
        RankingCandidate(
            idea_id="one-shot",
            expected_net_value_usd=500.0,
            confidence=0.99,
            repeatability=0.0,
            capital_required_usd=75.0,
            max_drawdown_usd=10.0,
            feasible=True,
        ),
        RankingCandidate(
            idea_id="zero-expectancy",
            expected_net_value_usd=0.0,
            confidence=1.0,
            repeatability=1.0,
            capital_required_usd=10.0,
            max_drawdown_usd=1.0,
            feasible=True,
        ),
        RankingCandidate(
            idea_id="excessive-drawdown",
            expected_net_value_usd=75.0,
            confidence=0.90,
            repeatability=0.95,
            capital_required_usd=100.0,
            max_drawdown_usd=95.0,
            feasible=True,
        ),
    ]

    ranked = rank_candidate_ideas(candidates, top_n=3, max_drawdown_to_value=1.0)

    assert [item.idea_id for item in ranked] == [
        "efficient-repeatable",
        "small-but-reliable",
        "broad-but-capital-heavy",
    ]
    assert ranked[0].score > ranked[1].score > ranked[2].score


def test_top_n_selection_uses_deterministic_tie_breakers_regardless_of_input_order():
    candidates = [
        RankingCandidate(
            idea_id="gamma",
            expected_net_value_usd=50.0,
            confidence=0.80,
            repeatability=0.80,
            capital_required_usd=100.0,
            max_drawdown_usd=20.0,
        ),
        RankingCandidate(
            idea_id="alpha",
            expected_net_value_usd=50.0,
            confidence=0.80,
            repeatability=0.80,
            capital_required_usd=100.0,
            max_drawdown_usd=20.0,
        ),
        RankingCandidate(
            idea_id="beta",
            expected_net_value_usd=50.0,
            confidence=0.80,
            repeatability=0.80,
            capital_required_usd=100.0,
            max_drawdown_usd=20.0,
        ),
    ]

    forward = rank_candidate_ideas(candidates, top_n=2)
    reversed_order = rank_candidate_ideas(list(reversed(candidates)), top_n=2)

    assert [item.idea_id for item in forward] == ["alpha", "beta"]
    assert [item.idea_id for item in reversed_order] == ["alpha", "beta"]


def test_missing_capital_info_is_rejected():
    candidates = [
        RankingCandidate(
            idea_id="missing-capital",
            expected_net_value_usd=25.0,
            confidence=0.90,
            repeatability=0.90,
            capital_required_usd=None,
            max_drawdown_usd=5.0,
        )
    ]

    assert rank_candidate_ideas(candidates) == []


def test_ranking_candidate_rejects_coerced_inputs_and_unknown_fields():
    with pytest.raises(ValidationError):
        RankingCandidate(
            idea_id="coerced",
            expected_net_value_usd="25.0",
            confidence=0.90,
            repeatability=0.90,
            capital_required_usd=100.0,
            max_drawdown_usd=5.0,
        )

    with pytest.raises(ValidationError):
        RankingCandidate(
            idea_id="extra",
            expected_net_value_usd=25.0,
            confidence=0.90,
            repeatability=0.90,
            capital_required_usd=100.0,
            max_drawdown_usd=5.0,
            unsupported=True,
        )
