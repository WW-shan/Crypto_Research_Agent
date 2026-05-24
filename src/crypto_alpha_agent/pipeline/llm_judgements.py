from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.llm.runtime import RealLLMRuntime

JudgementDecision = Literal[
    "research_ready",
    "keep_collecting",
    "add_data",
    "redesign_validator",
    "stop",
    "owner_decision_review",
    "blocked",
]


class _JudgementModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class _EvidenceBackedJudgement(_JudgementModel):
    decision: JudgementDecision
    rationale: str = Field(min_length=1, max_length=1600)
    evidence_refs: list[str] = Field(min_length=1, max_length=32)
    next_actions: list[str] = Field(min_length=1, max_length=12)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    def validate_refs(self, allowed_refs: set[str]) -> None:
        unknown = sorted(set(self.evidence_refs) - allowed_refs)
        if unknown:
            raise ValueError("unknown evidence refs: " + ", ".join(unknown))


class SourceResearchJudgement(_EvidenceBackedJudgement):
    schema_name: Literal["SourceResearchJudgement"]


class DataReadinessJudgement(_EvidenceBackedJudgement):
    schema_name: Literal["DataReadinessJudgement"]
    missing_fields: list[str] = Field(default_factory=list, max_length=24)


class LLMHypothesisSet(_EvidenceBackedJudgement):
    schema_name: Literal["LLMHypothesisSet"]
    hypotheses: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    critique: list[str] = Field(default_factory=list, max_length=12)


class EvidenceRunInterpretation(_EvidenceBackedJudgement):
    schema_name: Literal["EvidenceRunInterpretation"]
    blocked_reason_review: list[str] = Field(default_factory=list, max_length=16)
    next_experiment: dict[str, Any] | None = None


class GovernanceReview(_EvidenceBackedJudgement):
    schema_name: Literal["GovernanceReview"]
    family_actions: dict[str, JudgementDecision] = Field(default_factory=dict)


class BootstrapInterpretation(_EvidenceBackedJudgement):
    schema_name: Literal["BootstrapInterpretation"]
    historical_is_profit_proof: Literal[False] = False


class RolloutReadinessNarrative(_EvidenceBackedJudgement):
    schema_name: Literal["RolloutReadinessNarrative"]
    live_execution_enabled: Literal[False] = False


class RuntimeCommandJudgement(_EvidenceBackedJudgement):
    schema_name: Literal["RuntimeCommandJudgement"]


class LLMJudgementTask(_JudgementModel):
    command: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    facts: dict[str, Any]
    evidence_refs: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


def run_source_research_judgement(
    runtime: RealLLMRuntime,
    *,
    command: str,
    source_health: dict[str, Any],
    evidence_refs: list[str],
) -> SourceResearchJudgement:
    task = LLMJudgementTask(
        command=command,
        schema_name="SourceResearchJudgement",
        objective="Judge whether the probed source is useful for research.",
        facts={"source_health": source_health},
        evidence_refs=evidence_refs,
        constraints=_default_constraints(),
    )
    judgement = runtime.structured_call(task, SourceResearchJudgement)
    judgement.validate_refs(set(evidence_refs))
    return judgement


def run_data_readiness_judgement(
    runtime: RealLLMRuntime,
    *,
    command: str,
    ingestion_summary: dict[str, Any],
    evidence_refs: list[str],
) -> DataReadinessJudgement:
    task = LLMJudgementTask(
        command=command,
        schema_name="DataReadinessJudgement",
        objective="Judge whether ingested data is ready for research use.",
        facts={"ingestion_summary": ingestion_summary},
        evidence_refs=evidence_refs,
        constraints=_default_constraints(),
    )
    judgement = runtime.structured_call(task, DataReadinessJudgement)
    judgement.validate_refs(set(evidence_refs))
    return judgement


def run_runtime_command_judgement(
    runtime: RealLLMRuntime,
    *,
    command: str,
    facts: dict[str, Any],
    evidence_refs: list[str],
    objective: str,
) -> RuntimeCommandJudgement:
    task = LLMJudgementTask(
        command=command,
        schema_name="RuntimeCommandJudgement",
        objective=objective,
        facts=facts,
        evidence_refs=evidence_refs,
        constraints=_default_constraints(),
    )
    judgement = runtime.structured_call(task, RuntimeCommandJudgement)
    judgement.validate_refs(set(evidence_refs))
    return judgement


def _default_constraints() -> list[str]:
    return [
        "Use only supplied facts and evidence_refs.",
        "Do not request live capital.",
        "Do not request live order routing.",
        "Do not request wallet keys or premium infrastructure.",
        "Return only the requested JSON schema.",
    ]
