from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport, ValidationSummary

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def persist_research_loop_memory(
    report: ResearchLoopReport, memory_path: str | Path
) -> list[MemoryRecord]:
    if not report.hypotheses:
        return []

    store = MemoryStore(memory_path)
    stored_records: list[MemoryRecord] = []
    for index, hypothesis in enumerate(report.hypotheses):
        record = MemoryRecord(
            record_id=_record_id(report.run_id, index, hypothesis),
            created_at=DETERMINISTIC_EVENT_TIME_ISO,
            updated_at=DETERMINISTIC_EVENT_TIME_ISO,
            opportunity=_opportunity(report, hypothesis),
            hypothesis=hypothesis.model_dump(mode="python"),
            score=_score(report, hypothesis),
            rejected_reasons=_rejected_reasons(report, hypothesis),
            tags=_tags(report.run_id, hypothesis),
        )
        stored_records.append(store.upsert(record))
    return stored_records


def _record_id(run_id: str, index: int, hypothesis: AlphaHypothesis) -> str:
    metric = hypothesis.evidence[0].metric if hypothesis.evidence else "unknown"
    return (
        f"research-loop:{_slug(run_id)}:{index}:"
        f"{_slug(hypothesis.asset)}:{_slug(hypothesis.category)}:{_slug(metric)}"
    )


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


def _tags(run_id: str, hypothesis: AlphaHypothesis) -> list[str]:
    outcome = "accepted" if hypothesis.actionability == "executable" else "blocked"
    metric = hypothesis.evidence[0].metric if hypothesis.evidence else "unknown"
    return _unique_non_empty(
        [
            "research-loop",
            run_id,
            _slug(hypothesis.asset),
            _slug(hypothesis.category),
            _slug(metric),
            hypothesis.actionability,
            outcome,
        ]
    )


def _validation_summaries_for_asset(
    report: ResearchLoopReport, asset: str
) -> list[ValidationSummary]:
    return [summary for summary in report.validation_summaries if summary.asset == asset]


def _slug(value: str) -> str:
    return SLUG_PATTERN.sub("-", value.lower()).strip("-") or "unknown"


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
