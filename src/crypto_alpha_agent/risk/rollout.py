from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
    from crypto_alpha_agent.evidence.paper import PaperEvidencePackage

RolloutReasonCode = Literal[
    "insufficient_sample_size",
    "insufficient_walk_forward_splits",
    "non_positive_cost_adjusted_expectancy",
    "failure_rate_above_limit",
    "duplicate_paper_trade_evidence",
    "duplicate_walk_forward_split",
    "unstable_walk_forward_performance",
    "manual_override_violation",
    "max_loss_budget_breached",
]

FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
FailureRateLimit = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
StringTuple = tuple[str, ...]
_CLOSED_OUTCOME_STATUSES = {"closed", "filled", "success"}
_FAILED_OUTCOME_STATUSES = {"failed", "rejected", "blocked"}
_LOSS_EVIDENCE_STATUSES = _CLOSED_OUTCOME_STATUSES | _FAILED_OUTCOME_STATUSES


class RolloutPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    min_paper_trade_count: PositiveInt = 30
    max_failure_rate: FailureRateLimit = 0.10
    min_walk_forward_splits: PositiveInt = 3
    min_walk_forward_expectancy_usd: FiniteFloat = 0.0
    max_loss_budget_usd: NonNegativeFiniteFloat = 100.0


class PaperTradeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    trade_id: str = Field(min_length=1)
    gross_pnl_usd: FiniteFloat
    total_cost_usd: NonNegativeFiniteFloat
    failed: bool = False
    manual_override_violation: bool = False

    @property
    def net_pnl_usd(self) -> float:
        return self.gross_pnl_usd - self.total_cost_usd


class WalkForwardSplit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    split_id: str = Field(min_length=1)
    cost_adjusted_expectancy_usd: FiniteFloat


class RolloutEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    eligible_for_tiny_live: bool
    reason_codes: list[RolloutReasonCode] = Field(default_factory=list)
    observation_count: NonNegativeInt
    walk_forward_split_count: NonNegativeInt
    cost_adjusted_expectancy_usd: FiniteFloat
    failure_rate: NonNegativeFiniteFloat
    max_observed_loss_usd: NonNegativeFiniteFloat


class StrategyEvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str = Field(min_length=1)
    validation_evidence_ids: StringTuple = Field(default_factory=tuple)
    validation_blocked_reasons: StringTuple = Field(default_factory=tuple)
    paper_outcome_ids: StringTuple = Field(default_factory=tuple)
    paper_failure_reasons: StringTuple = Field(default_factory=tuple)
    sample_size: NonNegativeInt
    closed_count: NonNegativeInt
    failed_count: NonNegativeInt
    blocked_count: NonNegativeInt = 0
    net_pnl_usd: FiniteFloat
    hit_rate: FailureRateLimit
    max_drawdown_usd: NonNegativeFiniteFloat
    rollout_observation_count: NonNegativeInt
    walk_forward_split_count: NonNegativeInt
    max_observed_loss_usd: NonNegativeFiniteFloat
    artifact_path: str | None = None
    evidence_package_path: str | None = None

    @field_validator("strategy_family")
    @classmethod
    def _normalize_strategy_family(cls, strategy_family: str) -> str:
        normalized = strategy_family.strip()
        if not normalized:
            raise ValueError("strategy_family must not be blank")
        return normalized

    def to_paper_evidence_package(self) -> PaperEvidencePackage:
        from crypto_alpha_agent.evidence.paper import PaperEvidencePackage

        return PaperEvidencePackage(
            strategy_family=self.strategy_family,
            sample_size=self.sample_size,
            closed_count=self.closed_count,
            failed_count=self.failed_count,
            blocked_count=self.blocked_count,
            net_pnl_usd=self.net_pnl_usd,
            hit_rate=self.hit_rate,
            max_drawdown_usd=self.max_drawdown_usd,
            failure_reasons=list(self.paper_failure_reasons),
        )


class RolloutReviewArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    command: Literal["rollout-review"] = "rollout-review"
    decision: Literal["blocked", "ready_for_human_review"]
    blocked_reasons: tuple[str, ...] = Field(default_factory=tuple)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
    readiness_artifact: dict[str, Any]
    rollout_evaluation: RolloutEvaluation
    evidence_package: StrategyEvidencePackage
    max_observed_loss_usd: NonNegativeFiniteFloat


