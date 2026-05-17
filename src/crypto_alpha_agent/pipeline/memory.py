from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
import re
from typing import Any

from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis, EvidenceBundle
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport, ValidationSummary

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def persist_research_loop_memory(
    report: ResearchLoopReport, memory_path: str | Path
) -> list[MemoryRecord]:
    store = MemoryStore(memory_path)
    stored_records: list[MemoryRecord] = []
    for record in _research_loop_memory_records(report):
        stored_records.append(store.upsert(record))
    return stored_records


def replace_research_loop_memory(
    report: ResearchLoopReport, memory_path: str | Path
) -> list[MemoryRecord]:
    records = _research_loop_memory_records(report)
    if not records and not Path(memory_path).exists():
        return []

    store = MemoryStore(memory_path)
    return store.replace_matching(
        lambda record: _is_replaceable_research_loop_record(record, report.run_id),
        records,
    )


def persist_paper_outcome_memory(
    outcomes: Iterable[PaperSimulationOutcome],
    memory_path: str | Path,
    *,
    replace_run: bool = False,
) -> list[MemoryRecord]:
    outcome_list = list(outcomes)
    if replace_run:
        return replace_paper_outcome_memory(outcome_list, memory_path)
    if not outcome_list:
        return []

    store = MemoryStore(memory_path)
    stored_records: list[MemoryRecord] = []
    for outcome in outcome_list:
        stored_records.append(store.upsert(_paper_memory_record(outcome)))
    return stored_records


def persist_validation_evidence_memory(
    evidence_items: Iterable[ValidationEvidence],
    memory_path: str | Path,
    run_id: str,
) -> list[MemoryRecord]:
    evidence_list = list(evidence_items)
    if not evidence_list:
        return []
    _validate_evidence_run_ids(evidence_list, run_id)

    store = MemoryStore(memory_path)
    stored_records: list[MemoryRecord] = []
    for evidence in evidence_list:
        stored_records.append(store.upsert(_validation_memory_record(evidence, run_id)))
    return stored_records


def replace_validation_evidence_memory(
    evidence_items: Iterable[ValidationEvidence],
    memory_path: str | Path,
    run_id: str,
) -> list[MemoryRecord]:
    evidence_list = list(evidence_items)
    _validate_evidence_run_ids(evidence_list, run_id)
    records = [_validation_memory_record(evidence, run_id) for evidence in evidence_list]
    if not records and not Path(memory_path).exists():
        return []

    store = MemoryStore(memory_path)
    return store.replace_matching(
        lambda record: _is_replaceable_validation_evidence_record(record, run_id),
        records,
    )


def replace_paper_outcome_memory(
    outcomes: Iterable[PaperSimulationOutcome],
    memory_path: str | Path,
    *,
    run_ids: Iterable[str] | None = None,
) -> list[MemoryRecord]:
    outcome_list = list(outcomes)
    resolved_run_ids = {outcome.run_id for outcome in outcome_list}
    if run_ids is not None:
        resolved_run_ids.update(run_ids)
    if not resolved_run_ids:
        return []
    if not outcome_list and not Path(memory_path).exists():
        return []

    records = [_paper_memory_record(outcome) for outcome in outcome_list]
    store = MemoryStore(memory_path)
    return store.replace_matching(
        lambda record: _is_replaceable_paper_outcome_record(record, resolved_run_ids),
        records,
    )


def _research_loop_memory_records(report: ResearchLoopReport) -> list[MemoryRecord]:
    records: list[MemoryRecord] = []
    for index, hypothesis in enumerate(report.hypotheses):
        curated_hypothesis = _curated_hypothesis(hypothesis)
        records.append(
            MemoryRecord(
                record_id=_record_id(report.run_id, index, hypothesis, curated_hypothesis),
                created_at=DETERMINISTIC_EVENT_TIME_ISO,
                updated_at=DETERMINISTIC_EVENT_TIME_ISO,
                opportunity=_opportunity(report, hypothesis),
                hypothesis=curated_hypothesis,
                score=_score(report, hypothesis),
                rejected_reasons=_rejected_reasons(report, hypothesis),
                tags=_tags(report, hypothesis),
            )
        )
    return records


