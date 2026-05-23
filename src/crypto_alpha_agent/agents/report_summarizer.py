from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from crypto_alpha_agent.agents.llm_contracts import UNSAFE_TEXT_PATTERNS

ReportType = Literal["daily", "weekly"]
SummaryLLM = Callable[[Any], Any]


class _StrictSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class EvidenceReportSummaryTask(_StrictSummaryModel):
    task_id: str = Field(min_length=1)
    report_type: ReportType
    objective: str = Field(min_length=1)
    deterministic_report: dict[str, Any]
    constraints: list[str] = Field(default_factory=list)


class EvidenceReportNarrativeSummary(_StrictSummaryModel):
    report_type: ReportType
    summary: str = Field(min_length=1, max_length=1200)
    metric_refs: list[str] = Field(min_length=1, max_length=8)
    caveats: list[str] = Field(default_factory=list, max_length=8)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @model_validator(mode="after")
    def _reject_unsafe_values(self) -> "EvidenceReportNarrativeSummary":
        _reject_unsafe_string_values(
            {
                "summary": self.summary,
                "metric_refs": self.metric_refs,
                "caveats": self.caveats,
            }
        )
        return self


class EvidenceReportSummaryResult(_StrictSummaryModel):
    accepted: bool
    summary: EvidenceReportNarrativeSummary | None = None
    rejected_reason_codes: list[str] = Field(default_factory=list)
    llm_response_metadata: dict[str, Any] = Field(default_factory=dict)


def summarize_evidence_report(
    report: Any,
    *,
    report_type: ReportType,
    llm: SummaryLLM,
) -> EvidenceReportSummaryResult:
    task = EvidenceReportSummaryTask(
        task_id=f"evidence-report-summary:{report_type}",
        report_type=report_type,
        objective=(
            "Write a concise narrative summary from deterministic evidence metrics. "
            "Do not invent metrics, do not change decisions, and do not request execution."
        ),
        deterministic_report=report.model_dump(mode="json"),
        constraints=[
            "Use only deterministic_report values.",
            "Keep deterministic validation, paper, data-quality, and cost metrics as source of truth.",
            "Return only valid JSON.",
        ],
    )
    raw_response = llm(task)
    metadata = _raw_response_metadata(raw_response, accepted=False)
    if not isinstance(raw_response, str):
        return EvidenceReportSummaryResult(
            accepted=False,
            rejected_reason_codes=["invalid_llm_response_type"],
            llm_response_metadata=metadata,
        )

    try:
        payload = json.loads(raw_response, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        return EvidenceReportSummaryResult(
            accepted=False,
            rejected_reason_codes=["invalid_json"],
            llm_response_metadata=metadata,
        )

    try:
        summary = EvidenceReportNarrativeSummary.model_validate(payload)
    except (ValidationError, ValueError):
        return EvidenceReportSummaryResult(
            accepted=False,
            rejected_reason_codes=["invalid_summary"],
            llm_response_metadata=metadata,
        )

    return EvidenceReportSummaryResult(
        accepted=True,
        summary=summary,
        rejected_reason_codes=[],
        llm_response_metadata=_raw_response_metadata(raw_response, accepted=True),
    )


def _raw_response_metadata(raw_response: Any, *, accepted: bool) -> dict[str, Any]:
    metadata: dict[str, Any] = {
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


def _reject_unsafe_string_values(value: Any) -> None:
    if isinstance(value, str):
        for term, pattern in UNSAFE_TEXT_PATTERNS:
            if pattern.search(value):
                raise ValueError(f"unsafe report summary text contains prohibited term: {term}")
        return
    if isinstance(value, list | tuple | set):
        for item in value:
            _reject_unsafe_string_values(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            _reject_unsafe_string_values(item)
