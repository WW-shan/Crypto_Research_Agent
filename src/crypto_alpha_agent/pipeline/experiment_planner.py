from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.pipeline.ai_research_context import AIResearchContext, build_ai_research_context
from crypto_alpha_agent.risk.charter_guard import guard_generated_idea
from crypto_alpha_agent.strategy import default_strategy_registry

PlannerLLM = Callable[[Any], Any]

_DEGRADED_MARKERS = {
    "degraded",
    "degraded_expectancy",
    "fee_killed_edge",
    "negative_expectancy",
}
_FAMILY_SPECIFIC_EVIDENCE_REQUIRED = {"funding_open_interest_crowding"}
_SUPPORTED_GAP_REFS = {"gap:collect_more_walk_forward_data"}


class _PlannerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExperimentProposal(_PlannerModel):
    proposal_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    parameter_changes: dict[str, Any]
    evidence_refs: list[str]
    why_it_might_improve_edge: str = Field(min_length=1)
    expected_edge_mechanism: str = Field(min_length=1)
    disconfirmation_tests: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    required_data_fields: list[str] = Field(min_length=1)
    selected_validator: str = Field(min_length=1)
    allowed_data_sources: list[str] = Field(min_length=1)
    max_capital_usd: float = Field(ge=0)
    max_notional_usd: float = Field(ge=0)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("parameter_changes")
    @classmethod
    def _validate_json_safe_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        _json_safe(value)
        return value

    @model_validator(mode="after")
    def _reject_execution_authority(self) -> "ExperimentProposal":
        if self.uses_real_capital or self.live_order_routing:
            raise ValueError("experiment proposals cannot authorize execution")
        return self


class StrategyTemplateProposal(_PlannerModel):
    proposal_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    proposed_validator_name: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    expected_edge_mechanism: str = Field(min_length=1)
    required_data_fields: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    disconfirmation_tests: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    deterministic_tests_required: Literal[True] = True
    human_review_required: Literal[True] = True
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @model_validator(mode="after")
    def _reject_execution_authority(self) -> "StrategyTemplateProposal":
        if self.uses_real_capital or self.live_order_routing:
            raise ValueError("strategy template proposals cannot authorize execution")
        return self


class ExperimentBatch(_PlannerModel):
    batch_id: str = Field(min_length=1)
    proposals: list[ExperimentProposal]
    strategy_template_proposals: list[StrategyTemplateProposal] = Field(default_factory=list)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class _LLMExperimentProposalPayload(_PlannerModel):
    strategy_family: str = Field(min_length=1)
    parameter_changes: dict[str, Any]
    evidence_refs: list[str] = Field(min_length=1)
    why_it_might_improve_edge: str = Field(min_length=1)
    expected_edge_mechanism: str = Field(min_length=1)
    disconfirmation_tests: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    required_data_fields: list[str] = Field(min_length=1)
    selected_validator: str = Field(min_length=1)
    allowed_data_sources: list[str] | None = None
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("parameter_changes")
    @classmethod
    def _validate_json_safe_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        _json_safe(value)
        return value


class ExperimentPlannerInput(_PlannerModel):
    db_path: str
    memory_path: str
    strategy_family: str | None = None
    max_proposals: int = Field(default=3, ge=1)
    current_capital_usd: float = Field(ge=0)
    allow_stopped_family: bool = False


class ExperimentPlannerMemoryContext(_PlannerModel):
    degraded_strategy_families: list[str]
    blocked_parameter_sets: dict[str, list[dict[str, Any]]]
    blocked_parameter_set_count: int = Field(ge=0)


class ExperimentPlannerTask(_PlannerModel):
    task_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    planner_input: ExperimentPlannerInput
    validation_evidence_summaries: list[dict[str, Any]]
    paper_evidence_packages: list[dict[str, Any]]
    degraded_strategy_families: list[str]
    blocked_parameter_sets: dict[str, list[dict[str, Any]]]
    memory_context: ExperimentPlannerMemoryContext
    source_health_summaries: list[dict[str, Any]] = Field(default_factory=list)
    available_data_fields: dict[str, list[str]] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    registered_validators: list[dict[str, Any]] = Field(default_factory=list)
    research_context: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=lambda: ["local_evidence_ledger", "memory_facts", "charter_guard"])
    network_policy: Literal["offline"] = "offline"
    current_capital_usd: float = Field(ge=0)


