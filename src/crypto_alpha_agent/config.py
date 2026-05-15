from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionMode = Literal["research_only", "paper", "gated_live"]


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_mode: ActionMode = "research_only"
    max_capital_per_trade_usd: float | None = Field(default=None, ge=0)
    min_confidence: float = Field(default=0.0, ge=0, le=1)
    require_human_approval: bool = True
