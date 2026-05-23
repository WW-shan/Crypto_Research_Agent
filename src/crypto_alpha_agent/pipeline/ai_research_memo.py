from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.pipeline.evidence_reports import build_weekly_evidence_report
from crypto_alpha_agent.pipeline.experiment_planner import ExperimentProposal, StrategyTemplateProposal, plan_next_experiments


class AIResearchMemo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    memo_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    what_changed: list[str] = Field(min_length=1)
    what_failed: list[str] = Field(min_length=1)
    what_should_stop: list[str] = Field(min_length=1)
    next_experiment: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    rejected_reason_codes: list[str] = Field(default_factory=list)
    accepted_proposals: list[ExperimentProposal] = Field(default_factory=list)
    strategy_template_proposals: list[StrategyTemplateProposal] = Field(default_factory=list)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_ai_research_memo(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    strategy_family: str | None = None,
    current_capital_usd: float = 300.0,
) -> AIResearchMemo:
    report = build_weekly_evidence_report(db_path=db_path, memory_path=memory_path)
    plan = plan_next_experiments(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family=strategy_family,
        current_capital_usd=current_capital_usd,
        offline_only=True,
    )
    what_changed = _what_changed(report)
    what_failed = _what_failed(report, plan.rejected_reason_codes)
    what_should_stop = _what_should_stop(report)
    next_experiment = _next_experiment(plan)
    evidence_refs = _dedupe(
        ref
        for proposal in [*plan.proposals, *plan.strategy_template_proposals]
        for ref in proposal.evidence_refs
    )
    memo_payload = {
        "what_changed": what_changed,
        "what_failed": what_failed,
        "what_should_stop": what_should_stop,
        "next_experiment": next_experiment,
        "evidence_refs": evidence_refs,
        "rejected_reason_codes": plan.rejected_reason_codes,
    }
    return AIResearchMemo(
        memo_id=f"ai-research-memo-{_short_hash(memo_payload)}",
        generated_at=DETERMINISTIC_EVENT_TIME_ISO,
        what_changed=what_changed,
        what_failed=what_failed,
        what_should_stop=what_should_stop,
        next_experiment=next_experiment,
        evidence_refs=evidence_refs,
        rejected_reason_codes=list(plan.rejected_reason_codes),
        accepted_proposals=list(plan.proposals),
        strategy_template_proposals=list(plan.strategy_template_proposals),
    )


def _what_changed(report: object) -> list[str]:
    summaries = getattr(report, "family_summaries", [])
    if not summaries:
        return ["No weekly family evidence has been accumulated yet."]
    changed: list[str] = []
    for summary in summaries:
        changed.append(
            f"{summary.strategy_family}: sample_size={summary.sample_size}, "
            f"validation_count={summary.validation_count}, action={summary.recommended_action}"
        )
    return changed


def _what_failed(report: object, planner_rejections: list[str]) -> list[str]:
    failed = list(getattr(report, "top_rejected_reasons", []))
    failed.extend(planner_rejections)
    return _dedupe(failed) or ["No failed evidence has been recorded yet."]


def _what_should_stop(report: object) -> list[str]:
    stopped = list(getattr(report, "degraded_families", []))
    for summary in getattr(report, "family_summaries", []):
        if summary.recommended_action == "stop":
            stopped.append(summary.strategy_family)
    return _dedupe(stopped) or ["No strategy family should stop based on current weekly evidence."]


def _next_experiment(plan: object) -> list[str]:
    proposals = getattr(plan, "proposals", [])
    if proposals:
        return [
            f"{proposal.strategy_family}: {proposal.expected_edge_mechanism}"
            for proposal in proposals
        ]
    templates = getattr(plan, "strategy_template_proposals", [])
    if templates:
        return [
            f"{proposal.strategy_family}: design {proposal.proposed_validator_name}"
            for proposal in templates
        ]
    return ["Collect supported public data before proposing another experiment."]


def _short_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def _dedupe(values: object) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped
