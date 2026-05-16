from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from crypto_alpha_agent.agents.llm_contracts import ResearchTask
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
        run_id="run-llm-graph-001",
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
        "proposal_id": "proposal-llm-graph-001",
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


def _llm(raw_response: str) -> Callable[[ResearchTask], str]:
    def fake_llm(_task: ResearchTask) -> str:
        return raw_response

    return fake_llm


def test_llm_graph_routes_accepted_paper_action_through_validation_critique_memory_and_human_checkpoint(
    tmp_path,
) -> None:
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.orchestrator import (
        DETERMINISTIC_EVENT_TIME_ISO,
        build_llm_research_graph,
    )

    memory_path = tmp_path / "llm-memory.jsonl"
    graph = build_llm_research_graph(_llm(_proposal_json()))

    state = graph.invoke(
        {
            "research_report": _report(),
            "memory_path": memory_path,
            "suggest_paper_action": True,
        }
    )

    assert state["trace"] == [
        "llm_research",
        "create_validation_request",
        "llm_critique",
        "update_llm_memory",
        "llm_human_checkpoint",
    ]
    assert state["llm_research_result"]["accepted"] is True
    assert state["llm_proposal"]["proposal_id"] == "proposal-llm-graph-001"
    assert state["guard_decision"]["approved"] is True
    assert state["validation_request"] == {
        "request_id": "validation:proposal-llm-graph-001",
        "proposal_id": "proposal-llm-graph-001",
        "validation_type": "historical_validation",
        "dataset": "run-llm-graph-001",
        "source": "stored_report",
        "metrics": ["net_return", "max_drawdown", "hit_rate"],
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
        "start_time": None,
        "end_time": None,
    }
    assert state["critique_result"]["accepted"] is False
    assert state["critique_result"]["next_action"] == "human_review"
    assert "human approval" in " ".join(state["critique_result"]["reasons"])
    assert state["memory_updated"] is True
    assert state["approval_required"] is True
    assert state["paused_at"] == "llm_human_checkpoint"
    assert state["human_checkpoint_reason"] == "paper_action_requires_human_approval"

    persisted = MemoryStore(memory_path).get("llm:proposal-llm-graph-001")
    assert persisted is not None
    assert persisted.created_at == DETERMINISTIC_EVENT_TIME_ISO
    assert persisted.updated_at == DETERMINISTIC_EVENT_TIME_ISO
    assert persisted.hypothesis["proposal"]["proposal_id"] == "proposal-llm-graph-001"
    assert persisted.score["guard_decision"]["approved"] is True
    assert persisted.score["validation_request"]["request_id"] == "validation:proposal-llm-graph-001"
    assert persisted.score["critique_result"]["next_action"] == "human_review"


def test_llm_graph_routes_guard_rejection_to_memory_without_validation_or_checkpoint(
    tmp_path,
) -> None:
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.orchestrator import build_llm_research_graph

    memory_path = tmp_path / "llm-memory.jsonl"
    graph = build_llm_research_graph(
        _llm(_proposal_json(capital_required_usd=1_000.0)),
        max_capital_usd=300.0,
    )

    state = graph.invoke(
        {
            "research_report": _report(),
            "memory_path": memory_path,
            "suggest_paper_action": True,
        }
    )

    assert state["trace"] == ["llm_research", "update_llm_memory"]
    assert state["llm_research_result"]["accepted"] is False
    assert state["guard_decision"]["approved"] is False
    assert state["llm_research_result"]["rejected_reason_codes"] == ["capital_above_budget"]
    assert "validation_request" not in state
    assert "critique_result" not in state
    assert "approval_required" not in state
    assert "paused_at" not in state
    assert state["memory_updated"] is True

    persisted = MemoryStore(memory_path).get("llm:proposal-llm-graph-001")
    assert persisted is not None
    assert persisted.rejected_reasons == ["capital_above_budget"]
    assert persisted.score["guard_decision"]["reason_codes"] == ["capital_above_budget"]
    assert "validation_request" not in persisted.score


def test_existing_build_graph_behavior_remains_unchanged() -> None:
    from crypto_alpha_agent.orchestrator import build_graph

    graph = build_graph()
    state = graph.invoke({"mode": "research", "require_human_approval": True})

    assert state["trace"][-1] == "human_checkpoint"
    assert state["approval_required"] is True
    assert "proposal_finalized" not in state