def _validate_evidence_run_ids(evidence_items: Iterable[ValidationEvidence], run_id: str) -> None:
    for evidence in evidence_items:
        if evidence.run_id is not None and evidence.run_id != run_id:
            raise ValueError(
                "validation evidence run_id does not match supplied run_id: "
                f"{evidence.run_id!r} != {run_id!r}"
            )


def _is_replaceable_research_loop_record(record: MemoryRecord, run_id: str) -> bool:
    return (
        record.record_id.startswith(f"research-loop:{_slug(run_id)}:")
        and "research-loop" in record.tags
        and run_id in record.tags
    )


def _is_replaceable_validation_evidence_record(record: MemoryRecord, run_id: str) -> bool:
    return (
        (record.opportunity or {}).get("run_id") == run_id
        and "validation-evidence" in record.tags
    )


def _is_replaceable_paper_outcome_record(
    record: MemoryRecord, run_ids: set[str]
) -> bool:
    return (
        (record.record_id.startswith("paper-outcome:") or "paper-evidence" in record.tags)
        and (record.opportunity or {}).get("run_id") in run_ids
        and "paper-evidence" in record.tags
    )


def _validation_memory_record(evidence: ValidationEvidence, run_id: str) -> MemoryRecord:
    return MemoryRecord(
        record_id=f"validation:{run_id}:{evidence.evidence_id}",
        created_at=DETERMINISTIC_EVENT_TIME_ISO,
        updated_at=DETERMINISTIC_EVENT_TIME_ISO,
        opportunity=_validation_opportunity(evidence, run_id),
        hypothesis=_validation_hypothesis(evidence),
        score=_validation_score(evidence),
        rejected_reasons=_validation_rejected_reasons(evidence),
        tags=_validation_tags(evidence, run_id),
    )


def _validation_opportunity(evidence: ValidationEvidence, run_id: str) -> dict[str, Any]:
    return {
        "strategy_family": evidence.strategy_family,
        "symbol": evidence.symbol,
        "timeframe": evidence.timeframe,
        "validator": evidence.validator_name,
        "run_id": run_id,
        "uses_real_capital": False,
        "live_order_routing": False,
    }


def _validation_hypothesis(evidence: ValidationEvidence) -> dict[str, Any]:
    blocked_reasons = list(evidence.blocked_reasons)
    return {
        "lesson": "validation_approved" if evidence.approved else "validation_blocked",
        "metrics": _validation_score(evidence),
        "blocked_reasons": blocked_reasons,
        "disconfirmation_hints": blocked_reasons,
    }


def _validation_score(evidence: ValidationEvidence) -> dict[str, Any]:
    return {
        "trade_count": evidence.trade_count,
        "net_return": evidence.net_return,
        "gross_expectancy": evidence.gross_expectancy,
        "fee_adjusted_expectancy": evidence.fee_adjusted_expectancy,
        "slippage_adjusted_expectancy": evidence.slippage_adjusted_expectancy,
        "max_drawdown": evidence.max_drawdown,
        "walk_forward_split_count": evidence.walk_forward_split_count,
        "walk_forward_pass_rate": evidence.walk_forward_pass_rate,
    }


def _validation_rejected_reasons(evidence: ValidationEvidence) -> list[str]:
    if evidence.approved:
        return []
    return list(evidence.blocked_reasons)


def _validation_tags(evidence: ValidationEvidence, run_id: str) -> list[str]:
    outcome = "approved" if evidence.approved else "blocked"
    return _unique_non_empty(
        [
            "validation-evidence",
            evidence.strategy_family,
            _slug(evidence.symbol),
            outcome,
            run_id,
        ]
    )


