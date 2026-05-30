from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CreationKind = Literal[
    "family_idea",
    "data_source_idea",
    "validator_idea",
    "strategy_idea",
    "experiment_idea",
    "system_improvement_idea",
]
CreationStatus = Literal["active", "needs_data", "needs_fix", "stale", "archived"]
CreationRole = Literal["director", "scout", "creator", "builder", "runner", "critic"]


class _StrictAutonomyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class CreationObject(_StrictAutonomyModel):
    id: str = Field(min_length=1)
    kind: CreationKind
    title: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    why_now: str = Field(min_length=1)
    first_code_change: str = Field(min_length=1)
    expected_experiment: str = Field(min_length=1)
    status: CreationStatus = "active"
    continuation_reason: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    uses_real_capital: bool = False
    live_order_routing: bool = False

    @model_validator(mode="after")
    def reject_live_capital(self) -> "CreationObject":
        if self.uses_real_capital:
            raise ValueError("uses_real_capital must be false")
        if self.live_order_routing:
            raise ValueError("live_order_routing must be false")
        return self


class CreationRoleNote(_StrictAutonomyModel):
    role: CreationRole
    summary: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class CreationTaskRecord(_StrictAutonomyModel):
    task_id: str = Field(min_length=1)
    creation_id: str = Field(min_length=1)
    path: Path


class CodexExecResult(_StrictAutonomyModel):
    command: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    output_path: str | None = None


class CreationCycleReport(_StrictAutonomyModel):
    task_id: str
    creation: CreationObject
    accepted: bool
    status: CreationStatus
    report_path: str
    json_path: str
    task_path: str
    patch_path: str | None = None
    runner_exit_code: int | None = None
    rejected_reason_codes: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    llm_required: Literal[True] = True
    codex_required: Literal[True] = True
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
