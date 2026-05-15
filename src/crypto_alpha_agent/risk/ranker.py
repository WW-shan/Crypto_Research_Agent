from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RankingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    idea_id: str = Field(min_length=1)
    expected_net_value_usd: float
    confidence: float = Field(ge=0, le=1)
    repeatability: float = Field(ge=0, le=1)
    capital_required_usd: float | None = Field(default=None, gt=0)
    max_drawdown_usd: float | None = Field(default=None, ge=0)
    feasible: bool = True
    opportunity_id: str | None = None
    hypothesis_id: str | None = None
    backtest_id: str | None = None
    memory_key: str | None = None


class RankedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    idea_id: str
    score: float
    expected_net_value_usd: float
    confidence: float
    repeatability: float
    capital_required_usd: float
    capital_efficiency: float
    max_drawdown_usd: float | None = None
    opportunity_id: str | None = None
    hypothesis_id: str | None = None
    backtest_id: str | None = None
    memory_key: str | None = None


CandidateInput = RankingCandidate | Mapping[str, Any]


def rank_candidate_ideas(
    candidates: Sequence[CandidateInput],
    *,
    top_n: int = 5,
    max_drawdown_to_value: float = 2.0,
) -> list[RankedCandidate]:
    if top_n <= 0:
        return []

    scored = [
        _score_candidate(_coerce_candidate(candidate), max_drawdown_to_value=max_drawdown_to_value)
        for candidate in candidates
    ]
    eligible = [candidate for candidate in scored if candidate is not None]

    return sorted(
        eligible,
        key=lambda candidate: (
            -candidate.score,
            -candidate.expected_net_value_usd,
            -candidate.confidence,
            -candidate.repeatability,
            -candidate.capital_efficiency,
            candidate.idea_id,
        ),
    )[:top_n]


def _coerce_candidate(candidate: CandidateInput) -> RankingCandidate:
    if isinstance(candidate, RankingCandidate):
        return candidate
    return RankingCandidate.model_validate(candidate)


def _score_candidate(
    candidate: RankingCandidate,
    *,
    max_drawdown_to_value: float,
) -> RankedCandidate | None:
    if not candidate.feasible:
        return None
    if candidate.expected_net_value_usd <= 0:
        return None
    if candidate.repeatability <= 0:
        return None
    if candidate.capital_required_usd is None:
        return None
    if candidate.max_drawdown_usd is not None:
        drawdown_to_value = candidate.max_drawdown_usd / candidate.expected_net_value_usd
        if drawdown_to_value > max_drawdown_to_value:
            return None

    capital_efficiency = candidate.expected_net_value_usd / candidate.capital_required_usd
    drawdown_penalty = _drawdown_penalty(candidate)
    score = (
        candidate.expected_net_value_usd
        * candidate.confidence
        * candidate.repeatability
        * capital_efficiency
        * drawdown_penalty
    )

    return RankedCandidate(
        idea_id=candidate.idea_id,
        score=round(score, 12),
        expected_net_value_usd=candidate.expected_net_value_usd,
        confidence=candidate.confidence,
        repeatability=candidate.repeatability,
        capital_required_usd=candidate.capital_required_usd,
        capital_efficiency=capital_efficiency,
        max_drawdown_usd=candidate.max_drawdown_usd,
        opportunity_id=candidate.opportunity_id,
        hypothesis_id=candidate.hypothesis_id,
        backtest_id=candidate.backtest_id,
        memory_key=candidate.memory_key,
    )


def _drawdown_penalty(candidate: RankingCandidate) -> float:
    if candidate.max_drawdown_usd is None or candidate.max_drawdown_usd == 0:
        return 1.0

    reward_to_risk = candidate.expected_net_value_usd / candidate.max_drawdown_usd
    return min(1.0, reward_to_risk)
