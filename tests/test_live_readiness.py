from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.evidence.paper import PaperEvidencePackage
from crypto_alpha_agent.risk.rollout import RolloutEvaluation


def _passing_rollout(**overrides) -> RolloutEvaluation:
    data = {
        "eligible_for_tiny_live": True,
        "reason_codes": [],
        "observation_count": 30,
        "walk_forward_split_count": 3,
        "cost_adjusted_expectancy_usd": 4.25,
        "failure_rate": 0.0,
        "max_observed_loss_usd": 12.0,
    }
    data.update(overrides)
    return RolloutEvaluation(**data)


def _clean_paper(**overrides) -> PaperEvidencePackage:
    data = {
        "strategy_family": "funding_basis",
        "sample_size": 30,
        "closed_count": 30,
        "failed_count": 0,
        "net_pnl_usd": 127.5,
        "hit_rate": 0.7,
        "max_drawdown_usd": 8.0,
        "failure_reasons": [],
    }
    data.update(overrides)
    return PaperEvidencePackage(**data)


def test_generates_review_ready_artifact_without_enabling_live_execution():
    from crypto_alpha_agent.evidence.live_readiness import generate_tiny_live_readiness_artifact

    artifact = generate_tiny_live_readiness_artifact(
        strategy_family="funding_basis",
        rollout_evaluation=_passing_rollout(),
        paper_evidence=_clean_paper(),
        human_approved=True,
        human_approval_reference="approval-2026-05-16",
    )

    assert artifact.strategy_family == "funding_basis"
    assert artifact.ready_for_human_review is True
    assert artifact.live_execution_enabled is False
    assert artifact.required_action_mode == "gated_live_review_only"
    assert artifact.reason_codes == []
    assert artifact.rollout_reason_codes == []
    assert artifact.paper_failure_reasons == []
    assert artifact.max_notional_usd == 25.0
    assert artifact.max_daily_loss_usd == 10.0
    assert artifact.human_approval_reference == "approval-2026-05-16"

    checklist_by_code = {item.code: item for item in artifact.checklist_items}
    assert checklist_by_code["paper_evidence_positive_clean"].status == "pass"
    assert checklist_by_code["human_approval_recorded"].status == "pass"


def test_blocks_readiness_with_deterministic_reasons_and_checklist_details():
    from crypto_alpha_agent.evidence.live_readiness import generate_tiny_live_readiness_artifact

    artifact = generate_tiny_live_readiness_artifact(
        strategy_family="funding_basis",
        rollout_evaluation=_passing_rollout(
            eligible_for_tiny_live=False,
            reason_codes=["insufficient_sample_size"],
            observation_count=30,
        ),
        paper_evidence=_clean_paper(
            strategy_family="momentum",
            sample_size=12,
            closed_count=12,
            failed_count=1,
            net_pnl_usd=0.0,
            failure_reasons=["paper_order_rejected"],
        ),
    )

    assert artifact.ready_for_human_review is False
    assert artifact.live_execution_enabled is False
    assert artifact.reason_codes == [
        "rollout_gates_not_passed",
        "paper_evidence_failed",
        "insufficient_paper_sample",
        "human_approval_missing",
        "strategy_family_mismatch",
    ]
    assert artifact.rollout_reason_codes == ["insufficient_sample_size"]
    assert artifact.paper_failure_reasons == ["paper_order_rejected"]

    checklist_by_code = {item.code: item for item in artifact.checklist_items}
    assert checklist_by_code["rollout_gates_passed"].status == "fail"
    assert "insufficient_sample_size" in checklist_by_code["rollout_gates_passed"].detail
    assert checklist_by_code["paper_evidence_positive_clean"].status == "fail"
    assert "paper_order_rejected" in checklist_by_code["paper_evidence_positive_clean"].detail
    assert checklist_by_code["paper_sample_covers_rollout"].status == "fail"
    assert checklist_by_code["human_approval_recorded"].status == "fail"
    assert checklist_by_code["strategy_family_matches"].status == "fail"


def test_accepts_mapping_inputs_for_artifact_generation():
    from crypto_alpha_agent.evidence.live_readiness import generate_tiny_live_readiness_artifact

    artifact = generate_tiny_live_readiness_artifact(
        strategy_family="funding_basis",
        rollout_evaluation=_passing_rollout().model_dump(),
        paper_evidence=_clean_paper().model_dump(),
        human_approved=True,
        human_approval_reference="review-ticket-42",
        max_notional_usd=15.0,
        max_daily_loss_usd=5.0,
    )

    assert artifact.ready_for_human_review is True
    assert artifact.live_execution_enabled is False
    assert artifact.max_notional_usd == 15.0
    assert artifact.max_daily_loss_usd == 5.0


def test_human_approval_requires_boolean_true_and_nonblank_reference():
    from crypto_alpha_agent.evidence.live_readiness import generate_tiny_live_readiness_artifact

    string_approved_artifact = generate_tiny_live_readiness_artifact(
        strategy_family="funding_basis",
        rollout_evaluation=_passing_rollout(),
        paper_evidence=_clean_paper(),
        human_approved="true",  # type: ignore[arg-type]
        human_approval_reference="approval-2026-05-16",
    )
    blank_reference_artifact = generate_tiny_live_readiness_artifact(
        strategy_family="funding_basis",
        rollout_evaluation=_passing_rollout(),
        paper_evidence=_clean_paper(),
        human_approved=True,
        human_approval_reference="   ",
    )

    assert string_approved_artifact.ready_for_human_review is False
    assert string_approved_artifact.reason_codes == ["human_approval_missing"]
    assert blank_reference_artifact.ready_for_human_review is False
    assert blank_reference_artifact.reason_codes == ["human_approval_missing"]
    assert blank_reference_artifact.human_approval_reference is None


def test_module_exposes_artifact_api_without_live_order_functions():
    import crypto_alpha_agent.evidence.live_readiness as live_readiness

    function_names = [
        name
        for name, value in inspect.getmembers(live_readiness, inspect.isfunction)
        if value.__module__ == live_readiness.__name__
    ]

    forbidden_fragments = ("execute", "order", "trade", "place")
    assert function_names == ["generate_tiny_live_readiness_artifact"]
    assert not any(fragment in name for name in function_names for fragment in forbidden_fragments)


def test_evidence_package_exports_live_readiness_artifact_api():
    from crypto_alpha_agent.evidence import (
        TinyLiveReadinessArtifact,
        generate_tiny_live_readiness_artifact,
    )
    from crypto_alpha_agent.evidence.live_readiness import (
        TinyLiveReadinessArtifact as DirectArtifact,
        generate_tiny_live_readiness_artifact as direct_generate,
    )

    assert TinyLiveReadinessArtifact is DirectArtifact
    assert generate_tiny_live_readiness_artifact is direct_generate


def test_readiness_models_are_strict_and_reject_extra_fields():
    from crypto_alpha_agent.evidence.live_readiness import TinyLiveReadinessArtifact

    with pytest.raises(ValidationError):
        TinyLiveReadinessArtifact(
            strategy_family="funding_basis",
            ready_for_human_review=False,
            live_execution_enabled=False,
            required_action_mode="gated_live_review_only",
            reason_codes=[],
            checklist_items=[],
            rollout_reason_codes=[],
            paper_failure_reasons=[],
            max_notional_usd=25.0,
            max_daily_loss_usd=10.0,
            human_approval_reference=None,
            unexpected=True,
        )
