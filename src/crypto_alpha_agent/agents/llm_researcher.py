from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crypto_alpha_agent.agents.llm_contracts import HypothesisProposal, ResearchTask
from crypto_alpha_agent.pipeline.ai_research_context import build_ai_research_context
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport
from crypto_alpha_agent.risk.charter_guard import CharterGuardDecision, guard_generated_idea

LLMCallable = Callable[[ResearchTask], str]


class LLMResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    accepted: bool
    task: ResearchTask
    proposal: HypothesisProposal | None
    guard_decision: CharterGuardDecision | None
    rejected_reason_codes: list[str] = Field(default_factory=list)
    raw_response: str
    prompt_context: dict[str, Any]


def run_llm_research_node(
    report: ResearchLoopReport,
    llm: LLMCallable,
    *,
    task_id: str = "llm-research",
    max_capital_usd: float = 300.0,
    db_path: str | Path | None = None,
    memory_path: str | Path | None = None,
    strategy_family: str | None = None,
) -> LLMResearchResult:
    task = _research_task_from_report(
        report,
        task_id=task_id,
        db_path=db_path,
        memory_path=memory_path,
        strategy_family=strategy_family,
    )
    raw_response = llm(task)

    try:
        proposal = HypothesisProposal.model_validate_json(raw_response)
    except ValidationError as exc:
        reason = "invalid_json" if _is_json_error(exc) else "invalid_proposal"
        return LLMResearchResult(
            accepted=False,
            task=task,
            proposal=None,
            guard_decision=None,
            rejected_reason_codes=[reason],
            raw_response=raw_response,
            prompt_context=task.context,
        )

    guard_decision = guard_generated_idea(
        proposal, max_capital_usd=max_capital_usd
    )
    if not guard_decision.approved:
        return LLMResearchResult(
            accepted=False,
            task=task,
            proposal=proposal,
            guard_decision=guard_decision,
            rejected_reason_codes=list(guard_decision.reason_codes),
            raw_response=raw_response,
            prompt_context=task.context,
        )

    return LLMResearchResult(
        accepted=True,
        task=task,
        proposal=proposal,
        guard_decision=guard_decision,
        rejected_reason_codes=[],
        raw_response=raw_response,
        prompt_context=task.context,
    )


def _research_task_from_report(
    report: ResearchLoopReport,
    *,
    task_id: str,
    db_path: str | Path | None = None,
    memory_path: str | Path | None = None,
    strategy_family: str | None = None,
) -> ResearchTask:
    context = _prompt_context(
        report,
        ai_research_context=_optional_ai_research_context(
            report,
            db_path=db_path,
            memory_path=memory_path,
            strategy_family=strategy_family,
        ),
    )
    return ResearchTask(
        task_id=task_id,
        agent_role="hypothesis_generator",
        objective="Generate one research-only hypothesis from the stored research report.",
        context=context,
        evidence=_evidence_from_context(context),
        allowed_tools=["local_report", "market_history", "charter_guard"],
        network_policy="offline",
        current_capital_usd=report.current_capital_usd,
        requires_human_approval=False,
    )


