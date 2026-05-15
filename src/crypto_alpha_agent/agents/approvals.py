from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ManualApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    approved: bool
    approver: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    reference_id: str | None = Field(default=None, min_length=1)
