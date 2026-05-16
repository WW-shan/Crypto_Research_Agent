from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crypto_alpha_agent.config import ActionMode
from crypto_alpha_agent.state import DependencyLevel

AgentRole = Literal["scanner", "hypothesis_generator", "coder", "reflexion", "supervisor"]
NetworkPolicy = Literal["offline", "ordinary_public_apis", "restricted_public_apis"]
ValidationType = Literal[
    "backtest",
    "historical_validation",
    "walk_forward",
    "funding_extremity",
    "momentum",
]
NextAction = Literal["revise", "reject", "validate", "update_memory", "human_review"]

UNSAFE_TEXT_TERMS = (
    "live order",
    "live orders",
    "live instruction",
    "live instructions",
    "live execution",
    "order placement",
    "place order",
    "place a live order",
    "order routing",
    "route orders",
    "private key",
    "private_key",
    "seed phrase",
    "wallet key",
    "wallet keys",
    "mev",
    "mempool",
    "sandwich",
    "flash loan",
    "bridge race",
    "premium rpc",
    "premium_rpc",
    "private rpc",
    "private_rpc",
    "sub-second arbitrage",
    "sub second arbitrage",
    "withdraw",
    "admin",
    "admin permissions",
)

_TOKEN_BOUNDARY_START = r"(?<![A-Za-z0-9])"
_TOKEN_BOUNDARY_END = r"(?![A-Za-z0-9])"
_TERM_SEPARATOR_PATTERN = r"[\s_-]*"


def _unsafe_term_pattern(term: str) -> re.Pattern[str]:
    parts = [part for part in re.split(r"[\s_-]+", term.lower()) if part]
    body = _TERM_SEPARATOR_PATTERN.join(re.escape(part) for part in parts)
    return re.compile(
        f"{_TOKEN_BOUNDARY_START}{body}{_TOKEN_BOUNDARY_END}",
        re.IGNORECASE,
    )


UNSAFE_TEXT_PATTERNS = tuple(
    (term, _unsafe_term_pattern(term)) for term in UNSAFE_TEXT_TERMS
)


class _StrictResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def _reject_unsafe_text(self) -> "_StrictResearchModel":
        _validate_safe_text(self.model_dump(mode="python"))
        return self


class ResearchTask(_StrictResearchModel):
    task_id: str = Field(min_length=1)
    agent_role: AgentRole
    objective: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    network_policy: NetworkPolicy = "ordinary_public_apis"
    current_capital_usd: float = Field(ge=0)
    requires_human_approval: bool = False


class HypothesisProposal(_StrictResearchModel):
    proposal_id: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    assumptions: list[str] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    disconfirmation: list[str] = Field(min_length=1)
    data_needed: list[str] = Field(min_length=1)
    capital_required_usd: float = Field(ge=0)
    speed_dependency: DependencyLevel = "none"
    rpc_dependency: DependencyLevel = "none"
    action_mode: ActionMode = "research_only"

    @field_validator("action_mode")
    @classmethod
    def _require_research_only(cls, value: ActionMode) -> ActionMode:
        if value != "research_only":
            raise ValueError("LLM proposals are research-only")
        return value


class ValidationRequest(_StrictResearchModel):
    request_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    validation_type: ValidationType
    dataset: str = Field(min_length=1)
    source: str = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    fee_bps: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)
    start_time: str | None = None
    end_time: str | None = None


class CritiqueResult(_StrictResearchModel):
    proposal_id: str = Field(min_length=1)
    accepted: bool
    reasons: list[str] = Field(min_length=1)
    lessons: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    disconfirmation_failures: list[str] = Field(default_factory=list)
    next_action: NextAction


def _validate_safe_text(value: Any) -> None:
    if isinstance(value, str):
        _reject_unsafe_string(value)
        return
    if isinstance(value, list | tuple | set):
        for item in value:
            _validate_safe_text(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_safe_text(key)
            _validate_safe_text(item)


def _reject_unsafe_string(value: str) -> None:
    for term, pattern in UNSAFE_TEXT_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"unsafe LLM contract text contains prohibited term: {term}")
