from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.config import ActionMode
from crypto_alpha_agent.state import DependencyLevel

RejectReason = Literal[
    "capital_above_budget",
    "speed_dependency_too_high",
    "rpc_dependency_too_high",
    "net_pnl_below_minimum",
    "opportunity_not_repeatable",
    "downside_unbounded",
    "downside_above_limit",
]


class FeasibilityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    score: int = Field(ge=0, le=100)
    reasons: list[RejectReason] = Field(default_factory=list)
    capital_required_usd: float = Field(ge=0)
    current_capital_usd: float = Field(ge=0)
    expected_net_pnl_usd: float
    max_downside_usd: float | None = Field(default=None, ge=0)
    repeatable: bool
    speed_dependency: DependencyLevel
    rpc_dependency: DependencyLevel
    action_mode: ActionMode = "research_only"


def score_feasibility(
    *,
    capital_required_usd: float,
    current_capital_usd: float,
    expected_net_pnl_usd: float,
    max_downside_usd: float | None = None,
    repeatable: bool = True,
    speed_dependency: DependencyLevel = "none",
    rpc_dependency: DependencyLevel = "none",
    action_mode: ActionMode = "research_only",
    min_net_pnl_usd: float = 10.0,
    min_net_pnl_ratio: float = 0.02,
    max_allowed_downside_usd: float = 100.0,
    allow_high_speed: bool = False,
    allow_high_rpc: bool = False,
    require_repeatable: bool = True,
) -> FeasibilityScore:
    reasons: list[RejectReason] = []

    if capital_required_usd > current_capital_usd:
        reasons.append("capital_above_budget")

    if speed_dependency == "high" and not allow_high_speed:
        reasons.append("speed_dependency_too_high")

    if rpc_dependency == "high" and not allow_high_rpc:
        reasons.append("rpc_dependency_too_high")

    minimum_net_pnl_usd = max(min_net_pnl_usd, capital_required_usd * min_net_pnl_ratio)
    if expected_net_pnl_usd < minimum_net_pnl_usd:
        reasons.append("net_pnl_below_minimum")

    if require_repeatable and not repeatable:
        reasons.append("opportunity_not_repeatable")

    if max_downside_usd is None:
        reasons.append("downside_unbounded")
    elif max_downside_usd > max_allowed_downside_usd:
        reasons.append("downside_above_limit")

    approved = not reasons
    score = _calculate_score(
        approved=approved,
        reasons=reasons,
        capital_required_usd=capital_required_usd,
        current_capital_usd=current_capital_usd,
        expected_net_pnl_usd=expected_net_pnl_usd,
        max_downside_usd=max_downside_usd,
    )

    return FeasibilityScore(
        approved=approved,
        score=score,
        reasons=reasons,
        capital_required_usd=capital_required_usd,
        current_capital_usd=current_capital_usd,
        expected_net_pnl_usd=expected_net_pnl_usd,
        max_downside_usd=max_downside_usd,
        repeatable=repeatable,
        speed_dependency=speed_dependency,
        rpc_dependency=rpc_dependency,
        action_mode=action_mode,
    )


def _calculate_score(
    *,
    approved: bool,
    reasons: list[RejectReason],
    capital_required_usd: float,
    current_capital_usd: float,
    expected_net_pnl_usd: float,
    max_downside_usd: float | None,
) -> int:
    if not approved:
        return max(0, 60 - (len(reasons) * 15))

    capital_utilization = capital_required_usd / current_capital_usd if current_capital_usd else 1
    risk_penalty = 0
    if max_downside_usd:
        reward_to_risk = expected_net_pnl_usd / max_downside_usd
        risk_penalty = 10 if reward_to_risk < 1 else 0

    return max(1, min(100, round(100 - (capital_utilization * 20) - risk_penalty)))
