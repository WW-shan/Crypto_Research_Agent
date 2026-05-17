from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.quality import build_data_quality_report
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.pipeline.experiment_planner import ExperimentPlannerResult, plan_next_experiments

PAPER_SAMPLE_TARGET = 30
NEAR_PAPER_TRADE_COUNT = 25
NEAR_TINY_LIVE_SAMPLE_SIZE = 25
_DEGRADED_MARKERS = {
    "degraded",
    "degraded_expectancy",
    "fee_killed_edge",
    "negative_expectancy",
}
_FAILED_STATUSES = {"failed", "rejected", "blocked"}


class FamilyEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    sample_size: int = Field(ge=0)
    closed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    net_pnl_usd: float
    validation_count: int = Field(ge=0)
    rejected_reasons: list[str] = Field(default_factory=list)
    near_tiny_live_review: bool = False


class DailyEvidenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    strategy_families: list[str]
    validation_evidence_count: int = Field(ge=0)
    paper_evidence_count: int = Field(ge=0)
    paper_outcome_count: int = Field(ge=0)
    memory_record_count: int = Field(ge=0)
    new_candidate_count: int = Field(ge=0)
    blocked_candidate_count: int = Field(ge=0)
    data_quality_issue_count: int = Field(ge=0)
    next_experiments: ExperimentPlannerResult
    should_continue: bool
    should_stop_family: bool
    should_collect_more_data: bool
    near_paper_eligibility: bool
    near_tiny_live_review: bool
    reason_codes: list[str] = Field(default_factory=list)
    uses_real_capital: bool = False
    live_order_routing: bool = False


class WeeklyEvidenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    family_summaries: list[FamilyEvidenceSummary]
    top_rejected_reasons: list[str]
    best_improving_family: str | None = None
    degraded_families: list[str]
    sample_size_progress: dict[str, int]
    should_continue: bool
    should_stop_family: bool
    should_collect_more_data: bool
    near_paper_eligibility: bool
    near_tiny_live_review: bool
    reason_codes: list[str] = Field(default_factory=list)
    uses_real_capital: bool = False
    live_order_routing: bool = False


def build_daily_evidence_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    strategy_families: list[str] | None = None,
) -> DailyEvidenceReport:
    families = _normalize_families(strategy_families)
    validation_evidence = _load_validation_evidence(db_path, families)
    paper_outcomes = _load_paper_outcomes(db_path, families)
    paper_packages = aggregate_paper_evidence(_paper_evidence_mapping(outcome) for outcome in paper_outcomes)
    memory_records = _filtered_memory_records(MemoryStore(memory_path).list_records(), families)
    data_quality_report = build_data_quality_report(ResearchDataStore(db_path).load_records())
    next_experiments = plan_next_experiments(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family=families[0] if len(families) == 1 else None,
        offline_only=True,
    )

    near_paper_eligibility = _near_paper_eligibility(validation_evidence)
    near_tiny_live_review = any(
        package.sample_size >= NEAR_TINY_LIVE_SAMPLE_SIZE
        for package in paper_packages
    )
    should_collect_more_data = (
        any(package.sample_size < PAPER_SAMPLE_TARGET for package in paper_packages)
        or not paper_packages
        or bool(data_quality_report.issues)
    )
    should_stop_family = _should_stop_family(families, memory_records)

    return DailyEvidenceReport(
        strategy_families=families,
        validation_evidence_count=len(validation_evidence),
        paper_evidence_count=len(paper_packages),
        paper_outcome_count=len(paper_outcomes),
        memory_record_count=len(memory_records),
        new_candidate_count=sum(1 for record in memory_records if _is_new_candidate(record)),
        blocked_candidate_count=sum(1 for record in memory_records if _is_blocked_candidate(record)),
        data_quality_issue_count=len(data_quality_report.issues),
        next_experiments=next_experiments,
        should_continue=not should_stop_family,
        should_stop_family=should_stop_family,
        should_collect_more_data=should_collect_more_data,
        near_paper_eligibility=near_paper_eligibility,
        near_tiny_live_review=near_tiny_live_review,
        reason_codes=_daily_reason_codes(
            validation_evidence=validation_evidence,
            paper_packages=paper_packages,
            memory_records=memory_records,
            data_quality_issue_count=len(data_quality_report.issues),
            next_experiments=next_experiments,
            should_collect_more_data=should_collect_more_data,
        ),
    )


