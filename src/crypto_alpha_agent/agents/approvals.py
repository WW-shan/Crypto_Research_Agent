from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_alpha_agent.config import ActionMode

NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class ManualApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    approval_id: str = Field(min_length=1)
    approved: bool
    approver: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    action_mode: ActionMode
    venue: str = Field(min_length=1)
    max_approved_capital_usd: NonNegativeFiniteFloat
    reason: str = Field(min_length=1)
    reference_id: str | None = Field(default=None, min_length=1)

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, venue: str) -> str:
        return venue.strip().lower()