def _paper_memory_record(outcome: PaperSimulationOutcome) -> MemoryRecord:
    return MemoryRecord(
        record_id=f"paper-outcome:{outcome.run_id}:{outcome.outcome_id}",
        created_at=DETERMINISTIC_EVENT_TIME_ISO,
        updated_at=DETERMINISTIC_EVENT_TIME_ISO,
        opportunity=_paper_opportunity(outcome),
        hypothesis=_paper_hypothesis(outcome),
        score=_paper_score(outcome),
        rejected_reasons=_paper_rejected_reasons(outcome),
        paper_trade_outcome=outcome.model_dump(mode="json"),
        tags=_paper_tags(outcome),
    )


def _record_id(
    run_id: str, index: int, hypothesis: AlphaHypothesis, curated_hypothesis: dict[str, Any]
) -> str:
    metric = hypothesis.evidence[0].metric if hypothesis.evidence else "unknown"
    identity_hash = _short_hash(curated_hypothesis)
    return (
        f"research-loop:{_slug(run_id)}:{index}:"
        f"{_slug(hypothesis.asset)}:{_slug(hypothesis.category)}:{_slug(metric)}:"
        f"{identity_hash}"
    )


def _paper_opportunity(outcome: PaperSimulationOutcome) -> dict[str, Any]:
    return {
        "strategy_family": outcome.strategy_family,
        "symbol": outcome.symbol,
        "run_id": outcome.run_id,
        "candidate_id": outcome.candidate_id,
        "status": outcome.status,
        "notional": outcome.notional_usd,
        "notional_usd": outcome.notional_usd,
        "uses_real_capital": False,
        "live_order_routing": False,
    }