class ExperimentPlannerResult(_PlannerModel):
    batch_id: str
    accepted: bool
    proposals: list[ExperimentProposal]
    strategy_template_proposals: list[StrategyTemplateProposal] = Field(default_factory=list)
    degraded_strategy_families: list[str]
    decision_reason_codes: list[str] = Field(default_factory=list)
    rejected_reason_codes: list[str]
    validation_evidence_count: int = 0
    paper_evidence_count: int = 0
    stopped_family_override_used: bool = False
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def plan_next_experiments(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    strategy_family: str | None = None,
    max_proposals: int = 3,
    current_capital_usd: float = 300.0,
    llm: PlannerLLM,
    allow_stopped_family: bool = False,
) -> ExperimentPlannerResult:
    planner_input = ExperimentPlannerInput(
        db_path=str(db_path),
        memory_path=str(memory_path),
        strategy_family=strategy_family,
        max_proposals=max_proposals,
        current_capital_usd=float(current_capital_usd),
        allow_stopped_family=allow_stopped_family,
    )
    batch_id = _batch_id(planner_input)
    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence(strategy_family=strategy_family)
    paper_outcomes = PaperOutcomeLedger(db_path).load_outcomes(strategy_family=strategy_family)
    paper_evidence = aggregate_paper_evidence(_paper_mapping(outcome) for outcome in paper_outcomes)
    memory_records = MemoryStore(memory_path).list_records()
    research_context = build_ai_research_context(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family=strategy_family,
        current_capital_usd=current_capital_usd,
    )
    stopped_families = _load_stopped_strategy_families(memory_path)
    degraded_families = _safe_degraded_families(
        _dedupe(
            [
                *_degraded_strategy_families(memory_records),
                *stopped_families,
            ]
        )
    )
    blocked_parameter_sets = _blocked_parameter_sets(memory_records)
    duplicate_signatures = _experiment_signatures(memory_records)

    result = _plan_with_llm(
        planner_input,
        batch_id=batch_id,
        llm=llm,
        validation_evidence=validation_evidence,
        paper_evidence=paper_evidence,
        degraded_families=degraded_families,
        blocked_parameter_sets=blocked_parameter_sets,
        duplicate_signatures=duplicate_signatures,
        research_context=research_context,
    )

    stopped_family_override_used = _stopped_family_override_used(
        planner_input=planner_input,
        degraded_families=degraded_families,
        proposals=result.proposals,
    )
    result.stopped_family_override_used = stopped_family_override_used
    if stopped_family_override_used:
        result.decision_reason_codes = _dedupe(
            [*result.decision_reason_codes, "stopped_family_override_used"]
        )

    _persist_experiment_memory(memory_path, result)
    return result