def build_weekly_evidence_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
) -> WeeklyEvidenceReport:
    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence()
    paper_outcomes = PaperOutcomeLedger(db_path).load_outcomes()
    paper_packages = aggregate_paper_evidence(_paper_evidence_mapping(outcome) for outcome in paper_outcomes)
    memory_records = MemoryStore(memory_path).list_records()
    families = sorted(
        {
            *[item.strategy_family for item in validation_evidence],
            *[outcome.strategy_family for outcome in paper_outcomes],
            *[_record_strategy_family(record) for record in memory_records if _record_strategy_family(record)],
        }
    )

    validation_by_family: dict[str, list[ValidationEvidence]] = defaultdict(list)
    for item in validation_evidence:
        validation_by_family[item.strategy_family].append(item)
    packages_by_family = {package.strategy_family: package for package in paper_packages}
    memory_by_family: dict[str, list[MemoryRecord]] = defaultdict(list)
    for record in memory_records:
        family = _record_strategy_family(record)
        if family:
            memory_by_family[family].append(record)

    summaries = [
        _family_summary(
            family,
            package=packages_by_family.get(family),
            validation=validation_by_family.get(family, []),
            memory_records=memory_by_family.get(family, []),
        )
        for family in families
    ]
    summaries.sort(key=lambda summary: summary.strategy_family)

    rejected_reason_counts = Counter[str]()
    for summary in summaries:
        rejected_reason_counts.update(summary.rejected_reasons)
    top_rejected_reasons = [
        reason
        for reason, _count in sorted(
            rejected_reason_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    degraded_families = [
        summary.strategy_family
        for summary in summaries
        if _family_is_degraded(summary, memory_by_family.get(summary.strategy_family, []))
    ]
    best_improving_family = _best_improving_family(summaries, degraded_families)
    near_paper_eligibility = _near_paper_eligibility(validation_evidence)
    near_tiny_live_review = any(summary.near_tiny_live_review for summary in summaries)
    should_collect_more_data = any(
        summary.sample_size < PAPER_SAMPLE_TARGET for summary in summaries
    ) or not summaries
    should_stop_family = bool(families) and len(degraded_families) == len(families)

    return WeeklyEvidenceReport(
        family_summaries=summaries,
        top_rejected_reasons=top_rejected_reasons,
        best_improving_family=best_improving_family,
        degraded_families=degraded_families,
        sample_size_progress={
            summary.strategy_family: min(summary.sample_size, PAPER_SAMPLE_TARGET)
            for summary in summaries
        },
        should_continue=not should_stop_family,
        should_stop_family=should_stop_family,
        should_collect_more_data=should_collect_more_data,
        near_paper_eligibility=near_paper_eligibility,
        near_tiny_live_review=near_tiny_live_review,
        reason_codes=_weekly_reason_codes(
            summaries=summaries,
            top_rejected_reasons=top_rejected_reasons,
            best_improving_family=best_improving_family,
            degraded_families=degraded_families,
            should_collect_more_data=should_collect_more_data,
        ),
    )


def _normalize_families(strategy_families: list[str] | None) -> list[str]:
    if not strategy_families:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for family in strategy_families:
        stripped = family.strip()
        if stripped and stripped not in seen:
            normalized.append(stripped)
            seen.add(stripped)
    return normalized


def _load_validation_evidence(
    db_path: str | Path,
    families: list[str],
) -> list[ValidationEvidence]:
    ledger = ValidationEvidenceLedger(db_path)
    if not families:
        return ledger.load_evidence()
    evidence: list[ValidationEvidence] = []
    for family in families:
        evidence.extend(ledger.load_evidence(strategy_family=family))
    return evidence


def _load_paper_outcomes(
    db_path: str | Path,
    families: list[str],
) -> list[PaperSimulationOutcome]:
    ledger = PaperOutcomeLedger(db_path)
    if not families:
        return ledger.load_outcomes()
    outcomes: list[PaperSimulationOutcome] = []
    for family in families:
        outcomes.extend(ledger.load_outcomes(strategy_family=family))
    return outcomes


def _paper_evidence_mapping(outcome: PaperSimulationOutcome) -> dict[str, Any]:
    return {
        "strategy_family": outcome.strategy_family,
        "trade_id": outcome.outcome_id,
        "symbol": outcome.symbol,
        "status": outcome.status,
        "realized_net_pnl": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _filtered_memory_records(
    records: list[MemoryRecord],
    families: list[str],
) -> list[MemoryRecord]:
    if not families:
        return records
    family_set = set(families)
    return [
        record
        for record in records
        if _record_strategy_family(record) in family_set
    ]


def _record_strategy_family(record: MemoryRecord) -> str | None:
    for payload in (
        record.opportunity,
        record.hypothesis,
        record.score,
        record.backtest_artifacts,
        record.paper_trade_outcome,
    ):
        if isinstance(payload, dict):
            family = payload.get("strategy_family")
            if isinstance(family, str) and family.strip():
                return family.strip()
    return None


def _is_new_candidate(record: MemoryRecord) -> bool:
    return "new_candidate" in record.tags or (
        "candidate" in record.tags and not record.rejected_reasons
    )


def _is_blocked_candidate(record: MemoryRecord) -> bool:
    return "blocked_candidate" in record.tags or bool(record.rejected_reasons)


def _near_paper_eligibility(validation_evidence: list[ValidationEvidence]) -> bool:
    return any(
        item.approved and item.trade_count >= NEAR_PAPER_TRADE_COUNT
        for item in validation_evidence
    )


def _should_stop_family(
    families: list[str],
    memory_records: list[MemoryRecord],
) -> bool:
    if not families:
        return False
    degraded = {
        _record_strategy_family(record)
        for record in memory_records
        if _record_strategy_family(record) in families and _has_degraded_marker(record)
    }
    return bool(degraded) and degraded.issuperset(families)


def _has_degraded_marker(record: MemoryRecord) -> bool:
    tokens = {*record.tags, *record.rejected_reasons}
    return bool(tokens.intersection(_DEGRADED_MARKERS))


def _family_summary(
    family: str,
    *,
    package: PaperEvidencePackage | None,
    validation: list[ValidationEvidence],
    memory_records: list[MemoryRecord],
) -> FamilyEvidenceSummary:
    rejected_reasons = _dedupe(
        [
            *[
                reason
                for item in validation
                for reason in item.blocked_reasons
            ],
            *([] if package is None else package.failure_reasons),
            *[
                reason
                for record in memory_records
                for reason in record.rejected_reasons
            ],
        ]
    )
    sample_size = 0 if package is None else package.sample_size
    return FamilyEvidenceSummary(
        strategy_family=family,
        sample_size=sample_size,
        closed_count=0 if package is None else package.closed_count,
        failed_count=0 if package is None else package.failed_count,
        blocked_count=0 if package is None else package.blocked_count,
        net_pnl_usd=0.0 if package is None else package.net_pnl_usd,
        validation_count=len(validation),
        rejected_reasons=rejected_reasons,
        near_tiny_live_review=sample_size >= NEAR_TINY_LIVE_SAMPLE_SIZE,
    )


def _family_is_degraded(
    summary: FamilyEvidenceSummary,
    memory_records: list[MemoryRecord],
) -> bool:
    if any(_has_degraded_marker(record) for record in memory_records):
        return True
    return summary.failed_count >= 3 and summary.failed_count >= summary.closed_count


def _best_improving_family(
    summaries: list[FamilyEvidenceSummary],
    degraded_families: list[str],
) -> str | None:
    candidates = [
        summary
        for summary in summaries
        if summary.strategy_family not in set(degraded_families)
        and (summary.net_pnl_usd > 0 or summary.closed_count > summary.failed_count)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda summary: (
            summary.net_pnl_usd,
            summary.closed_count - summary.failed_count,
            summary.validation_count,
            summary.strategy_family,
        ),
        reverse=True,
    )
    return candidates[0].strategy_family


def _daily_reason_codes(
    *,
    validation_evidence: list[ValidationEvidence],
    paper_packages: list[PaperEvidencePackage],
    memory_records: list[MemoryRecord],
    data_quality_issue_count: int,
    next_experiments: ExperimentPlannerResult,
    should_collect_more_data: bool,
) -> list[str]:
    codes = ["validation" if validation_evidence else "no_validation_evidence"]
    codes.append("paper_evidence" if paper_packages else "no_paper_evidence")
    codes.append("memory" if memory_records else "no_memory_records")
    if data_quality_issue_count:
        codes.append("data_quality_issues")
    if next_experiments.proposals:
        codes.append("next_experiments")
    if should_collect_more_data:
        codes.append("collect_more_data")
    return _dedupe(codes)


def _weekly_reason_codes(
    *,
    summaries: list[FamilyEvidenceSummary],
    top_rejected_reasons: list[str],
    best_improving_family: str | None,
    degraded_families: list[str],
    should_collect_more_data: bool,
) -> list[str]:
    codes = ["weekly_aggregation" if summaries else "no_family_evidence"]
    if top_rejected_reasons:
        codes.append("rejected_reasons")
    if best_improving_family is not None:
        codes.append("best_improving_family")
    if degraded_families:
        codes.append("degraded_family")
    if should_collect_more_data:
        codes.append("collect_more_data")
    return _dedupe(codes)


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
