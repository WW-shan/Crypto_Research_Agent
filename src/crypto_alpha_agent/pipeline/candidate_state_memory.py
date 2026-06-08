from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.pipeline.evidence_universe import UniverseSourceCoverage
from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
    CandidateFeasibilityMetric,
    MultiHypothesisFeasibilityReport,
)

CandidateState = Literal[
    "candidate",
    "source_qualified",
    "feasibility_passed",
    "backtest_passed",
    "paper_collecting",
    "stopped",
    "redesign_required",
]

CURRENT_DERIVATIVES_CANDIDATES: tuple[str, ...] = (
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
)
_LEGACY_DERIVATIVES_REJECTION_REASON = "non_positive_cost_adjusted_expectancy"
_HARD_BLOCKERS = {
    "non_positive_cost_adjusted_expectancy",
    "unstable_walk_forward_performance",
    "cost_sensitivity_fragile",
    "single_asset_or_time_window_dependency",
    "lookahead_risk",
    "watchlist_only_source",
}


class CandidateStateMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    record_id: str
    candidate_id: str
    state: CandidateState
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_coverage: dict[str, dict[str, Any]] = Field(default_factory=dict)
    feasibility_summary: dict[str, Any] = Field(default_factory=dict)
    last_seen_at: datetime
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def persist_candidate_state_memory(
    report: MultiHypothesisFeasibilityReport,
    memory_path: str | Path,
    *,
    include_current_derivatives_rejections: bool = True,
) -> list[MemoryRecord]:
    entries = _candidate_state_entries(
        report,
        include_current_derivatives_rejections=include_current_derivatives_rejections,
    )
    if not entries:
        return []

    store = MemoryStore(memory_path)
    existing_created_at = {
        record.record_id: record.created_at
        for record in store.list_records()
        if record.record_id.startswith("candidate-state:")
    }
    records = [
        _memory_record(entry, existing_created_at=existing_created_at.get(entry.record_id))
        for entry in entries
    ]
    return store.replace_matching(
        lambda record: record.record_id.startswith("candidate-state:"),
        records,
    )


def _candidate_state_entries(
    report: MultiHypothesisFeasibilityReport,
    *,
    include_current_derivatives_rejections: bool,
) -> list[CandidateStateMemoryRecord]:
    coverage = _source_coverage_summary(report.universe.source_coverage)
    evidence_refs = _evidence_refs(report)
    entries = [
        _entry_for_metric(
            metric,
            report=report,
            source_coverage=coverage,
            evidence_refs=evidence_refs,
        )
        for metric in report.candidate_metrics
    ]
    if include_current_derivatives_rejections:
        entries.extend(
            _legacy_derivatives_rejection_entry(
                candidate_id,
                report=report,
                source_coverage=coverage,
                evidence_refs=evidence_refs,
            )
            for candidate_id in CURRENT_DERIVATIVES_CANDIDATES
        )
    return entries


def _entry_for_metric(
    metric: CandidateFeasibilityMetric,
    *,
    report: MultiHypothesisFeasibilityReport,
    source_coverage: dict[str, dict[str, Any]],
    evidence_refs: list[str],
) -> CandidateStateMemoryRecord:
    return CandidateStateMemoryRecord(
        record_id=_record_id(metric.candidate),
        candidate_id=metric.candidate,
        state=_state_for_metric(metric),
        reason_codes=list(metric.reason_codes),
        evidence_refs=evidence_refs,
        source_coverage=source_coverage,
        feasibility_summary=_feasibility_summary(metric, report),
        last_seen_at=_aware(report.generated_at),
        uses_real_capital=False,
        live_order_routing=False,
    )