def _prompt_context(
    report: ResearchLoopReport,
    *,
    ai_research_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = {
        "run_id": report.run_id,
        "source_filter": report.source_filter,
        "record_type_filter": report.record_type_filter,
        "current_capital_usd": report.current_capital_usd,
        "counts": {
            "loaded_records": report.loaded_records,
            "signals": report.signal_count,
            "anomalies": report.anomaly_count,
            "hypotheses": report.hypothesis_count,
            "weak_signals": report.weak_signal_count,
            "blocked_hypotheses": report.blocked_hypothesis_count,
            "validation_summaries": len(report.validation_summaries),
        },
        "safety": {
            "uses_real_capital": report.uses_real_capital,
            "execution_enabled": report.live_order_routing,
        },
        "notes": list(report.notes[:10]),
        "signals": [_signal_summary(signal) for signal in report.signals[:10]],
        "hypotheses": [
            _hypothesis_summary(hypothesis) for hypothesis in report.hypotheses[:10]
        ],
        "validation_summaries": [
            summary.model_dump(mode="python")
            for summary in report.validation_summaries[:10]
        ],
    }
    if ai_research_context is not None:
        context["ai_research_context"] = ai_research_context
    return context


def _signal_summary(signal: Any) -> dict[str, Any]:
    return {
        "category": signal.category,
        "source": signal.source,
        "asset": signal.asset,
        "metric": signal.metric,
        "value": signal.value,
        "evidence": list(signal.evidence[:5]),
        "venue": signal.venue,
        "chain": signal.chain,
        "protocol": signal.protocol,
        "z_score": signal.z_score,
        "deviation": signal.deviation,
        "persistence_seconds": signal.persistence_seconds,
        "liquidity_usd": signal.liquidity_usd,
        "capital_required_usd": signal.capital_required_usd,
        "speed_dependency": signal.speed_dependency,
        "rpc_dependency": signal.rpc_dependency,
        "weak_signal": signal.weak_signal,
    }


def _hypothesis_summary(hypothesis: Any) -> dict[str, Any]:
    return {
        "source": hypothesis.source,
        "category": hypothesis.category,
        "asset": hypothesis.asset,
        "what_changed": hypothesis.what_changed,
        "why_it_might_be_edge": hypothesis.why_it_might_be_edge,
        "expected_persistence_seconds": hypothesis.expected_persistence_seconds,
        "disconfirmation_tests": list(hypothesis.disconfirmation_tests[:5]),
        "actionability": hypothesis.actionability,
        "venue": hypothesis.venue,
        "chain": hypothesis.chain,
        "protocol": hypothesis.protocol,
    }


def _evidence_from_context(context: dict[str, Any]) -> list[str]:
    evidence = [
        f"Report {context['run_id']} contains {context['counts']['signals']} signals "
        f"and {context['counts']['hypotheses']} generated hypotheses.",
    ]
    evidence.extend(str(note) for note in context["notes"])
    for signal in context["signals"]:
        evidence.append(
            f"{signal['asset']} {signal['metric']} observed at {signal['value']} "
            f"from {signal['source']}."
        )
    for summary in context["validation_summaries"]:
        evidence.append(
            f"{summary['strategy_family']} validation for {summary['asset']} "
            f"{summary['timeframe']} was {summary['status']}."
        )
    ai_context = context.get("ai_research_context")
    if isinstance(ai_context, dict):
        evidence.append(
            "AI research context includes "
            f"{len(ai_context.get('paper_evidence_packages', []))} paper evidence packages, "
            f"{len(ai_context.get('source_health_summaries', []))} source health summaries, "
            f"and {len(ai_context.get('registered_validators', []))} registered validators."
        )
    return evidence


def _optional_ai_research_context(
    report: ResearchLoopReport,
    *,
    db_path: str | Path | None,
    memory_path: str | Path | None,
    strategy_family: str | None,
) -> dict[str, Any] | None:
    if db_path is None or memory_path is None:
        return None
    context = build_ai_research_context(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family=strategy_family,
        current_capital_usd=report.current_capital_usd,
    )
    return _rename_prompt_context_keys(context.model_dump(mode="python"))


def _rename_prompt_context_keys(value: Any) -> Any:
    if isinstance(value, dict):
        renamed: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = "execution_enabled" if key == "live_order_routing" else str(key)
            renamed[safe_key] = _rename_prompt_context_keys(item)
        return renamed
    if isinstance(value, list):
        return [_rename_prompt_context_keys(item) for item in value]
    if value == "live_order_routing":
        return "execution_enabled"
    return value


def _is_json_error(exc: ValidationError) -> bool:
    return any(error.get("type") == "json_invalid" for error in exc.errors())
