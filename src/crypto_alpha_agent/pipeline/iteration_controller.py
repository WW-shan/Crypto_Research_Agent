from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.pipeline.ai_research_context import (
    AIResearchContext,
    build_ai_research_context,
)
from crypto_alpha_agent.pipeline.expansion_preparation import (
    ExpansionPreparationReport,
    build_expansion_preparation_report,
)
from crypto_alpha_agent.pipeline.governance_reports import (
    ProfitGovernanceReport,
    build_profit_governance_report,
)
from crypto_alpha_agent.risk.charter_guard import guard_generated_idea

IterationCandidateKind = Literal[
    "new_data_source",
    "new_strategy_validator",
    "validator_change",
    "experiment_parameter_change",
    "code_change_request",
]
IterationCandidateRisk = Literal["low", "medium", "high", "blocked"]
IterationControllerLLM = Callable[[Any], Any]

_OWNER_AUTONOMY_REFS = {
    "goal:owner_autonomy_target",
    "gap:30_60_90_out_of_sample",
    "registry:strategy_families",
    "source_catalog:expansion_candidates",
    "governance:family_scoreboard",
}


class _StrictIterationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class IterationCandidate(_StrictIterationModel):
    kind: IterationCandidateKind
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    expected_value: str = Field(min_length=1)
    risk_level: IterationCandidateRisk
    next_actions: list[str] = Field(min_length=1)
    required_tests: list[str] = Field(min_length=1)
    required_data_fields: list[str] = Field(min_length=1)
    source_discovery_queries: list[str] = Field(default_factory=list)
    source_probe_targets: list[str] = Field(default_factory=list)
    strategy_family: str | None = None
    target_files: list[str] = Field(default_factory=list)
    human_review_required: bool
    direct_code_write_authorized: bool
    uses_real_capital: bool = False
    live_order_routing: bool = False


class IterationCandidateBatch(_StrictIterationModel):
    candidates: list[IterationCandidate] = Field(min_length=1, max_length=10)
    rejected_reason_codes: list[str] = Field(default_factory=list, max_length=32)
    uses_real_capital: bool = False
    live_order_routing: bool = False


class IterationControllerInput(_StrictIterationModel):
    db_path: str
    memory_path: str
    strategy_family: str | None = None
    current_capital_usd: float = Field(ge=0)
    max_candidates: int = Field(ge=1, le=10)


class IterationControllerTask(_StrictIterationModel):
    task_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    controller_input: IterationControllerInput
    research_context: dict[str, Any]
    expansion_preparation: dict[str, Any]
    profit_governance: dict[str, Any]
    evidence_refs: list[str]
    allowed_candidate_kinds: list[IterationCandidateKind]
    constraints: list[str]
    allowed_tools: list[str]
    network_policy: Literal["offline"] = "offline"
    llm_must_return_json: Literal[True] = True
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class IterationCycleReport(_StrictIterationModel):
    cycle_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    accepted: bool
    candidates: list[IterationCandidate]
    rejected_reason_codes: list[str]
    evidence_refs: list[str]
    current_capital_usd: float = Field(ge=0)
    strategy_family: str | None = None
    research_evidence_ref_count: int = Field(ge=0)
    source_candidate_count: int = Field(ge=0)
    strategy_candidate_count: int = Field(ge=0)
    governance_family_count: int = Field(ge=0)
    llm_required: Literal[True] = True
    auto_executes_changes: Literal[False] = False
    scheduler_executes_commands: Literal[False] = False
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_iteration_cycle_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    llm: IterationControllerLLM,
    strategy_family: str | None = None,
    current_capital_usd: float = 300.0,
    max_candidates: int = 5,
) -> IterationCycleReport:
    controller_input = IterationControllerInput(
        db_path=str(db_path),
        memory_path=str(memory_path),
        strategy_family=strategy_family,
        current_capital_usd=float(current_capital_usd),
        max_candidates=max_candidates,
    )
    research_context = build_ai_research_context(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family=strategy_family,
        current_capital_usd=current_capital_usd,
    )
    expansion_report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=memory_path,
        current_capital_usd=current_capital_usd,
    )
    governance_report = build_profit_governance_report(
        db_path=db_path,
        memory_path=memory_path,
        current_capital_usd=current_capital_usd,
    )
    cycle_id = _cycle_id(controller_input, research_context)
    evidence_refs = _allowed_evidence_refs(research_context)
    task = _iteration_task(
        controller_input,
        cycle_id=cycle_id,
        research_context=research_context,
        expansion_report=expansion_report,
        governance_report=governance_report,
        evidence_refs=evidence_refs,
    )
    raw_response = llm(task)
    response_metadata = _raw_response_metadata(raw_response, accepted=False)
    if not isinstance(raw_response, str):
        return _report(
            cycle_id=cycle_id,
            accepted=False,
            candidates=[],
            rejected_reason_codes=["invalid_llm_response_type"],
            controller_input=controller_input,
            research_context=research_context,
            expansion_report=expansion_report,
            governance_report=governance_report,
            evidence_refs=evidence_refs,
            response_metadata=response_metadata,
        )

    try:
        payload = json.loads(raw_response, parse_constant=_reject_json_constant)
        batch = IterationCandidateBatch.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError):
        return _report(
            cycle_id=cycle_id,
            accepted=False,
            candidates=[],
            rejected_reason_codes=["invalid_llm_schema"],
            controller_input=controller_input,
            research_context=research_context,
            expansion_report=expansion_report,
            governance_report=governance_report,
            evidence_refs=evidence_refs,
            response_metadata=response_metadata,
        )

    rejected_reason_codes = list(batch.rejected_reason_codes)
    if batch.uses_real_capital:
        rejected_reason_codes.append("live_capital_requested")
    if batch.live_order_routing:
        rejected_reason_codes.append("live_order_routing_requested")

    candidates: list[IterationCandidate] = []
    for candidate in batch.candidates[:max_candidates]:
        rejection = _candidate_rejection_reason(
            candidate,
            evidence_refs=set(evidence_refs),
            current_capital_usd=controller_input.current_capital_usd,
        )
        if rejection is None:
            candidates.append(candidate)
        else:
            rejected_reason_codes.append(rejection)

    accepted = bool(candidates) and not batch.uses_real_capital and not batch.live_order_routing
    if not accepted:
        rejected_reason_codes.append("no_safe_iteration_candidates")

    return _report(
        cycle_id=cycle_id,
        accepted=accepted,
        candidates=candidates,
        rejected_reason_codes=_dedupe(rejected_reason_codes),
        controller_input=controller_input,
        research_context=research_context,
        expansion_report=expansion_report,
        governance_report=governance_report,
        evidence_refs=evidence_refs,
        response_metadata=_raw_response_metadata(raw_response, accepted=accepted),
    )