def _legacy_derivatives_rejection_entry(
    candidate_id: str,
    *,
    report: MultiHypothesisFeasibilityReport,
    source_coverage: dict[str, dict[str, Any]],
    evidence_refs: list[str],
) -> CandidateStateMemoryRecord:
    return CandidateStateMemoryRecord(
        record_id=_record_id(candidate_id),
        candidate_id=candidate_id,
        state="redesign_required",
        reason_codes=[_LEGACY_DERIVATIVES_REJECTION_REASON],
        evidence_refs=[*evidence_refs, "derivatives-conditioned-lab:current-candidate-memory"],
        source_coverage=source_coverage,
        feasibility_summary={
            "mode": report.mode,
            "legacy_derivatives_conditioned_candidate": True,
            "blocked_reason": _LEGACY_DERIVATIVES_REJECTION_REASON,
        },
        last_seen_at=_aware(report.generated_at),
        uses_real_capital=False,
        live_order_routing=False,
    )


def _memory_record(
    entry: CandidateStateMemoryRecord,
    *,
    existing_created_at: str | None,
) -> MemoryRecord:
    last_seen_at = entry.last_seen_at.isoformat()
    created_at = existing_created_at or last_seen_at
    return MemoryRecord(
        record_id=entry.record_id,
        created_at=created_at,
        updated_at=last_seen_at,
        opportunity={
            "candidate_id": entry.candidate_id,
            "state": entry.state,
            "last_seen_at": last_seen_at,
            "uses_real_capital": False,
            "live_order_routing": False,
        },
        hypothesis={
            "candidate_id": entry.candidate_id,
            "state": entry.state,
            "reason_codes": list(entry.reason_codes),
            "evidence_refs": list(entry.evidence_refs),
            "uses_real_capital": False,
            "live_order_routing": False,
        },
        score={
            "source_coverage": entry.source_coverage,
            "feasibility_summary": entry.feasibility_summary,
            "last_seen_at": last_seen_at,
        },
        rejected_reasons=list(entry.reason_codes),
        tags=_tags(entry),
    )


def _state_for_metric(metric: CandidateFeasibilityMetric) -> CandidateState:
    if metric.candidate_state_target in {
        "candidate",
        "source_qualified",
        "feasibility_passed",
        "redesign_required",
        "stopped",
        "backtest_passed",
        "paper_collecting",
    }:
        return metric.candidate_state_target
    reason_codes = set(metric.reason_codes)
    return "redesign_required" if reason_codes & _HARD_BLOCKERS else "candidate"


def _feasibility_summary(
    metric: CandidateFeasibilityMetric,
    report: MultiHypothesisFeasibilityReport,
) -> dict[str, Any]:
    return {
        "mode": report.mode,
        "timeframe": report.timeframe,
        "symbols": list(report.symbols),
        "cost_bps_grid": list(report.cost_bps_grid),
        "readiness": metric.readiness,
        "sample_count": metric.sample_count,
        "asset_coverage": dict(metric.asset_coverage),
        "split_coverage": metric.split_coverage,
        "gross_mean": metric.gross_mean,
        "net_mean": metric.net_mean,
        "win_rate": metric.win_rate,
        "turnover": metric.turnover,
        "selected_symbol_counts": dict(metric.selected_symbol_counts),
        "candidate_state_target": metric.candidate_state_target,
    }


def _source_coverage_summary(
    coverage_items: list[UniverseSourceCoverage],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for item in coverage_items:
        key = f"{item.source}:{item.record_type}:{item.feed}"
        summary[key] = {
            "source": item.source,
            "record_type": item.record_type,
            "feed": item.feed,
            "role": item.role,
            "records": item.records,
            "latest_observed_at": item.latest_observed_at.isoformat()
            if item.latest_observed_at is not None
            else None,
            "latest_30_day_limited": item.latest_30_day_limited,
            "source_health_present": item.source_health_present,
            "network_routes": list(item.network_routes),
            "blocked_reasons": list(item.blocked_reasons),
        }
    return summary


def _evidence_refs(report: MultiHypothesisFeasibilityReport) -> list[str]:
    return [
        f"{report.command}:{report.mode}",
        f"timeframe:{report.timeframe}",
    ]


def _tags(entry: CandidateStateMemoryRecord) -> list[str]:
    return _dedupe_preserving_order(
        [
            "candidate-state",
            entry.candidate_id,
            entry.state,
            *entry.reason_codes,
        ]
    )


def _record_id(candidate_id: str) -> str:
    return f"candidate-state:{candidate_id}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dedupe_preserving_order(values) -> list:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
