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
from crypto_alpha_agent.risk.charter_guard import guard_generated_idea
from crypto_alpha_agent.strategy import default_strategy_registry

PlannerLLM = Callable[[Any], Any]

_DEGRADED_MARKERS = {
    "degraded",
    "degraded_expectancy",
    "fee_killed_edge",
    "negative_expectancy",
}
_FUNDING_BASELINE_PARAMETERS = {"threshold_abs": 0.0005, "hold_bars": 1}


class _PlannerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExperimentProposal(_PlannerModel):
    proposal_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    parameter_changes: dict[str, Any]
    evidence_refs: list[str]
    why_it_might_improve_edge: str = Field(min_length=1)
    disconfirmation_tests: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
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


class ExperimentBatch(_PlannerModel):
    batch_id: str = Field(min_length=1)
    proposals: list[ExperimentProposal]
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class ExperimentPlannerInput(_PlannerModel):
    db_path: str
    memory_path: str
    strategy_family: str | None = None
    max_proposals: int = Field(default=3, ge=1)
    current_capital_usd: float = Field(ge=0)
    offline_only: bool = True
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
    allowed_tools: list[str] = Field(default_factory=lambda: ["local_evidence_ledger", "memory_facts", "charter_guard"])
    network_policy: Literal["offline"] = "offline"
    current_capital_usd: float = Field(ge=0)


class ExperimentPlannerResult(_PlannerModel):
    batch_id: str
    accepted: bool
    proposals: list[ExperimentProposal]
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
    llm: PlannerLLM | None = None,
    offline_only: bool = True,
    allow_stopped_family: bool = False,
) -> ExperimentPlannerResult:
    planner_input = ExperimentPlannerInput(
        db_path=str(db_path),
        memory_path=str(memory_path),
        strategy_family=strategy_family,
        max_proposals=max_proposals,
        current_capital_usd=float(current_capital_usd),
        offline_only=offline_only,
        allow_stopped_family=allow_stopped_family,
    )
    batch_id = _batch_id(planner_input)
    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence(strategy_family=strategy_family)
    paper_outcomes = PaperOutcomeLedger(db_path).load_outcomes(strategy_family=strategy_family)
    paper_evidence = aggregate_paper_evidence(_paper_mapping(outcome) for outcome in paper_outcomes)
    memory_records = MemoryStore(memory_path).list_records()
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

    if llm is not None:
        result = _plan_with_llm(
            planner_input,
            batch_id=batch_id,
            llm=llm,
            validation_evidence=validation_evidence,
            paper_evidence=paper_evidence,
            degraded_families=degraded_families,
            blocked_parameter_sets=blocked_parameter_sets,
        )
    else:
        proposals = _fallback_proposals(
            planner_input,
            batch_id=batch_id,
            validation_evidence=validation_evidence,
            paper_evidence=paper_evidence,
            degraded_families=degraded_families,
            blocked_parameter_sets=blocked_parameter_sets,
        )
        accepted = bool(proposals)
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=accepted,
            proposals=proposals,
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=[] if accepted else ["no_safe_registered_proposals"],
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
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

    should_persist_deterministic_result = bool(result.proposals) and not _is_no_evidence_deterministic_fallback(
        validation_evidence=validation_evidence,
        paper_evidence=paper_evidence,
        degraded_families=degraded_families,
        blocked_parameter_sets=blocked_parameter_sets,
    )
    if llm is not None or should_persist_deterministic_result:
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
) -> ExperimentPlannerResult:
    task = _planner_task(
        planner_input,
        batch_id=batch_id,
        validation_evidence=validation_evidence,
        paper_evidence=paper_evidence,
        degraded_families=degraded_families,
        blocked_parameter_sets=blocked_parameter_sets,
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
    if not guard.approved or _payload_requests_execution(payload):
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

    proposal_payloads = payload.get("proposals", payload) if isinstance(payload, dict) else payload
    if isinstance(proposal_payloads, Mapping):
        proposal_payloads = [proposal_payloads]
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
    for index, item in enumerate(proposal_payloads[: planner_input.max_proposals], start=1):
        if not isinstance(item, Mapping):
            continue
        try:
            proposal = _proposal_from_payload(
                item,
                planner_input=planner_input,
                batch_id=batch_id,
                index=index,
                validation_evidence=validation_evidence,
                paper_evidence=paper_evidence,
                degraded_families=degraded_families,
                blocked_parameter_sets=blocked_parameter_sets,
            )
        except (ValidationError, ValueError):
            proposal = None
        if proposal is not None:
            proposals.append(proposal)

    if not proposals:
        result = ExperimentPlannerResult(
            batch_id=batch_id,
            accepted=False,
            proposals=[],
            degraded_strategy_families=degraded_families,
            rejected_reason_codes=["no_safe_registered_proposals"],
            validation_evidence_count=len(validation_evidence),
            paper_evidence_count=len(paper_evidence),
        )
        result.__dict__["_response_metadata"] = response_metadata
        return result

    result = ExperimentPlannerResult(
        batch_id=batch_id,
        accepted=True,
        proposals=proposals,
        degraded_strategy_families=degraded_families,
        rejected_reason_codes=[],
        validation_evidence_count=len(validation_evidence),
        paper_evidence_count=len(paper_evidence),
    )
    result.__dict__["_response_metadata"] = _raw_response_metadata(raw_response, accepted=True)
    return result


def _fallback_proposals(
    planner_input: ExperimentPlannerInput,
    *,
    batch_id: str,
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
    degraded_families: list[str],
    blocked_parameter_sets: dict[str, list[dict[str, Any]]],
) -> list[ExperimentProposal]:
    families = _candidate_families(planner_input, degraded_families=degraded_families)
    proposals: list[ExperimentProposal] = []
    for family in families:
        family_validation = [item for item in validation_evidence if item.strategy_family == family]
        family_paper = [item for item in paper_evidence if item.strategy_family == family]
        for parameters, reason in _fallback_parameter_sets(family_validation, family_paper):
            if _parameters_were_blocked(family, parameters, blocked_parameter_sets):
                continue
            proposals.append(
                _build_proposal(
                    planner_input,
                    batch_id=batch_id,
                    index=len(proposals) + 1,
                    strategy_family=family,
                    parameter_changes=parameters,
                    evidence_refs=_evidence_refs(family_validation, family_paper),
                    why_it_might_improve_edge=reason,
                )
            )
            if len(proposals) >= planner_input.max_proposals:
                return proposals
    return proposals


def _fallback_parameter_sets(
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
) -> list[tuple[dict[str, Any], str]]:
    blocked_reasons = {reason for item in validation_evidence for reason in item.blocked_reasons}
    paper_reasons = {reason for item in paper_evidence for reason in item.failure_reasons}
    negative_expectancy = any(
        item.net_return < 0 or item.fee_adjusted_expectancy < 0 or item.slippage_adjusted_expectancy < 0
        for item in validation_evidence
    ) or any(item.net_pnl_usd < 0 for item in paper_evidence)

    if "insufficient_walk_forward_splits" in blocked_reasons or "insufficient_walk_forward_splits" in paper_reasons:
        return [
            (
                {
                    "experiment_type": "collect_more_walk_forward_data",
                    "threshold_abs": 0.0005,
                    "hold_bars": 1,
                    "min_walk_forward_splits": 3,
                },
                "Validation was blocked by insufficient walk-forward splits, so the next experiment gathers more public history before changing execution assumptions.",
            )
        ]
    if "fee_killed_edge" in paper_reasons or negative_expectancy:
        return [
            (
                {"threshold_abs": 0.001, "hold_bars": 2},
                "A stricter funding threshold and longer hold test whether only larger public dislocations survive fees and slippage.",
            ),
            (
                {"threshold_abs": 0.0015, "hold_bars": 1},
                "A smaller sweep around higher extremity filters can disconfirm whether fees killed the baseline edge.",
            ),
        ]
    return [
        (
            dict(_FUNDING_BASELINE_PARAMETERS),
            "No recent evidence exists, so start with the registered low-capital funding baseline.",
        ),
        (
            {"threshold_abs": 0.001, "hold_bars": 1},
            "A conservative adjacent threshold sweep checks whether larger funding extremes improve fee-adjusted expectancy.",
        ),
    ]


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
) -> ExperimentProposal | None:
    family = str(item.get("strategy_family", "")).strip()
    if family not in _candidate_families(planner_input, degraded_families=degraded_families):
        return None
    parameters = item.get("parameter_changes")
    if not isinstance(parameters, dict):
        parameters = {}
    if _parameters_were_blocked(family, parameters, blocked_parameter_sets):
        return None
    family_validation = [evidence for evidence in validation_evidence if evidence.strategy_family == family]
    family_paper = [evidence for evidence in paper_evidence if evidence.strategy_family == family]
    return _build_proposal(
        planner_input,
        batch_id=batch_id,
        index=index,
        strategy_family=family,
        parameter_changes=dict(parameters),
        evidence_refs=_evidence_refs(family_validation, family_paper),
        why_it_might_improve_edge=str(
            item.get("why_it_might_improve_edge")
            or "The LLM proposed a bounded parameter-only experiment for registered public funding data."
        ),
        disconfirmation_tests=_string_list(item.get("disconfirmation_tests")),
        stop_conditions=_string_list(item.get("stop_conditions")),
    )