def _plan_with_llm(
    planner_input: ExperimentPlannerInput,
    *,
    batch_id: str,
    llm: PlannerLLM,
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
    degraded_families: list[str],
    blocked_parameter_sets: dict[str, list[dict[str, Any]]],
    duplicate_signatures: set[str],
    research_context: AIResearchContext,
) -> ExperimentPlannerResult:
    task = _planner_task(
        planner_input,
        batch_id=batch_id,
        validation_evidence=validation_evidence,
        paper_evidence=paper_evidence,
        degraded_families=degraded_families,
        blocked_parameter_sets=blocked_parameter_sets,
        research_context=research_context,
    )
    raw_response = llm(task)
    response_metadata = _raw_response_metadata(raw_response, accepted=False)
    if not isinstance(raw_response, str):
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=False,
            proposals=[],
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=["invalid_llm_response_type"],
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
        )
        result.__dict__["_response_metadata"] = response_metadata
        return result

    try:
        payload = json.loads(raw_response, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=False,
            proposals=[],
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=["invalid_json"],
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
        )
        result.__dict__["_response_metadata"] = response_metadata
        return result

    guard = guard_generated_idea(payload, max_capital_usd=planner_input.current_capital_usd)
    if not guard.approved or _payload_requests_execution(payload) or _payload_requests_paper_outcome(payload):
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=False,
            proposals=[],
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=["charter_violation"],
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
        )
        result.__dict__["_response_metadata"] = response_metadata
        return result

    proposal_payloads, template_payloads = _llm_payload_sections(payload)
    if not isinstance(proposal_payloads, list):
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=False,
            proposals=[],
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=["invalid_shape"],
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
        )
        result.__dict__["_response_metadata"] = response_metadata
        return result

    proposals: list[ExperimentProposal] = []
    rejected_reasons: list[str] = []
    for index, item in enumerate(proposal_payloads[: planner_input.max_proposals], start=1):
        if not isinstance(item, Mapping):
            rejected_reasons.append("invalid_shape")
            continue
        proposal, rejected_reason = _proposal_from_payload(
            item,
            planner_input=planner_input,
            batch_id=batch_id,
            index=index,
            validation_evidence=validation_evidence,
            paper_evidence=paper_evidence,
            degraded_families=degraded_families,
            blocked_parameter_sets=blocked_parameter_sets,
            duplicate_signatures=duplicate_signatures,
            research_context=research_context,
        )
        if proposal is not None:
            proposals.append(proposal)
        elif rejected_reason is not None:
            rejected_reasons.append(rejected_reason)

    template_proposals: list[StrategyTemplateProposal] = []
    if isinstance(template_payloads, list):
        for item in template_payloads[: planner_input.max_proposals]:
            if not isinstance(item, Mapping):
                rejected_reasons.append("invalid_shape")
                continue
            template, rejected_reason = _template_from_payload(
                item,
                planner_input=planner_input,
                research_context=research_context,
            )
            if template is not None:
                template_proposals.append(template)
            elif rejected_reason is not None:
                rejected_reasons.append(rejected_reason)

    if not proposals and not template_proposals:
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=False,
            proposals=[],
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=_dedupe([*rejected_reasons, "no_safe_registered_proposals"]),
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
        )
        result.__dict__["_response_metadata"] = response_metadata
        return result

    result = ExperimentPlannerResult(
        batch_id=batch_id,
        accepted=True,
        proposals=proposals,
        strategy_template_proposals=template_proposals,
        degraded_strategy_families=degraded_families,
        rejected_reason_codes=[],
        validation_evidence_count=len(validation_evidence),
        paper_evidence_count=len(paper_evidence),
    )
    result.__dict__["_response_metadata"] = _raw_response_metadata(raw_response, accepted=True)
    partial_rejected_reason_codes = _dedupe(rejected_reasons)
    if partial_rejected_reason_codes:
        result.__dict__["_partial_rejected_reason_codes"] = partial_rejected_reason_codes
    return result


def _should_skip_without_family_evidence(
    family: str,
    *,
    has_any_evidence: bool,
    family_validation: list[ValidationEvidence],
    family_paper: list[PaperEvidencePackage],
) -> bool:
    has_family_evidence = bool(family_validation or family_paper)
    if family in _FAMILY_SPECIFIC_EVIDENCE_REQUIRED:
        return not has_family_evidence
    return has_any_evidence and not has_family_evidence


def _proposal_from_payload(
    item: Mapping[str, Any],
    *,
    planner_input: ExperimentPlannerInput,
    batch_id: str,
    index: int,
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
    degraded_families: list[str],
    blocked_parameter_sets: dict[str, list[dict[str, Any]]],
    duplicate_signatures: set[str],
    research_context: AIResearchContext,
) -> tuple[ExperimentProposal | None, str | None]:
    try:
        draft = _LLMExperimentProposalPayload.model_validate(item)
    except ValidationError:
        return None, "invalid_proposal_schema"

    family = draft.strategy_family.strip()
    if family not in _candidate_families(planner_input, degraded_families=degraded_families):
        return None, "unsupported_strategy_family"
    registry = default_strategy_registry(current_capital_usd=planner_input.current_capital_usd)
    spec = registry.get(family)
    if draft.selected_validator != spec.validator_name:
        return None, "unsupported_validator"
    if draft.allowed_data_sources is not None and set(draft.allowed_data_sources) - set(spec.required_record_types):
        return None, "unsupported_data_sources"
    parameters = dict(draft.parameter_changes)
    if _parameters_were_blocked(family, parameters, blocked_parameter_sets):
        return None, "duplicate_experiment"
    if _experiment_signature(family, draft.selected_validator, parameters) in duplicate_signatures:
        return None, "duplicate_experiment"
    if not _required_data_fields_supported(
        draft.required_data_fields,
        required_record_types=list(spec.required_record_types),
        research_context=research_context,
    ):
        return None, "unsupported_data_fields"
    if not _evidence_refs_supported(draft.evidence_refs, research_context, parameters):
        return None, "missing_evidence_ref"
    family_validation = [evidence for evidence in validation_evidence if evidence.strategy_family == family]
    family_paper = [evidence for evidence in paper_evidence if evidence.strategy_family == family]
    if _should_skip_without_family_evidence(
        family,
        has_any_evidence=bool(validation_evidence or paper_evidence),
        family_validation=family_validation,
        family_paper=family_paper,
    ):
        return None, "missing_family_evidence"
    proposal = _build_proposal(
        planner_input,
        batch_id=batch_id,
        index=index,
        strategy_family=family,
        parameter_changes=parameters,
        evidence_refs=list(draft.evidence_refs),
        why_it_might_improve_edge=draft.why_it_might_improve_edge,
        expected_edge_mechanism=draft.expected_edge_mechanism,
        disconfirmation_tests=list(draft.disconfirmation_tests),
        stop_conditions=list(draft.stop_conditions),
        required_data_fields=list(draft.required_data_fields),
        selected_validator=draft.selected_validator,
    )
    return proposal, None