def _paper_hypothesis(outcome: PaperSimulationOutcome) -> dict[str, Any]:
    return {
        "paper_status": outcome.status,
        "net_pnl_usd": outcome.net_pnl_usd,
        "fees_usd": outcome.fees_usd,
        "slippage_usd": outcome.slippage_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _paper_score(outcome: PaperSimulationOutcome) -> dict[str, Any]:
    return {
        "entry_price": outcome.entry_price,
        "exit_price": outcome.exit_price,
        "quantity": outcome.quantity,
        "notional_usd": outcome.notional_usd,
        "gross_pnl_usd": outcome.gross_pnl_usd,
        "fees_usd": outcome.fees_usd,
        "slippage_usd": outcome.slippage_usd,
        "net_pnl_usd": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
    }


def _paper_rejected_reasons(outcome: PaperSimulationOutcome) -> list[str]:
    if outcome.status in {"blocked", "failed"}:
        return list(outcome.failure_reasons)
    return []


def _paper_tags(outcome: PaperSimulationOutcome) -> list[str]:
    return _unique_non_empty(
        [
            "paper-evidence",
            outcome.strategy_family,
            _slug(outcome.symbol),
            outcome.status,
            outcome.run_id,
        ]
    )


def _curated_hypothesis(hypothesis: AlphaHypothesis) -> dict[str, Any]:
    return {
        "source": hypothesis.source,
        "category": hypothesis.category,
        "asset": hypothesis.asset,
        "what_changed": hypothesis.what_changed,
        "why_it_might_be_edge": hypothesis.why_it_might_be_edge,
        "evidence": [_curated_evidence(evidence) for evidence in hypothesis.evidence],
        "expected_persistence_seconds": hypothesis.expected_persistence_seconds,
        "disconfirmation_tests": list(hypothesis.disconfirmation_tests),
        "disconfirmation_criteria": [
            criterion.model_dump(mode="python") for criterion in hypothesis.disconfirmation_criteria
        ],
        "action_mode": hypothesis.action_mode,
        "actionability": hypothesis.actionability,
        "venue": hypothesis.venue,
        "chain": hypothesis.chain,
        "protocol": hypothesis.protocol,
    }


def _curated_evidence(evidence: EvidenceBundle) -> dict[str, Any]:
    raw = evidence.raw
    raw_keys = sorted(str(key) for key in raw)
    return {
        "source": evidence.source,
        "category": evidence.category,
        "asset": evidence.asset,
        "metric": evidence.metric,
        "value": evidence.value,
        "signal_evidence": list(evidence.signal_evidence),
        "raw_keys": raw_keys,
        "raw_sha256": _sha256(raw) if raw else None,
        "raw_omitted": bool(raw),
        "anomaly_classification": evidence.anomaly_classification,
        "anomaly_score": evidence.anomaly_score,
        "executable": evidence.executable,
        "persistence_seconds": evidence.persistence_seconds,
        "anomaly_reasons": list(evidence.anomaly_reasons),
        "venue": evidence.venue,
        "chain": evidence.chain,
        "protocol": evidence.protocol,
        "z_score": evidence.z_score,
        "deviation": evidence.deviation,
    }


def _opportunity(report: ResearchLoopReport, hypothesis: AlphaHypothesis) -> dict[str, Any]:
    return {
        "run_id": report.run_id,
        "source_filter": report.source_filter,
        "record_type_filter": report.record_type_filter,
        "source": hypothesis.source,
        "category": hypothesis.category,
        "asset": hypothesis.asset,
        "venue": hypothesis.venue,
        "chain": hypothesis.chain,
        "protocol": hypothesis.protocol,
        "current_capital_usd": report.current_capital_usd,
        "actionability": hypothesis.actionability,
        "expected_persistence_seconds": hypothesis.expected_persistence_seconds,
        "uses_real_capital": report.uses_real_capital,
        "live_order_routing": report.live_order_routing,
    }


def _score(report: ResearchLoopReport, hypothesis: AlphaHypothesis) -> dict[str, Any]:
    return {
        "report_counts": {
            "loaded_records": report.loaded_records,
            "signal_count": report.signal_count,
            "anomaly_count": report.anomaly_count,
            "hypothesis_count": report.hypothesis_count,
            "weak_signal_count": report.weak_signal_count,
            "blocked_hypothesis_count": report.blocked_hypothesis_count,
        },
        "validation_summaries": [
            summary.model_dump(mode="python")
            for summary in _validation_summaries_for_asset(report, hypothesis.asset)
        ],
        "notes": list(report.notes),
    }


def _rejected_reasons(report: ResearchLoopReport, hypothesis: AlphaHypothesis) -> list[str]:
    if hypothesis.actionability == "executable":
        return []

    reasons: list[str] = ["hypothesis_blocked"]
    for evidence in hypothesis.evidence:
        reasons.extend(evidence.anomaly_reasons)
    for summary in _validation_summaries_for_asset(report, hypothesis.asset):
        if summary.status == "blocked":
            reasons.extend(summary.blocked_reasons)
    return _unique_non_empty(reasons)


def _tags(report: ResearchLoopReport, hypothesis: AlphaHypothesis) -> list[str]:
    outcome = "accepted" if hypothesis.actionability == "executable" else "blocked"
    metric = hypothesis.evidence[0].metric if hypothesis.evidence else "unknown"
    return _unique_non_empty(
        [
            "research-loop",
            report.run_id,
            _slug(hypothesis.asset),
            _slug(hypothesis.category),
            _slug(metric),
            hypothesis.actionability,
            outcome,
            *report.decision_reason_codes,
        ]
    )


def _validation_summaries_for_asset(
    report: ResearchLoopReport, asset: str
) -> list[ValidationSummary]:
    return [summary for summary in report.validation_summaries if summary.asset == asset]


def _slug(value: str) -> str:
    return SLUG_PATTERN.sub("-", value.lower()).strip("-") or "unknown"


def _short_hash(value: dict[str, Any]) -> str:
    return _sha256(value)[:12]


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
