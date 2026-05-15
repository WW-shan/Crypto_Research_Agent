from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_alpha_agent.agents.approvals import ManualApproval

ExecutionMode = Literal["research", "paper", "gated_live"]
RiskReasonCode = Literal[
    "capital_above_opportunity_limit",
    "daily_loss_limit_reached",
    "consecutive_failure_limit_reached",
    "venue_not_allowed",
    "forbidden_api_permission",
    "forbidden_wallet_permission",
    "api_permission_scope_too_broad",
    "wallet_permission_scope_too_broad",
    "manual_approval_required",
    "manual_approval_denied",
]

NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]

UNBOUNDED_PERMISSIONS = {"*", "all", "unbounded"}
FORBIDDEN_API_PERMISSIONS = {"admin", "withdraw"}
FORBIDDEN_WALLET_PERMISSIONS = {"admin", "withdraw"}
MODE_API_PERMISSIONS: dict[ExecutionMode, set[str]] = {
    "research": {"read"},
    "paper": {"read", "paper"},
    "gated_live": {"trade"},
}
MODE_WALLET_PERMISSIONS: dict[ExecutionMode, set[str]] = {
    "research": set(),
    "paper": {"paper-only"},
    "gated_live": {"no-withdraw"},
}


class PermissionScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    venue: str = Field(min_length=1)
    api_permissions: list[str] = Field(default_factory=list)
    wallet_permissions: list[str] = Field(default_factory=list)

    @field_validator("api_permissions", "wallet_permissions")
    @classmethod
    def _reject_unbounded_permissions(cls, permissions: list[str]) -> list[str]:
        normalized = [_normalize_permission(permission) for permission in permissions]
        if any(permission in UNBOUNDED_PERMISSIONS for permission in normalized):
            raise ValueError("unbounded permissions are not allowed")
        return normalized


class RiskPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    max_capital_per_opportunity_usd: NonNegativeFiniteFloat
    max_daily_loss_usd: NonNegativeFiniteFloat
    max_consecutive_failures: NonNegativeInt
    allowed_venues: list[str] = Field(min_length=1)

    @field_validator("allowed_venues")
    @classmethod
    def _normalize_allowed_venues(cls, venues: list[str]) -> list[str]:
        normalized = [_normalize_venue(venue) for venue in venues]
        if len(set(normalized)) != len(normalized):
            raise ValueError("allowed venues must be unique")
        return normalized


class RiskContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    opportunity_id: str = Field(min_length=1)
    execution_mode: ExecutionMode = "research"
    venue: str = Field(min_length=1)
    capital_required_usd: NonNegativeFiniteFloat
    daily_realized_pnl_usd: FiniteFloat = 0.0
    consecutive_failures: NonNegativeInt = 0
    permission_scope: PermissionScope
    manual_approval: ManualApproval | None = None

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, venue: str) -> str:
        return _normalize_venue(venue)


class RiskDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    opportunity_id: str
    approved: bool
    execution_mode: ExecutionMode
    execution_allowed: bool
    live_execution_allowed: bool
    reason_codes: list[RiskReasonCode] = Field(default_factory=list)

    def assert_can_execute(self) -> None:
        if not self.execution_allowed:
            reasons = ",".join(self.reason_codes) or "execution_not_allowed"
            raise PermissionError(f"risk guardian blocked execution: {reasons}")


class RiskGuardian:
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy

    def evaluate(self, context: RiskContext) -> RiskDecision:
        reasons: list[RiskReasonCode] = []

        if context.capital_required_usd > self.policy.max_capital_per_opportunity_usd:
            reasons.append("capital_above_opportunity_limit")

        daily_loss_usd = max(0.0, -context.daily_realized_pnl_usd)
        if daily_loss_usd >= self.policy.max_daily_loss_usd:
            reasons.append("daily_loss_limit_reached")

        if context.consecutive_failures >= self.policy.max_consecutive_failures:
            reasons.append("consecutive_failure_limit_reached")

        if context.execution_mode != "research" and context.venue not in self.policy.allowed_venues:
            reasons.append("venue_not_allowed")

        reasons.extend(_permission_reasons(context))
        reasons.extend(_approval_reasons(context))

        approved = not reasons
        execution_allowed = approved and context.execution_mode in {"paper", "gated_live"}
        live_execution_allowed = approved and context.execution_mode == "gated_live"

        return RiskDecision(
            opportunity_id=context.opportunity_id,
            approved=approved,
            execution_mode=context.execution_mode,
            execution_allowed=execution_allowed,
            live_execution_allowed=live_execution_allowed,
            reason_codes=reasons,
        )


def _permission_reasons(context: RiskContext) -> list[RiskReasonCode]:
    reasons: list[RiskReasonCode] = []
    scope = context.permission_scope

    if context.execution_mode != "research" and _normalize_venue(scope.venue) != context.venue:
        reasons.append("venue_not_allowed")

    if any(permission in FORBIDDEN_API_PERMISSIONS for permission in scope.api_permissions):
        reasons.append("forbidden_api_permission")
    elif not _is_subset(scope.api_permissions, MODE_API_PERMISSIONS[context.execution_mode]):
        reasons.append("api_permission_scope_too_broad")

    if any(permission in FORBIDDEN_WALLET_PERMISSIONS for permission in scope.wallet_permissions):
        reasons.append("forbidden_wallet_permission")
    elif not _is_subset(scope.wallet_permissions, MODE_WALLET_PERMISSIONS[context.execution_mode]):
        reasons.append("wallet_permission_scope_too_broad")

    return reasons


def _approval_reasons(context: RiskContext) -> list[RiskReasonCode]:
    if context.execution_mode != "gated_live":
        return []
    if context.manual_approval is None:
        return ["manual_approval_required"]
    if not context.manual_approval.approved:
        return ["manual_approval_denied"]
    return []


def _is_subset(values: Sequence[str], allowed_values: set[str]) -> bool:
    return set(values).issubset(allowed_values)


def _normalize_permission(permission: str) -> str:
    return permission.strip().lower()


def _normalize_venue(venue: str) -> str:
    return venue.strip().lower()