def _build_proposal(
    planner_input: ExperimentPlannerInput,
    *,
    batch_id: str,
    index: int,
    strategy_family: str,
    parameter_changes: dict[str, Any],
    evidence_refs: list[str],
    why_it_might_improve_edge: str,
    disconfirmation_tests: list[str] | None = None,
    stop_conditions: list[str] | None = None,
) -> ExperimentProposal:
    registry = default_strategy_registry(current_capital_usd=planner_input.current_capital_usd)
    spec = registry.get(strategy_family)
    proposal_id = _proposal_id(batch_id, index, strategy_family, parameter_changes)
    max_notional = min(25.0, planner_input.current_capital_usd * 0.1, spec.max_notional_usd)
    return ExperimentProposal(
        proposal_id=proposal_id,
        strategy_family=strategy_family,
        parameter_changes=parameter_changes,
        evidence_refs=evidence_refs or ["evidence:none"],
        why_it_might_improve_edge=why_it_might_improve_edge,
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
    return any(parameters == blocked for blocked in blocked_parameter_sets.get(family, []))


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


def _persist_experiment_memory(memory_path: str | Path, result: ExperimentPlannerResult) -> None:
    store = MemoryStore(memory_path)
    metadata = result.__dict__.get("_response_metadata")
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


def _is_no_evidence_deterministic_fallback(
    *,
    validation_evidence: list[ValidationEvidence],
    paper_evidence: list[PaperEvidencePackage],
    degraded_families: list[str],
    blocked_parameter_sets: dict[str, list[dict[str, Any]]],
) -> bool:
    return (
        not validation_evidence
        and not paper_evidence
        and not degraded_families
        and not blocked_parameter_sets
    )


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