def _iteration_task(
    controller_input: IterationControllerInput,
    *,
    cycle_id: str,
    research_context: AIResearchContext,
    expansion_report: ExpansionPreparationReport,
    governance_report: ProfitGovernanceReport,
    evidence_refs: list[str],
) -> IterationControllerTask:
    return IterationControllerTask(
        task_id=f"iteration-controller:{cycle_id}",
        objective=(
            "Propose evidence-grounded next iteration candidates for the owner "
            "autonomy target. Do not execute code, promote data sources, route "
            "orders, or authorize real capital."
        ),
        controller_input=controller_input,
        research_context=research_context.model_dump(mode="python"),
        expansion_preparation=expansion_report.model_dump(mode="python"),
        profit_governance=governance_report.model_dump(mode="python"),
        evidence_refs=evidence_refs,
        allowed_candidate_kinds=[
            "new_data_source",
            "new_strategy_validator",
            "validator_change",
            "experiment_parameter_change",
            "code_change_request",
        ],
        constraints=[
            "Every candidate must cite evidence_refs from the provided list.",
            "human_review_required must be true.",
            "direct_code_write_authorized must be false.",
            "uses_real_capital and live_order_routing must be false.",
            "code_change_request candidates must include target_files and required_tests.",
            "new_data_source candidates must include discovery queries or source probe targets.",
        ],
        allowed_tools=[
            "local_evidence_ledger",
            "source_probe_catalog",
            "strategy_registry",
            "charter_guard",
        ],
    )


def _candidate_rejection_reason(
    candidate: IterationCandidate,
    *,
    evidence_refs: set[str],
    current_capital_usd: float,
) -> str | None:
    if candidate.uses_real_capital:
        return "live_capital_requested"
    if candidate.live_order_routing:
        return "live_order_routing_requested"
    if not candidate.human_review_required:
        return "human_review_not_required"
    if candidate.direct_code_write_authorized:
        return "direct_code_write_authorized"
    if not candidate.required_tests:
        return "missing_required_tests"
    if not set(candidate.evidence_refs).issubset(evidence_refs):
        return "missing_evidence_ref"
    if candidate.kind == "code_change_request" and not candidate.target_files:
        return "missing_target_files"
    if (
        candidate.kind == "new_data_source"
        and not candidate.source_discovery_queries
        and not candidate.source_probe_targets
    ):
        return "missing_source_probe_plan"
    guard = guard_generated_idea(
        candidate.model_dump(mode="python"),
        max_capital_usd=current_capital_usd,
    )
    if not guard.approved:
        return "charter_violation"
    return None


def _report(
    *,
    cycle_id: str,
    accepted: bool,
    candidates: list[IterationCandidate],
    rejected_reason_codes: list[str],
    controller_input: IterationControllerInput,
    research_context: AIResearchContext,
    expansion_report: ExpansionPreparationReport,
    governance_report: ProfitGovernanceReport,
    evidence_refs: list[str],
    response_metadata: dict[str, Any],
) -> IterationCycleReport:
    report = IterationCycleReport(
        cycle_id=cycle_id,
        generated_at=DETERMINISTIC_EVENT_TIME_ISO,
        accepted=accepted,
        candidates=candidates,
        rejected_reason_codes=_dedupe(rejected_reason_codes),
        evidence_refs=evidence_refs,
        current_capital_usd=controller_input.current_capital_usd,
        strategy_family=controller_input.strategy_family,
        research_evidence_ref_count=len(research_context.evidence_refs),
        source_candidate_count=len(expansion_report.source_candidates),
        strategy_candidate_count=len(expansion_report.strategy_candidates),
        governance_family_count=len(governance_report.family_scoreboard),
    )
    report.__dict__["_response_metadata"] = response_metadata
    return report


def _allowed_evidence_refs(research_context: AIResearchContext) -> list[str]:
    return _dedupe([*research_context.evidence_refs, *_OWNER_AUTONOMY_REFS])


def _cycle_id(
    controller_input: IterationControllerInput,
    research_context: AIResearchContext,
) -> str:
    material = json.dumps(
        {
            "input": controller_input.model_dump(mode="json"),
            "evidence_refs": list(research_context.evidence_refs),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _raw_response_metadata(raw_response: Any, *, accepted: bool) -> dict[str, Any]:
    metadata = {
        "status": "accepted" if accepted else "rejected",
        "raw_response_type": type(raw_response).__name__,
        "raw_response_omitted": True,
    }
    if isinstance(raw_response, str):
        metadata["raw_response_length"] = len(raw_response)
        metadata["raw_response_sha256"] = hashlib.sha256(
            raw_response.encode("utf-8")
        ).hexdigest()
    return metadata


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