def _build_proposal(
    planner_input: ExperimentPlannerInput,
    *,
    batch_id: str,
    index: int,
    strategy_family: str,
    parameter_changes: dict[str, Any],
    evidence_refs: list[str],
    why_it_might_improve_edge: str,
    expected_edge_mechanism: str,
    disconfirmation_tests: list[str] | None = None,
    stop_conditions: list[str] | None = None,
    required_data_fields: list[str] | None = None,
    selected_validator: str | None = None,
) -> ExperimentProposal:
    registry = default_strategy_registry(current_capital_usd=planner_input.current_capital_usd)
    spec = registry.get(strategy_family)
    proposal_id = _proposal_id(batch_id, index, strategy_family, parameter_changes)
    max_notional = min(25.0, planner_input.current_capital_usd * 0.1, spec.max_notional_usd)
    return ExperimentProposal(
        proposal_id=proposal_id,
        strategy_family=strategy_family,
        parameter_changes=parameter_changes,
        evidence_refs=evidence_refs or [_gap_evidence_ref(parameter_changes)],
        why_it_might_improve_edge=why_it_might_improve_edge,
        expected_edge_mechanism=expected_edge_mechanism,
        disconfirmation_tests=disconfirmation_tests
        or [
            "Reject if fee-adjusted expectancy is non-positive after validation.",
            "Reject if walk-forward pass rate remains below 50%.",
        ],
        stop_conditions=stop_conditions
        or [
            "Stop after two consecutive blocked validation runs for the same parameters.",
            "Stop if max drawdown exceeds the low-capital paper budget.",
        ],
        required_data_fields=required_data_fields or list(spec.required_record_types),
        selected_validator=selected_validator or spec.validator_name,
        allowed_data_sources=list(spec.required_record_types),
        max_capital_usd=planner_input.current_capital_usd,
        max_notional_usd=max_notional,
    )


def _candidate_families(
    planner_input: ExperimentPlannerInput,
    *,
    degraded_families: list[str],
) -> list[str]:
    registry = default_strategy_registry(current_capital_usd=planner_input.current_capital_usd)
    families = [planner_input.strategy_family] if planner_input.strategy_family else list(registry.list_families())
    registered: list[str] = []
    for family in families:
        if family is None:
            continue
        if family in degraded_families and not planner_input.allow_stopped_family:
            continue
        try:
            spec = registry.get(family)
        except KeyError:
            continue
        if {"market_candle", "funding_rate"}.issubset(set(spec.required_record_types)):
            registered.append(family)
    return registered


def _degraded_strategy_families(records: Iterable[MemoryRecord]) -> list[str]:
    registered_families = _registered_strategy_families()
    degraded: set[str] = set()
    for record in records:
        markers = {item.lower() for item in [*record.tags, *record.rejected_reasons]}
        if not markers.intersection(_DEGRADED_MARKERS):
            continue
        family = _family_from_record(record)
        if family in registered_families:
            degraded.add(family)
    return sorted(degraded)


