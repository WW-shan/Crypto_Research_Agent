from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from crypto_alpha_agent.agents.llm_contracts import HypothesisProposal, ResearchTask
from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport, ValidationSummary


def _report() -> ResearchLoopReport:
    signal = ScannerSignal(
        category="cex",
        source="stored_binance_public",
        asset="BTC",
        metric="funding_rate",
        value=0.012,
        evidence=["BTC funding was elevated for three intervals."],
        venue="binance",
        z_score=3.2,
        persistence_seconds=900.0,
        liquidity_usd=50_000.0,
        capital_required_usd=125.0,
        evidence_count=3,
    )
    return ResearchLoopReport(
        run_id="run-llm-001",
        db_path="research.db",
        source_filter="stored_binance_public",
        record_type_filter="market_candle",
        current_capital_usd=275.0,
        loaded_records=7,
        signal_count=1,
        anomaly_count=0,
        hypothesis_count=0,
        weak_signal_count=0,
        blocked_hypothesis_count=0,
        uses_real_capital=False,
        live_order_routing=False,
        records=[],
        signals=[signal],
        anomalies=[],
        hypotheses=[],
        notes=["weak_signals_absent", "validation_ready"],
        validation_summaries=[
            ValidationSummary(
                strategy_family="funding_momentum",
                asset="BTC",
                timeframe="1h",
                status="passed",
                trade_count=4,
                net_return=0.031,
                max_drawdown=0.008,
                fee_adjusted_expectancy=0.004,
                slippage_adjusted_expectancy=0.003,
            )
        ],
    )


def _proposal_json(**overrides: Any) -> str:
    payload = {
        "proposal_id": "proposal-llm-001",
        "thesis": "Funding dislocations may persist after public exchange updates.",
        "hypothesis": "Elevated BTC public funding fades over the next interval after fees.",
        "assumptions": ["Public funding history remains available for replay."],
        "evidence": ["Stored report showed elevated BTC funding for three intervals."],
        "disconfirmation": ["Reject if the signal disappears after fee adjustment."],
        "data_needed": ["Hourly public funding rates", "Historical mark prices"],
        "capital_required_usd": 125.0,
        "speed_dependency": "low",
        "rpc_dependency": "none",
        "action_mode": "research_only",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _capturing_llm(raw_response: str) -> tuple[Callable[[ResearchTask], str], list[ResearchTask]]:
    captured: list[ResearchTask] = []

    def llm(task: ResearchTask) -> str:
        captured.append(task)
        return raw_response

    return llm, captured


def test_accepts_valid_proposal_and_guard_approval() -> None:
    from crypto_alpha_agent.agents.llm_researcher import run_llm_research_node

    llm, captured = _capturing_llm(_proposal_json())

    result = run_llm_research_node(_report(), llm)

    assert result.accepted is True
    assert isinstance(result.proposal, HypothesisProposal)
    assert result.guard_decision is not None
    assert result.guard_decision.approved is True
    assert result.rejected_reason_codes == []
    assert captured[0].task_id == "llm-research"
    assert captured[0].current_capital_usd == 275.0


def test_invalid_json_returns_rejection_without_raising() -> None:
    from crypto_alpha_agent.agents.llm_researcher import run_llm_research_node

    llm, _ = _capturing_llm("{not json")

    result = run_llm_research_node(_report(), llm)

    assert result.accepted is False
    assert result.proposal is None
    assert result.guard_decision is None
    assert result.rejected_reason_codes == ["invalid_json"]
    assert result.raw_response == "{not json"


@pytest.mark.parametrize(
    "raw_response",
    [
        _proposal_json(unexpected_field="not allowed"),
        _proposal_json(action_mode="paper"),
    ],
)
def test_invalid_proposal_contract_returns_rejection(raw_response: str) -> None:
    from crypto_alpha_agent.agents.llm_researcher import run_llm_research_node

    llm, _ = _capturing_llm(raw_response)

    result = run_llm_research_node(_report(), llm)

    assert result.accepted is False
    assert result.proposal is None
    assert result.guard_decision is None
    assert result.rejected_reason_codes == ["invalid_proposal"]


def test_charter_guard_rejection_returns_guard_reason_codes() -> None:
    from crypto_alpha_agent.agents.llm_researcher import run_llm_research_node

    llm, _ = _capturing_llm(_proposal_json(capital_required_usd=1_000.0))

    result = run_llm_research_node(_report(), llm, max_capital_usd=300.0)

    assert result.accepted is False
    assert result.proposal is not None
    assert result.guard_decision is not None
    assert result.guard_decision.approved is False
    assert result.rejected_reason_codes == ["capital_above_budget"]


def test_research_task_contains_compact_report_context_for_llm() -> None:
    from crypto_alpha_agent.agents.llm_researcher import run_llm_research_node

    llm, captured = _capturing_llm(_proposal_json())

    result = run_llm_research_node(_report(), llm, task_id="custom-task")

    assert result.prompt_context == captured[0].context
    assert captured[0].task_id == "custom-task"
    assert captured[0].network_policy == "offline"
    assert captured[0].context["run_id"] == "run-llm-001"
    assert captured[0].context["current_capital_usd"] == 275.0
    assert captured[0].context["counts"] == {
        "loaded_records": 7,
        "signals": 1,
        "anomalies": 0,
        "hypotheses": 0,
        "weak_signals": 0,
        "blocked_hypotheses": 0,
        "validation_summaries": 1,
    }
    assert captured[0].context["notes"] == ["weak_signals_absent", "validation_ready"]
    assert captured[0].context["signals"][0]["asset"] == "BTC"
    assert captured[0].context["signals"][0]["metric"] == "funding_rate"
    assert captured[0].evidence
