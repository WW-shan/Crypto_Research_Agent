from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_alpha_agent.risk.charter_guard import (
    CharterGuardDecision,
    guard_generated_idea,
)

FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]

PaperEligibilityReasonCode = Literal[
    "insufficient_historical_trades",
    "non_positive_fee_adjusted_expectancy",
    "drawdown_unbounded",
    "drawdown_above_limit",
    "charter_violation",
    "paper_evidence_failed",
    "paper_evidence_strategy_mismatch",
]
ActionMode = Literal["paper"]


class PaperEligibilityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    min_historical_trades: NonNegativeInt = 5
    min_fee_adjusted_expectancy: NonNegativeFiniteFloat = 0.0
    max_drawdown: NonNegativeFiniteFloat = 0.20


class PaperEligibilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    allowed: bool
    reason_codes: list[PaperEligibilityReasonCode]
    action_mode: ActionMode = "paper"
    historical_trade_count: NonNegativeInt
    fee_adjusted_expectancy: FiniteFloat | None
    max_drawdown: FiniteFloat | None
    charter_reason_codes: list[str]
    paper_failure_reasons: list[str]


class _ValidationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str = Field(min_length=1)
    trade_count: NonNegativeInt
    fee_adjusted_expectancy: FiniteFloat | None = None
    max_drawdown: FiniteFloat | None = None

    @field_validator("max_drawdown")
    @classmethod
    def _normalize_max_drawdown(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return abs(value)


class _PaperEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str = Field(min_length=1)
    failed_count: NonNegativeInt
    net_pnl_usd: FiniteFloat
    failure_reasons: list[str] = Field(default_factory=list)

    @field_validator("failure_reasons")
    @classmethod
    def _dedupe_failure_reasons(cls, reasons: list[str]) -> list[str]:
        return _dedupe(reason for reason in reasons if reason)


def evaluate_paper_eligibility(
    candidate: Any,
    *,
    validation: Any,
    charter_decision: CharterGuardDecision | Mapping[str, Any] | None = None,
    paper_evidence: Any | None = None,
    policy: PaperEligibilityPolicy | Mapping[str, Any] | None = None,
) -> PaperEligibilityDecision:
    policy_model = _coerce_policy(policy)
    validation_model = _coerce_validation(validation)
    charter_model = _coerce_charter_decision(
        candidate,
        charter_decision=charter_decision,
    )
    paper_model = _coerce_paper_evidence(paper_evidence)

    reason_codes: list[PaperEligibilityReasonCode] = []

    if validation_model.trade_count < policy_model.min_historical_trades:
        reason_codes.append("insufficient_historical_trades")

    if (
        validation_model.fee_adjusted_expectancy is None
        or validation_model.fee_adjusted_expectancy
        <= policy_model.min_fee_adjusted_expectancy
    ):
        reason_codes.append("non_positive_fee_adjusted_expectancy")

    if validation_model.max_drawdown is None:
        reason_codes.append("drawdown_unbounded")
    elif validation_model.max_drawdown > policy_model.max_drawdown:
        reason_codes.append("drawdown_above_limit")

    charter_reason_codes = [str(reason) for reason in charter_model.reason_codes]
    if not charter_model.approved:
        reason_codes.append("charter_violation")

    paper_failure_reasons = _paper_failure_reasons(paper_model)
    if paper_model is not None and (paper_model.failed_count > 0 or paper_failure_reasons):
        reason_codes.append("paper_evidence_failed")
    if (
        paper_model is not None
        and paper_model.strategy_family != validation_model.strategy_family
    ):
        reason_codes.append("paper_evidence_strategy_mismatch")

    return PaperEligibilityDecision(
        allowed=not reason_codes,
        reason_codes=reason_codes,
        action_mode="paper",
        historical_trade_count=validation_model.trade_count,
        fee_adjusted_expectancy=validation_model.fee_adjusted_expectancy,
        max_drawdown=validation_model.max_drawdown,
        charter_reason_codes=charter_reason_codes,
        paper_failure_reasons=paper_failure_reasons,
    )


def _coerce_policy(
    policy: PaperEligibilityPolicy | Mapping[str, Any] | None,
) -> PaperEligibilityPolicy:
    if policy is None:
        return PaperEligibilityPolicy()
    if isinstance(policy, PaperEligibilityPolicy):
        return policy
    return PaperEligibilityPolicy.model_validate(policy)


def _coerce_validation(validation: Any) -> _ValidationEvidence:
    data = _field_mapping(
        validation,
        (
            "strategy_family",
            "trade_count",
            "fee_adjusted_expectancy",
            "max_drawdown",
        ),
    )
    return _ValidationEvidence.model_validate(data)


def _coerce_charter_decision(
    candidate: Any,
    *,
    charter_decision: CharterGuardDecision | Mapping[str, Any] | None,
) -> CharterGuardDecision:
    if charter_decision is None:
        return guard_generated_idea(candidate)
    if isinstance(charter_decision, CharterGuardDecision):
        return charter_decision
    return CharterGuardDecision.model_validate(charter_decision)


def _coerce_paper_evidence(paper_evidence: Any | None) -> _PaperEvidence | None:
    if paper_evidence is None:
        return None
    data = _field_mapping(
        paper_evidence,
        (
            "strategy_family",
            "failed_count",
            "net_pnl_usd",
            "failure_reasons",
        ),
    )
    return _PaperEvidence.model_validate(data)


def _field_mapping(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        source = value.model_dump(mode="python")
        return {field: source[field] for field in fields if field in source}
    if isinstance(value, Mapping):
        return {field: value[field] for field in fields if field in value}
    return {field: getattr(value, field) for field in fields if hasattr(value, field)}


def _paper_failure_reasons(paper_evidence: _PaperEvidence | None) -> list[str]:
    if paper_evidence is None:
        return []

    reasons = _dedupe(paper_evidence.failure_reasons)
    if paper_evidence.net_pnl_usd <= 0:
        reasons.append("negative_net_pnl")
    return _dedupe(reasons)


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
