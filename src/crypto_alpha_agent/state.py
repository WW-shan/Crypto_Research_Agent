from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.config import ActionMode, RuntimeConfig

DependencyLevel = Literal["none", "low", "medium", "high"]


class OpportunityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    venue: str | None = None
    asset: str
    chain: str | None = None
    protocol: str | None = None
    edge_type: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    freshness_seconds: float | None = Field(default=None, ge=0)
    capital_required_usd: float = Field(default=0.0, ge=0)
    fee_estimate_usd: float = Field(default=0.0, ge=0)
    gas_estimate_usd: float = Field(default=0.0, ge=0)
    slippage_estimate_usd: float = Field(default=0.0, ge=0)
    speed_dependency: DependencyLevel = "none"
    rpc_dependency: DependencyLevel = "none"
    inventory_dependency: DependencyLevel = "none"
    expected_gross_pnl_usd: float | None = None
    expected_net_pnl_usd: float | None = None
    downside_usd: float | None = Field(default=None, ge=0)
    time_to_expiry_seconds: float | None = Field(default=None, ge=0)


class ExecutionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity: OpportunityEvent
    action_mode: ActionMode = "research_only"
    capital_to_deploy_usd: float = Field(default=0.0, ge=0)
    expected_net_pnl_usd: float | None = None
    downside_usd: float | None = Field(default=None, ge=0)
    rationale: str | None = None


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_mode: ActionMode = "research_only"
    proposal: ExecutionProposal | None = None
    approved: bool = False
    reason: str | None = None


class ResearchState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: RuntimeConfig = Field(default_factory=RuntimeConfig)
    opportunities: list[OpportunityEvent] = Field(default_factory=list)
    proposals: list[ExecutionProposal] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