def paper_outcomes_to_rollout_observations(
    outcomes: Iterable[PaperSimulationOutcome],
    *,
    include_failed_outcomes: bool = False,
) -> list[PaperTradeObservation]:
    observations: list[PaperTradeObservation] = []
    for outcome in outcomes:
        status = _outcome_status(outcome)
        if status in _CLOSED_OUTCOME_STATUSES:
            observations.append(
                PaperTradeObservation(
                    trade_id=outcome.outcome_id,
                    gross_pnl_usd=outcome.gross_pnl_usd,
                    total_cost_usd=outcome.fees_usd + outcome.slippage_usd,
                    failed=False,
                    manual_override_violation=False,
                )
            )
            continue

        if include_failed_outcomes and status in _FAILED_OUTCOME_STATUSES:
            observations.append(
                PaperTradeObservation(
                    trade_id=outcome.outcome_id,
                    gross_pnl_usd=outcome.gross_pnl_usd,
                    total_cost_usd=outcome.fees_usd + outcome.slippage_usd,
                    failed=True,
                    manual_override_violation=False,
                )
            )
    return observations


def validation_evidence_to_walk_forward_splits(
    evidence: Iterable[ValidationEvidence],
) -> list[WalkForwardSplit]:
    splits: list[WalkForwardSplit] = []
    seen_evidence_ids: set[str] = set()
    for item in evidence:
        if item.evidence_id in seen_evidence_ids:
            continue
        seen_evidence_ids.add(item.evidence_id)
        if not item.approved or item.blocked_reasons:
            continue
        for split_index in range(item.walk_forward_split_count):
            splits.append(
                WalkForwardSplit(
                    split_id=f"{item.evidence_id}:split:{split_index}",
                    cost_adjusted_expectancy_usd=item.slippage_adjusted_expectancy,
                )
            )
    return splits


def compute_max_observed_loss_usd(
    outcomes: Iterable[PaperSimulationOutcome],
) -> float:
    max_loss = 0.0
    for outcome in outcomes:
        if _outcome_status(outcome) not in _LOSS_EVIDENCE_STATUSES:
            continue
        max_loss = max(max_loss, outcome.max_drawdown_usd)
        if outcome.net_pnl_usd < 0:
            max_loss = max(max_loss, abs(outcome.net_pnl_usd))
        derived_net_pnl = outcome.gross_pnl_usd - outcome.fees_usd - outcome.slippage_usd
        if derived_net_pnl < 0:
            max_loss = max(max_loss, abs(derived_net_pnl))
    return float(max_loss)


def build_strategy_evidence_package(
    db_path: str | Path,
    strategy_family: str,
) -> StrategyEvidencePackage:
    from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
    from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger

    outcomes = PaperOutcomeLedger(db_path).load_outcomes(strategy_family=strategy_family)
    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence(
        strategy_family=strategy_family
    )
    observations = paper_outcomes_to_rollout_observations(
        outcomes,
        include_failed_outcomes=True,
    )
    walk_forward_splits = validation_evidence_to_walk_forward_splits(validation_evidence)
    closed_outcomes = [
        outcome
        for outcome in outcomes
        if _outcome_status(outcome) in _CLOSED_OUTCOME_STATUSES
    ]
    failed_outcomes = [
        outcome
        for outcome in outcomes
        if _outcome_status(outcome) in _FAILED_OUTCOME_STATUSES
    ]
    max_observed_loss = compute_max_observed_loss_usd(outcomes)

    return StrategyEvidencePackage(
        strategy_family=strategy_family,
        validation_evidence_ids=tuple(item.evidence_id for item in validation_evidence),
        validation_blocked_reasons=_dedupe_nonempty_strings(
            reason
            for item in validation_evidence
            for reason in item.blocked_reasons
        ),
        paper_outcome_ids=tuple(outcome.outcome_id for outcome in outcomes),
        paper_failure_reasons=_dedupe_nonempty_strings(
            reason
            for outcome in outcomes
            for reason in outcome.failure_reasons
        ),
        sample_size=len(outcomes),
        closed_count=len(closed_outcomes),
        failed_count=len(failed_outcomes),
        blocked_count=sum(
            1 for outcome in outcomes if _outcome_status(outcome) == "blocked"
        ),
        net_pnl_usd=float(sum(outcome.net_pnl_usd for outcome in outcomes)),
        hit_rate=_paper_hit_rate(closed_outcomes),
        max_drawdown_usd=max_observed_loss,
        rollout_observation_count=len(observations),
        walk_forward_split_count=len(walk_forward_splits),
        max_observed_loss_usd=max_observed_loss,
    )


