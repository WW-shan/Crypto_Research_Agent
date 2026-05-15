from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis
from crypto_alpha_agent.backtest.vectorbt_runner import BacktestResult
from crypto_alpha_agent.risk.feasibility import FeasibilityScore

ReflectionOutcome = Literal["accept", "revise_strategy", "revise_hypothesis", "reject"]
ReflectionRoute = Literal["generate_hypothesis", "code_strategy", "update_memory", "__end__"]
ReflectionReasonCode = Literal[
    "insufficient_expectancy",
    "excessive_drawdown",
    "overfit",
    "costs_underestimated",
    "opportunity_not_repeatable",
    "missing_evidence",
]


class ReflectionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    assumption_failed: str = Field(min_length=1)
    evidence_missing: list[str] = Field(default_factory=list)
    likely_overfit: bool
    costs_underestimated: bool
    opportunity_repeatable: bool
    rejection_reasons: list[ReflectionReasonCode] = Field(default_factory=list)


class ReflectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    outcome: ReflectionOutcome
    assumption_failed: str | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    overfit: bool = False
    costs_underestimated: bool = False
    repeatable: bool = True
    rejection_reasons: list[ReflectionReasonCode] = Field(default_factory=list)
    next_route: ReflectionRoute | None = None


def reflect_strategy(
    *,
    hypothesis: AlphaHypothesis,
    backtest: BacktestResult,
    feasibility: FeasibilityScore | None = None,
    missing_evidence: list[str] | None = None,
) -> ReflectionDecision:
    missing_evidence = list(missing_evidence or [])

    repeatable = _is_repeatable(hypothesis=hypothesis, feasibility=feasibility)
    overfit = _is_overfit(backtest)
    costs_underestimated = _are_costs_underestimated(backtest)
    insufficient_expectancy = _is_insufficient_expectancy(backtest, feasibility)
    excessive_drawdown = _is_excessive_drawdown(backtest)

    rejection_reasons: list[ReflectionReasonCode] = []
    if missing_evidence:
        rejection_reasons.append("missing_evidence")
    if not repeatable:
        rejection_reasons.append("opportunity_not_repeatable")
    if overfit:
        rejection_reasons.append("overfit")
    if costs_underestimated:
        rejection_reasons.append("costs_underestimated")
    if insufficient_expectancy:
        rejection_reasons.append("insufficient_expectancy")
    if excessive_drawdown:
        rejection_reasons.append("excessive_drawdown")

    if missing_evidence or not repeatable:
        outcome = "revise_hypothesis"
        assumption_failed = _hypothesis_assumption_failed(missing_evidence, repeatable)
    elif overfit or costs_underestimated or insufficient_expectancy or excessive_drawdown:
        outcome = "revise_strategy"
        assumption_failed = _strategy_assumption_failed(overfit, costs_underestimated, insufficient_expectancy, excessive_drawdown)
    else:
        outcome = "accept"
        assumption_failed = "The strategy assumptions held up in backtest."

    report = ReflectionReport(
        assumption_failed=assumption_failed,
        evidence_missing=missing_evidence,
        likely_overfit=overfit,
        costs_underestimated=costs_underestimated,
        opportunity_repeatable=repeatable,
        rejection_reasons=rejection_reasons,
    )

    return route_reflection_decision(
        ReflectionDecision(
            outcome=outcome,
            assumption_failed=report.assumption_failed,
            missing_evidence=report.evidence_missing,
            overfit=report.likely_overfit,
            costs_underestimated=report.costs_underestimated,
            repeatable=report.opportunity_repeatable,
            rejection_reasons=report.rejection_reasons,
        )
    )


def route_reflection_decision(decision: ReflectionDecision) -> ReflectionDecision:
    next_route_by_outcome: dict[ReflectionOutcome, ReflectionRoute] = {
        "accept": "update_memory",
        "revise_strategy": "code_strategy",
        "revise_hypothesis": "generate_hypothesis",
        "reject": "generate_hypothesis",
    }
    return decision.model_copy(update={"next_route": next_route_by_outcome[decision.outcome]})


def _is_repeatable(*, hypothesis: AlphaHypothesis, feasibility: FeasibilityScore | None) -> bool:
    if feasibility is not None:
        if not feasibility.repeatable:
            return False
        if "opportunity_not_repeatable" in feasibility.reasons:
            return False
    return hypothesis.actionability == "executable"


def _is_overfit(backtest: BacktestResult) -> bool:
    return (
        (backtest.trade_count < 3 and backtest.net_return > 0.25)
        or (backtest.trade_count < 5 and backtest.win_rate >= 0.9)
        or (backtest.trade_count < 6 and backtest.net_return > 0.5 and backtest.win_rate >= 0.75)
    )


def _are_costs_underestimated(backtest: BacktestResult) -> bool:
    fee_gap = backtest.net_return - backtest.fee_adjusted_expectancy
    slippage_gap = backtest.net_return - backtest.slippage_adjusted_expectancy
    return fee_gap >= 0.05 or slippage_gap >= 0.05


def _is_insufficient_expectancy(backtest: BacktestResult, feasibility: FeasibilityScore | None) -> bool:
    if backtest.fee_adjusted_expectancy <= 0 or backtest.slippage_adjusted_expectancy <= 0:
        return True
    if backtest.net_return <= 0:
        return True
    if feasibility is not None and feasibility.expected_net_pnl_usd <= 0:
        return True
    return False


def _is_excessive_drawdown(backtest: BacktestResult) -> bool:
    return backtest.max_drawdown <= -0.2


def _hypothesis_assumption_failed(missing_evidence: list[str], repeatable: bool) -> str:
    if missing_evidence and not repeatable:
        return "The hypothesis lacked evidence and the opportunity does not appear repeatable."
    if missing_evidence:
        return "The hypothesis lacked independent evidence."
    return "The opportunity does not appear repeatable."


def _strategy_assumption_failed(
    overfit: bool,
    costs_underestimated: bool,
    insufficient_expectancy: bool,
    excessive_drawdown: bool,
) -> str:
    if overfit:
        return "The strategy appears overfit to too few trades."
    if costs_underestimated:
        return "Execution costs were underestimated."
    if excessive_drawdown:
        return "The strategy drawdown was too large."
    if insufficient_expectancy:
        return "The strategy did not produce enough expectancy after costs."
    return "The strategy assumptions did not hold."
