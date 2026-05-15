from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.observability.logging import ObservabilityEvent


class MetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    sum: float
    minimum: float
    maximum: float
    average: float


class ReportEventDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    event_type: str
    run_id: str
    opportunity_id: str | None = None
    idea_id: str | None = None
    decision: str | None = None
    action: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)


class DailyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    total_events: int = Field(ge=0)
    event_type_counts: dict[str, int]
    decision_counts: dict[str, int]
    action_counts: dict[str, int]
    approvals: int = Field(ge=0)
    blocks: int = Field(ge=0)
    reason_code_counts: dict[str, int]
    metrics: dict[str, MetricSummary]
    events: list[ReportEventDetail]
    skipped_event_lines: int = Field(default=0, ge=0)


def generate_daily_report(
    events: list[ObservabilityEvent],
    report_date: str | date,
    *,
    skipped_event_lines: int = 0,
) -> DailyReport:
    day = date.fromisoformat(report_date) if isinstance(report_date, str) else report_date
    daily_events = sorted(
        (event for event in events if event.date == day),
        key=lambda event: (event.timestamp, event.event_type, event.run_id),
    )

    event_type_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    reason_code_counts: Counter[str] = Counter()
    metric_values: dict[str, list[float]] = defaultdict(list)
    details: list[ReportEventDetail] = []

    for event in daily_events:
        event_type_counts[event.event_type] += 1
        if event.decision:
            decision_counts[event.decision] += 1
        if event.action:
            action_counts[event.action] += 1
        reason_code_counts.update(event.reason_codes)
        for metric_name, value in event.metrics.items():
            metric_values[metric_name].append(value)
        details.append(
            ReportEventDetail(
                timestamp=event.timestamp.isoformat(),
                event_type=event.event_type,
                run_id=event.run_id,
                opportunity_id=event.opportunity_id,
                idea_id=event.idea_id,
                decision=event.decision,
                action=event.action,
                reason_codes=event.reason_codes,
                metrics=event.metrics,
                evidence_refs=event.evidence_refs,
                artifact_refs=event.artifact_refs,
            )
        )

    return DailyReport(
        date=day,
        total_events=len(daily_events),
        event_type_counts=dict(sorted(event_type_counts.items())),
        decision_counts=dict(sorted(decision_counts.items())),
        action_counts=dict(sorted(action_counts.items())),
        approvals=decision_counts["approve"],
        blocks=decision_counts["block"],
        reason_code_counts=dict(sorted(reason_code_counts.items())),
        metrics=_summarize_metrics(metric_values),
        events=details,
        skipped_event_lines=skipped_event_lines,
    )


def _summarize_metrics(metric_values: dict[str, list[float]]) -> dict[str, MetricSummary]:
    summaries: dict[str, MetricSummary] = {}
    for metric_name, values in sorted(metric_values.items()):
        total = sum(values)
        summaries[metric_name] = MetricSummary(
            count=len(values),
            sum=total,
            minimum=min(values),
            maximum=max(values),
            average=total / len(values),
        )
    return summaries