def build_rollout_review_artifact(
    db_path: str | Path,
    strategy_family: str,
    human_approved: bool = False,
    human_approval_reference: str | None = None,
    max_notional_usd: float = 25.0,
    max_daily_loss_usd: float = 10.0,
) -> RolloutReviewArtifact:
    from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
    from crypto_alpha_agent.evidence.live_readiness import (
        generate_tiny_live_readiness_artifact,
    )
    from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger

    outcomes = PaperOutcomeLedger(db_path).load_outcomes(strategy_family=strategy_family)
    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence(
        strategy_family=strategy_family
    )
    observations = paper_outcomes_to_rollout_observations(
        outcomes,
        include_failed_outcomes=True,
    )
    walk_forward_splits = validation_evidence_to_walk_forward_splits(validation_evidence)
    evidence_package = build_strategy_evidence_package(db_path, strategy_family)
    rollout_evaluation = evaluate_rollout(
        policy=RolloutPolicy(max_loss_budget_usd=max_daily_loss_usd),
        observations=observations,
        walk_forward_splits=walk_forward_splits,
        max_observed_loss_usd=evidence_package.max_observed_loss_usd,
    )
    readiness_artifact = generate_tiny_live_readiness_artifact(
        strategy_family=strategy_family,
        rollout_evaluation=rollout_evaluation,
        paper_evidence=evidence_package.to_paper_evidence_package(),
        human_approved=human_approved,
        human_approval_reference=human_approval_reference,
        max_notional_usd=max_notional_usd,
        max_daily_loss_usd=max_daily_loss_usd,
    )

    return RolloutReviewArtifact(
        decision=(
            "ready_for_human_review"
            if readiness_artifact.ready_for_human_review
            else "blocked"
        ),
        blocked_reasons=_dedupe_nonempty_strings(
            [
                *rollout_evaluation.reason_codes,
                *readiness_artifact.reason_codes,
            ]
        ),
        readiness_artifact=readiness_artifact.model_dump(mode="json"),
        rollout_evaluation=rollout_evaluation,
        evidence_package=evidence_package,
        max_observed_loss_usd=evidence_package.max_observed_loss_usd,
    )


def evaluate_rollout(
    *,
    policy: RolloutPolicy,
    observations: list[PaperTradeObservation],
    walk_forward_splits: list[WalkForwardSplit],
    max_observed_loss_usd: float,
) -> RolloutEvaluation:
    reasons: list[RolloutReasonCode] = []
    observation_count = len(observations)
    split_count = len(walk_forward_splits)
    expectancy = _cost_adjusted_expectancy(observations)
    failure_rate = _failure_rate(observations)

    if observation_count < policy.min_paper_trade_count:
        reasons.append("insufficient_sample_size")

    if split_count < policy.min_walk_forward_splits:
        reasons.append("insufficient_walk_forward_splits")

    if _has_duplicate_ids(observation.trade_id for observation in observations):
        reasons.append("duplicate_paper_trade_evidence")

    if _has_duplicate_ids(split.split_id for split in walk_forward_splits):
        reasons.append("duplicate_walk_forward_split")

    if observation_count > 0 and expectancy <= 0:
        reasons.append("non_positive_cost_adjusted_expectancy")

    if observation_count > 0 and failure_rate > policy.max_failure_rate:
        reasons.append("failure_rate_above_limit")

    if any(split.cost_adjusted_expectancy_usd <= policy.min_walk_forward_expectancy_usd for split in walk_forward_splits):
        reasons.append("unstable_walk_forward_performance")

    if any(observation.manual_override_violation for observation in observations):
        reasons.append("manual_override_violation")

    if max_observed_loss_usd > policy.max_loss_budget_usd:
        reasons.append("max_loss_budget_breached")

    return RolloutEvaluation(
        eligible_for_tiny_live=not reasons,
        reason_codes=reasons,
        observation_count=observation_count,
        walk_forward_split_count=split_count,
        cost_adjusted_expectancy_usd=expectancy,
        failure_rate=failure_rate,
        max_observed_loss_usd=max_observed_loss_usd,
    )


def _cost_adjusted_expectancy(observations: list[PaperTradeObservation]) -> float:
    if not observations:
        return 0.0
    return sum(observation.net_pnl_usd for observation in observations) / len(observations)


def _failure_rate(observations: list[PaperTradeObservation]) -> float:
    if not observations:
        return 0.0
    return sum(1 for observation in observations if observation.failed) / len(observations)


def _has_duplicate_ids(ids) -> bool:
    seen: set[str] = set()
    for evidence_id in ids:
        if evidence_id in seen:
            return True
        seen.add(evidence_id)
    return False


def _outcome_status(outcome: PaperSimulationOutcome) -> str:
    return outcome.status.strip().lower()


def _paper_hit_rate(closed_outcomes: list[PaperSimulationOutcome]) -> float:
    if not closed_outcomes:
        return 0.0
    wins = sum(1 for outcome in closed_outcomes if outcome.net_pnl_usd > 0)
    return wins / len(closed_outcomes)


def _dedupe_nonempty_strings(values: Iterable[str]) -> StringTuple:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized)
    return tuple(deduped)
