from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal

from crypto_alpha_agent.evidence.paper import PaperEvidencePackage
from crypto_alpha_agent.risk.rollout import RolloutEvaluation, RolloutReasonCode
from pydantic import BaseModel, ConfigDict, Field

ReadinessReasonCode = Literal[
    "rollout_gates_not_passed",
    "paper_evidence_failed",
    "insufficient_paper_sample",
    "human_approval_missing",
    "strategy_family_mismatch",
]
ReadinessChecklistStatus = Literal["pass", "fail"]
RequiredActionMode = Literal["gated_live_review_only"]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class TinyLiveReadinessChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: ReadinessChecklistStatus
    detail: str = Field(min_length=1)


class TinyLiveReadinessArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str = Field(min_length=1)
    ready_for_human_review: bool
    live_execution_enabled: Literal[False] = False
    required_action_mode: RequiredActionMode = "gated_live_review_only"
    reason_codes: list[ReadinessReasonCode] = Field(default_factory=list)
    checklist_items: list[TinyLiveReadinessChecklistItem] = Field(default_factory=list)
    rollout_reason_codes: list[RolloutReasonCode] = Field(default_factory=list)
    paper_failure_reasons: list[str] = Field(default_factory=list)
    max_notional_usd: NonNegativeFiniteFloat
    max_daily_loss_usd: NonNegativeFiniteFloat
    human_approval_reference: str | None = None


def generate_tiny_live_readiness_artifact(
    *,
    strategy_family: str,
    rollout_evaluation: RolloutEvaluation | Mapping[str, Any],
    paper_evidence: PaperEvidencePackage | Mapping[str, Any],
    human_approved: bool = False,
    human_approval_reference: str | None = None,
    max_notional_usd: float = 25.0,
    max_daily_loss_usd: float = 10.0,
) -> TinyLiveReadinessArtifact:
    rollout = (
        rollout_evaluation
        if isinstance(rollout_evaluation, RolloutEvaluation)
        else RolloutEvaluation.model_validate(rollout_evaluation)
    )
    paper = (
        paper_evidence
        if isinstance(paper_evidence, PaperEvidencePackage)
        else PaperEvidencePackage.model_validate(paper_evidence)
    )

    rollout_passed = rollout.eligible_for_tiny_live
    paper_positive_clean = (
        paper.failed_count == 0
        and not paper.failure_reasons
        and paper.net_pnl_usd > 0
    )
    sample_covers_rollout = (
        paper.sample_size > 0
        and paper.closed_count > 0
        and paper.sample_size >= rollout.observation_count
        and paper.closed_count >= rollout.observation_count
    )
    approval_reference = (
        human_approval_reference
        if human_approval_reference is not None and human_approval_reference.strip()
        else None
    )
    human_approval_recorded = human_approved is True and approval_reference is not None
    strategy_matches = paper.strategy_family == strategy_family

    reason_codes: list[ReadinessReasonCode] = []
    if not rollout_passed:
        reason_codes.append("rollout_gates_not_passed")
    if not paper_positive_clean:
        reason_codes.append("paper_evidence_failed")
    if not sample_covers_rollout:
        reason_codes.append("insufficient_paper_sample")
    if not human_approval_recorded:
        reason_codes.append("human_approval_missing")
    if not strategy_matches:
        reason_codes.append("strategy_family_mismatch")

    checklist_items = [
        TinyLiveReadinessChecklistItem(
            code="rollout_gates_passed",
            name="Rollout gates passed",
            status="pass" if rollout_passed else "fail",
            detail=(
                "Rollout gates passed."
                if rollout_passed
                else f"Rollout gates failed: {', '.join(rollout.reason_codes)}."
            ),
        ),
        TinyLiveReadinessChecklistItem(
            code="paper_evidence_positive_clean",
            name="Paper evidence positive and clean",
            status="pass" if paper_positive_clean else "fail",
            detail=(
                "Paper evidence is profitable and has no recorded failures."
                if paper_positive_clean
                else (
                    "Paper evidence is not clean: "
                    f"failed_count={paper.failed_count}, "
                    f"net_pnl_usd={paper.net_pnl_usd}, "
                    f"failure_reasons={paper.failure_reasons}."
                )
            ),
        ),
        TinyLiveReadinessChecklistItem(
            code="paper_sample_covers_rollout",
            name="Paper sample covers rollout observations",
            status="pass" if sample_covers_rollout else "fail",
            detail=(
                "Paper sample and closed counts cover rollout observations."
                if sample_covers_rollout
                else (
                    "Paper evidence sample is insufficient: "
                    f"sample_size={paper.sample_size}, "
                    f"closed_count={paper.closed_count}, "
                    f"rollout_observation_count={rollout.observation_count}."
                )
            ),
        ),
        TinyLiveReadinessChecklistItem(
            code="human_approval_recorded",
            name="Human approval recorded",
            status="pass" if human_approval_recorded else "fail",
            detail=(
                f"Human approval reference recorded: {approval_reference}."
                if human_approval_recorded
                else "Human approval and reference are required before review readiness."
            ),
        ),
        TinyLiveReadinessChecklistItem(
            code="strategy_family_matches",
            name="Strategy family matches",
            status="pass" if strategy_matches else "fail",
            detail=(
                f"Evidence strategy family matches requested family {strategy_family}."
                if strategy_matches
                else (
                    "Evidence strategy family mismatch: "
                    f"requested={strategy_family}, evidence={paper.strategy_family}."
                )
            ),
        ),
    ]

    return TinyLiveReadinessArtifact(
        strategy_family=strategy_family,
        ready_for_human_review=not reason_codes,
        live_execution_enabled=False,
        required_action_mode="gated_live_review_only",
        reason_codes=reason_codes,
        checklist_items=checklist_items,
        rollout_reason_codes=list(rollout.reason_codes),
        paper_failure_reasons=list(paper.failure_reasons),
        max_notional_usd=max_notional_usd,
        max_daily_loss_usd=max_daily_loss_usd,
        human_approval_reference=approval_reference,
    )