def _blocked_parameter_sets(records: Iterable[MemoryRecord]) -> dict[str, list[dict[str, Any]]]:
    registered_families = _registered_strategy_families()
    blocked: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if not record.rejected_reasons and "blocked" not in record.tags:
            continue
        family = _family_from_record(record)
        if family not in registered_families:
            continue
        for section in (record.opportunity, record.hypothesis, record.score, record.paper_trade_outcome):
            if not isinstance(section, Mapping):
                continue
            parameters = section.get("parameter_changes") or section.get("parameters")
            if isinstance(parameters, dict):
                blocked.setdefault(family, []).append(parameters)
    return blocked


def _family_from_record(record: MemoryRecord) -> str | None:
    for section in (record.opportunity, record.hypothesis, record.score, record.paper_trade_outcome):
        if isinstance(section, Mapping):
            family = section.get("strategy_family")
            if isinstance(family, str) and family.strip():
                return family.strip()
    registry_families = set(default_strategy_registry(current_capital_usd=300.0).list_families())
    for tag in record.tags:
        if tag in registry_families:
            return tag
    return None


def _planner_task(
    planner_input: ExperimentPlannerInput,
    *,
    batch_id: str,
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
    degraded_families: list[str],
    blocked_parameter_sets: dict[str, list[dict[str, Any]]],
    research_context: AIResearchContext,
) -> ExperimentPlannerTask:
    safe_degraded_families = _safe_degraded_families(degraded_families)
    raw_safe_blocked_parameter_sets = _safe_context_value(blocked_parameter_sets)
    safe_blocked_parameter_sets = raw_safe_blocked_parameter_sets if isinstance(raw_safe_blocked_parameter_sets, dict) else {}
    memory_context = ExperimentPlannerMemoryContext(
        degraded_strategy_families=safe_degraded_families,
        blocked_parameter_sets=safe_blocked_parameter_sets,
        blocked_parameter_set_count=sum(len(items) for items in safe_blocked_parameter_sets.values()),
    )
    return ExperimentPlannerTask(
        task_id=f"experiment-planner:{batch_id}",
        objective="Plan bounded research-only experiments from stored evidence and memory facts.",
        planner_input=planner_input,
        validation_evidence_summaries=[
            _validation_evidence_summary(item) for item in validation_evidence
        ],
        paper_evidence_packages=[
            _safe_context_value(item.model_dump(mode="python")) for item in paper_evidence
        ],
        degraded_strategy_families=safe_degraded_families,
        blocked_parameter_sets=safe_blocked_parameter_sets,
        memory_context=memory_context,
        source_health_summaries=[
            _safe_context_value(item.model_dump(mode="python"))
            for item in research_context.source_health_summaries
        ],
        available_data_fields=research_context.available_data_fields,
        evidence_refs=list(research_context.evidence_refs),
        registered_validators=[
            _safe_context_value(item.model_dump(mode="python"))
            for item in research_context.registered_validators
        ],
        research_context=_safe_context_value(research_context.model_dump(mode="python")),
        current_capital_usd=planner_input.current_capital_usd,
    )


def _validation_evidence_summary(item: ValidationEvidence) -> dict[str, Any]:
    return _safe_context_value(
        {
            "evidence_id": item.evidence_id,
            "run_id": item.run_id,
            "strategy_family": item.strategy_family,
            "symbol": item.symbol,
            "timeframe": item.timeframe,
            "validator_name": item.validator_name,
            "trade_count": item.trade_count,
            "net_return": item.net_return,
            "fee_adjusted_expectancy": item.fee_adjusted_expectancy,
            "slippage_adjusted_expectancy": item.slippage_adjusted_expectancy,
            "max_drawdown": item.max_drawdown,
            "walk_forward_split_count": item.walk_forward_split_count,
            "walk_forward_pass_rate": item.walk_forward_pass_rate,
            "approved": item.approved,
            "blocked_reasons": list(item.blocked_reasons),
        }
    )


def _parameters_were_blocked(
    family: str,
    parameters: dict[str, Any],
    blocked_parameter_sets: dict[str, list[dict[str, Any]]],
) -> bool:
    candidate = _canonical_parameters(parameters)
    return any(candidate == _canonical_parameters(blocked) for blocked in blocked_parameter_sets.get(family, []))


