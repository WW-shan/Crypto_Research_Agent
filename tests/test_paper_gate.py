from __future__ import annotations

import math

import pytest
from pydantic import ValidationError


def _validation(**overrides):
    data = {
        "strategy_family": "funding_basis",
        "asset": "BTC/USDT",
        "timeframe": "1h",
        "status": "passed",
        "trade_count": 8,
        "net_return": 0.05,
        "max_drawdown": 0.08,
        "fee_adjusted_expectancy": 0.012,
        "slippage_adjusted_expectancy": 0.01,
        "blocked_reasons": [],
    }
    data.update(overrides)
    return data


def _candidate(**overrides):
    data = {
        "thesis": "Funding and basis research using public historical data",
        "capital_required_usd": 250.0,
        "data_needed": ["funding rates", "basis history"],
    }
    data.update(overrides)
    return data


def test_allows_candidate_with_positive_historical_evidence_and_charter_approval():
    from crypto_alpha_agent.risk.charter_guard import guard_generated_idea
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(),
        charter_decision=guard_generated_idea(_candidate()),
    )

    assert decision.allowed is True
    assert decision.reason_codes == []
    assert decision.action_mode == "paper"
    assert decision.historical_trade_count == 8
    assert decision.fee_adjusted_expectancy == 0.012
    assert decision.max_drawdown == 0.08
    assert decision.charter_reason_codes == []
    assert decision.paper_failure_reasons == []


def test_blocks_insufficient_historical_trades():
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(trade_count=4),
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["insufficient_historical_trades"]
    assert decision.historical_trade_count == 4


@pytest.mark.parametrize("expectancy", [0.0, -0.001])
def test_blocks_non_positive_fee_adjusted_expectancy(expectancy: float):
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(fee_adjusted_expectancy=expectancy),
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["non_positive_fee_adjusted_expectancy"]
    assert decision.fee_adjusted_expectancy == expectancy


def test_negative_min_fee_adjusted_expectancy_policy_is_invalid():
    from crypto_alpha_agent.risk.paper_gate import PaperEligibilityPolicy

    with pytest.raises(ValidationError):
        PaperEligibilityPolicy(min_fee_adjusted_expectancy=-0.001)


def test_default_policy_blocks_zero_fee_adjusted_expectancy():
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(fee_adjusted_expectancy=0.0),
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["non_positive_fee_adjusted_expectancy"]


@pytest.mark.parametrize("drawdown", [0.21, -0.21])
def test_blocks_drawdown_above_policy_limit_using_absolute_value(drawdown: float):
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(max_drawdown=drawdown),
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["drawdown_above_limit"]
    assert decision.max_drawdown == abs(drawdown)


def test_blocks_when_drawdown_is_missing_as_unbounded():
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(max_drawdown=None),
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["drawdown_unbounded"]
    assert decision.max_drawdown is None


def test_blocks_charter_violation_and_returns_charter_reason_codes():
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    decision = evaluate_paper_eligibility(
        _candidate(thesis="MEV mempool strategy", capital_required_usd=1_000.0),
        validation=_validation(),
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["charter_violation"]
    assert decision.charter_reason_codes == ["mev_or_mempool", "capital_above_budget"]


def test_blocks_failed_or_negative_paper_evidence_when_provided():
    from crypto_alpha_agent.evidence.paper import PaperEvidencePackage
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    evidence = PaperEvidencePackage(
        strategy_family="funding_basis",
        sample_size=2,
        closed_count=1,
        failed_count=1,
        net_pnl_usd=-1.5,
        hit_rate=0.0,
        max_drawdown_usd=2.0,
        failure_reasons=["exchange_unavailable"],
    )

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(),
        paper_evidence=evidence,
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["paper_evidence_failed"]
    assert decision.paper_failure_reasons == ["exchange_unavailable", "negative_net_pnl"]


def test_blocks_failed_paper_evidence_even_with_positive_net_pnl():
    from crypto_alpha_agent.evidence.paper import PaperEvidencePackage
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    evidence = PaperEvidencePackage(
        strategy_family="funding_basis",
        sample_size=2,
        closed_count=1,
        failed_count=1,
        net_pnl_usd=1.5,
        hit_rate=1.0,
        max_drawdown_usd=0.5,
    )

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(),
        paper_evidence=evidence,
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["paper_evidence_failed"]
    assert decision.paper_failure_reasons == []


def test_blocks_zero_paper_evidence_net_pnl():
    from crypto_alpha_agent.evidence.paper import PaperEvidencePackage
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    evidence = PaperEvidencePackage(
        strategy_family="funding_basis",
        sample_size=1,
        closed_count=1,
        failed_count=0,
        net_pnl_usd=0.0,
        hit_rate=0.0,
        max_drawdown_usd=0.0,
    )

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(),
        paper_evidence=evidence,
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["paper_evidence_failed"]
    assert decision.paper_failure_reasons == ["negative_net_pnl"]


def test_blocks_mismatched_paper_evidence_strategy_family():
    from crypto_alpha_agent.evidence.paper import PaperEvidencePackage
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    evidence = PaperEvidencePackage(
        strategy_family="stat_arb",
        sample_size=1,
        closed_count=1,
        failed_count=0,
        net_pnl_usd=1.0,
        hit_rate=1.0,
        max_drawdown_usd=0.1,
    )

    decision = evaluate_paper_eligibility(
        _candidate(),
        validation=_validation(strategy_family="funding_basis"),
        paper_evidence=evidence,
    )

    assert decision.allowed is False
    assert decision.reason_codes == ["paper_evidence_strategy_mismatch"]
    assert decision.paper_failure_reasons == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("fee_adjusted_expectancy", math.nan),
        ("fee_adjusted_expectancy", math.inf),
        ("max_drawdown", -math.inf),
    ],
)
def test_rejects_non_finite_validation_numeric_inputs(field: str, value: float):
    from crypto_alpha_agent.risk.paper_gate import evaluate_paper_eligibility

    with pytest.raises(ValidationError):
        evaluate_paper_eligibility(
            _candidate(),
            validation=_validation(**{field: value}),
        )
