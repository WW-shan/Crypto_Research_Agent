from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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