def _llm_payload_sections(payload: Any) -> tuple[list[Any] | Any, list[Any] | Any]:
    if isinstance(payload, list):
        return payload, []
    if not isinstance(payload, Mapping):
        return payload, []
    proposal_payloads = payload.get("proposals")
    if proposal_payloads is None and _looks_like_experiment_proposal(payload):
        proposal_payloads = [payload]
    if isinstance(proposal_payloads, Mapping):
        proposal_payloads = [proposal_payloads]
    template_payloads = payload.get("strategy_template_proposals", payload.get("template_proposals", []))
    if isinstance(template_payloads, Mapping):
        template_payloads = [template_payloads]
    return proposal_payloads or [], template_payloads or []


def _looks_like_experiment_proposal(payload: Mapping[str, Any]) -> bool:
    return "strategy_family" in payload and "parameter_changes" in payload


def _template_from_payload(
    item: Mapping[str, Any],
    *,
    planner_input: ExperimentPlannerInput,
    research_context: AIResearchContext,
) -> tuple[StrategyTemplateProposal | None, str | None]:
    try:
        template = StrategyTemplateProposal.model_validate(item)
    except ValidationError:
        return None, "invalid_template_schema"
    guard = guard_generated_idea(template, max_capital_usd=planner_input.current_capital_usd)
    if not guard.approved or _payload_requests_execution(template.model_dump(mode="python")):
        return None, "charter_violation"
    if not _required_data_fields_supported(
        template.required_data_fields,
        required_record_types=list(research_context.available_data_fields),
        research_context=research_context,
    ):
        return None, "unsupported_data_fields"
    if not _evidence_refs_supported(template.evidence_refs, research_context, {}):
        return None, "missing_evidence_ref"
    return template, None


def _required_data_fields_supported(
    fields: Iterable[str],
    *,
    required_record_types: list[str],
    research_context: AIResearchContext,
) -> bool:
    allowed = set(required_record_types)
    for record_type in required_record_types:
        allowed.update(research_context.available_data_fields.get(record_type, []))
    normalized = {str(field).strip() for field in fields if str(field).strip()}
    return bool(normalized) and normalized.issubset(allowed)


def _evidence_refs_supported(
    refs: Iterable[str],
    research_context: AIResearchContext,
    parameter_changes: Mapping[str, Any],
) -> bool:
    known_refs = set(research_context.evidence_refs)
    resolved_refs = [str(ref).strip() for ref in refs if str(ref).strip()]
    if not resolved_refs:
        return False
    for ref in resolved_refs:
        if ref in known_refs:
            continue
        if _is_supported_gap_ref(ref, parameter_changes):
            continue
        return False
    return True


def _is_supported_gap_ref(ref: str, parameter_changes: Mapping[str, Any]) -> bool:
    normalized = ref.strip().lower()
    experiment_type = str(parameter_changes.get("experiment_type", "")).strip().lower()
    if normalized in _SUPPORTED_GAP_REFS:
        return experiment_type in {"", "collect_more_walk_forward_data"}
    return False


def _gap_evidence_ref(parameter_changes: Mapping[str, Any]) -> str:
    experiment_type = str(parameter_changes.get("experiment_type", "")).strip()
    if experiment_type == "collect_more_walk_forward_data":
        return "gap:collect_more_walk_forward_data"
    return "gap:supported_registered_baseline"


def _experiment_signatures(records: Iterable[MemoryRecord]) -> set[str]:
    signatures: set[str] = set()
    registry = default_strategy_registry(current_capital_usd=300.0)
    for record in records:
        if not _record_blocks_duplicate(record):
            continue
        for proposal in _proposal_mappings_from_record(record):
            family = proposal.get("strategy_family")
            parameters = proposal.get("parameter_changes") or proposal.get("parameters")
            if not isinstance(family, str) or not isinstance(parameters, dict):
                continue
            validator = proposal.get("selected_validator")
            inferred_validator = ""
            try:
                inferred_validator = registry.get(family).validator_name
            except KeyError:
                pass
            signatures.add(_experiment_signature(family, str(validator or inferred_validator), parameters))
            signatures.add(_experiment_signature(family, "", parameters))
    return signatures


def _record_blocks_duplicate(record: MemoryRecord) -> bool:
    tag_set = {tag.strip().lower() for tag in record.tags}
    return bool(record.rejected_reasons) or bool(tag_set.intersection({"blocked", "rejected"}))


def _proposal_mappings_from_record(record: MemoryRecord) -> list[Mapping[str, Any]]:
    mappings: list[Mapping[str, Any]] = []
    for section in (record.hypothesis, record.opportunity, record.score, record.paper_trade_outcome):
        if not isinstance(section, Mapping):
            continue
        proposal = section.get("proposal")
        if isinstance(proposal, Mapping):
            mappings.append(proposal)
        if "parameter_changes" in section or "parameters" in section:
            mappings.append(section)
    return mappings


def _experiment_signature(
    family: str,
    selected_validator: str,
    parameters: Mapping[str, Any],
) -> str:
    return "|".join(
        [
            family.strip(),
            selected_validator.strip(),
            _canonical_parameters(parameters),
        ]
    )


def _canonical_parameters(parameters: Mapping[str, Any]) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)


def _evidence_refs(
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
) -> list[str]:
    refs = [f"validation:{item.run_id}:{item.evidence_id}" for item in validation_evidence]
    refs.extend(f"paper:{item.strategy_family}:sample_size:{item.sample_size}" for item in paper_evidence)
    return refs


def _paper_mapping(outcome: Any) -> dict[str, Any]:
    return {
        "strategy_family": outcome.strategy_family,
        "trade_id": outcome.outcome_id,
        "symbol": outcome.symbol,
        "status": outcome.status,
        "realized_net_pnl": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "notional_usd": outcome.notional_usd,
        "gross_pnl_usd": outcome.gross_pnl_usd,
        "fees_usd": outcome.fees_usd,
        "slippage_usd": outcome.slippage_usd,
        "cost_model_mode": outcome.cost_model_mode,
        "stale_signal_status": outcome.stale_signal_status,
        "fill_status": outcome.fill_status,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _payload_requests_execution(payload: Any) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).lower()
            if normalized in {"live_order_routing", "uses_real_capital"} and bool(value):
                return True
            if _payload_requests_execution(value):
                return True
    if isinstance(payload, list):
        return any(_payload_requests_execution(item) for item in payload)
    return False


def _payload_requests_paper_outcome(payload: Any) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).lower()
            if normalized in {"paper_outcomes", "paper_trade_outcomes", "paper_simulation_outcomes", "outcome_id"}:
                return True
            if _payload_requests_paper_outcome(value):
                return True
    if isinstance(payload, list):
        return any(_payload_requests_paper_outcome(item) for item in payload)
    return False


def _persist_experiment_memory(memory_path: str | Path, result: ExperimentPlannerResult) -> None:
    store = MemoryStore(memory_path)
    metadata = result.__dict__.get("_response_metadata")
    partial_rejected_reason_codes = list(result.__dict__.get("_partial_rejected_reason_codes") or [])
    if result.proposals:
        for proposal in result.proposals:
            store.upsert(
                MemoryRecord(
                    record_id=f"experiment-proposal:{result.batch_id}:{proposal.proposal_id}",
                    created_at=DETERMINISTIC_EVENT_TIME_ISO,
                    updated_at=DETERMINISTIC_EVENT_TIME_ISO,
                    opportunity={
                        "strategy_family": proposal.strategy_family,
                        "evidence_refs": proposal.evidence_refs,
                        "max_notional_usd": proposal.max_notional_usd,
                    },
                    hypothesis={"proposal": proposal.model_dump(mode="python"), "llm_response": metadata},
                    score={"accepted": result.accepted, "rejected_reason_codes": result.rejected_reason_codes},
                    rejected_reasons=list(result.rejected_reason_codes),
                    tags=["experiment-proposal", "accepted" if result.accepted else "rejected"],
                )
            )
    if result.strategy_template_proposals:
        for proposal in result.strategy_template_proposals:
            store.upsert(
                MemoryRecord(
                    record_id=f"strategy-template-proposal:{result.batch_id}:{proposal.proposal_id}",
                    created_at=DETERMINISTIC_EVENT_TIME_ISO,
                    updated_at=DETERMINISTIC_EVENT_TIME_ISO,
                    opportunity={
                        "strategy_family": proposal.strategy_family,
                        "evidence_refs": proposal.evidence_refs,
                        "design_only": True,
                        "uses_real_capital": False,
                        "live_order_routing": False,
                    },
                    hypothesis={
                        "template_proposal": proposal.model_dump(mode="python"),
                        "llm_response": metadata,
                    },
                    score={
                        "accepted": result.accepted,
                        "deterministic_tests_required": proposal.deterministic_tests_required,
                        "human_review_required": proposal.human_review_required,
                        "rejected_reason_codes": result.rejected_reason_codes,
                    },
                    rejected_reasons=list(result.rejected_reason_codes),
                    tags=["strategy-template-proposal", "design-only", "accepted" if result.accepted else "rejected"],
                )
            )
    if result.proposals or result.strategy_template_proposals:
        if partial_rejected_reason_codes:
            store.upsert(
                MemoryRecord(
                    record_id=f"experiment-proposal:{result.batch_id}:partial-rejected",
                    created_at=DETERMINISTIC_EVENT_TIME_ISO,
                    updated_at=DETERMINISTIC_EVENT_TIME_ISO,
                    opportunity={
                        "batch_id": result.batch_id,
                        "partial_batch_rejection": True,
                        "uses_real_capital": False,
                        "live_order_routing": False,
                    },
                    hypothesis={"llm_response": metadata},
                    score={
                        "accepted": False,
                        "parent_batch_accepted": result.accepted,
                        "rejected_reason_codes": partial_rejected_reason_codes,
                    },
                    rejected_reasons=partial_rejected_reason_codes,
                    tags=["experiment-proposal", "rejected", "partial-batch"],
                )
            )
        return
    if not result.accepted:
        store.upsert(
            MemoryRecord(
                record_id=f"experiment-proposal:{result.batch_id}:rejected",
                created_at=DETERMINISTIC_EVENT_TIME_ISO,
                updated_at=DETERMINISTIC_EVENT_TIME_ISO,
                opportunity={"batch_id": result.batch_id},
                hypothesis={"llm_response": metadata},
                score={"accepted": False, "rejected_reason_codes": result.rejected_reason_codes},
                rejected_reasons=list(result.rejected_reason_codes),
                tags=["experiment-proposal", "rejected"],
            )
        )


def _raw_response_metadata(raw_response: Any, *, accepted: bool) -> dict[str, Any]:
    metadata = {
        "status": "accepted" if accepted else "rejected",
        "raw_response_type": type(raw_response).__name__,
        "raw_response_omitted": True,
    }
    if isinstance(raw_response, str):
        metadata["raw_response_length"] = len(raw_response)
        metadata["raw_response_sha256"] = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
    return metadata


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _registered_strategy_families() -> set[str]:
    return set(default_strategy_registry(current_capital_usd=300.0).list_families())


def _safe_degraded_families(families: Iterable[str]) -> list[str]:
    registered_families = _registered_strategy_families()
    return [family for family in families if family in registered_families]


def _load_stopped_strategy_families(memory_path: str | Path) -> list[str]:
    from crypto_alpha_agent.pipeline.evidence_reports import load_stopped_strategy_families

    return load_stopped_strategy_families(memory_path)


def _stopped_family_override_used(
    *,
    planner_input: ExperimentPlannerInput,
    degraded_families: list[str],
    proposals: list[ExperimentProposal],
) -> bool:
    if not planner_input.allow_stopped_family or not degraded_families:
        return False
    proposed_stopped = {
        proposal.strategy_family
        for proposal in proposals
        if proposal.strategy_family in degraded_families
    }
    if proposed_stopped:
        return True
    return (
        planner_input.strategy_family is not None
        and planner_input.strategy_family in degraded_families
    )


def _batch_id(planner_input: ExperimentPlannerInput) -> str:
    payload = planner_input.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"experiment-batch-{digest}"


def _proposal_id(batch_id: str, index: int, strategy_family: str, parameters: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {"batch_id": batch_id, "index": index, "strategy_family": strategy_family, "parameters": parameters},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"proposal-{digest}"


def _string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else None
    if isinstance(value, Iterable):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or None
    return None


def _safe_context_value(value: Any) -> Any:
    if isinstance(value, str):
        return value if guard_generated_idea(value).approved else "unsafe_text_omitted"
    if isinstance(value, Mapping):
        return {
            str(_safe_context_value(key)): _safe_context_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_safe_context_value(item) for item in value]
    return value


def _json_safe(value: Any) -> None:
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("parameter values must be finite")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("parameter keys must be strings")
            _json_safe(item)
        return
    if isinstance(value, list):
        for item in value:
            _json_safe(item)
        return
    raise ValueError("parameters must be JSON safe")


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
