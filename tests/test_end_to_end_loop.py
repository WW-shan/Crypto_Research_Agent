from __future__ import annotations


def test_deterministic_research_loop_persists_memory_and_paper_trade(
    tmp_path,
    deterministic_alpha_signal,
):
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.orchestrator import run_deterministic_research_loop

    memory_path = tmp_path / "memory.jsonl"

    result = run_deterministic_research_loop(
        signal_fixtures=[deterministic_alpha_signal],
        memory_path=memory_path,
        paper_cash_usd=2_000.0,
    )

    assert result["trace"] == [
        "scan_market",
        "detect_anomaly",
        "generate_hypothesis",
        "score_feasibility",
        "code_strategy",
        "backtest",
        "critique",
        "update_memory",
        "risk_guard",
        "paper_execute",
    ]
    assert result["signals"][0]["source"] == "synthetic-fixture"
    assert result["anomalies"][0]["classification"] == "structural_discontinuity"
    assert result["hypothesis"]["actionability"] == "executable"
    assert result["feasibility"]["approved"] is True
    assert result["strategy"]["kind"] == "execution_proposal"
    assert result["backtest"]["trade_count"] >= 3
    assert result["critique"]["outcome"] == "accept"

    risk_decision = result["risk_decision"]
    assert risk_decision["execution_mode"] == "paper"
    assert risk_decision["execution_allowed"] is True
    assert risk_decision["reason_codes"] == []

    paper_trade = result["paper_trade"]
    assert paper_trade["buy"]["touched_real_capital"] is False
    assert paper_trade["sell"]["touched_real_capital"] is False
    assert paper_trade["sell"]["realized_net_pnl"] > 0

    persisted = MemoryStore(memory_path).list_records()
    assert len(persisted) == 1
    record = persisted[0]
    assert record.record_id == result["memory_record_id"]
    assert record.opportunity["asset"] == "ETH-USD"
    assert record.hypothesis["actionability"] == "executable"
    assert record.score["approved"] is True
    assert record.backtest_artifacts["metrics"]["trade_count"] == result["backtest"]["trade_count"]
    assert record.paper_trade_outcome["status"] == "closed"
    assert record.paper_trade_outcome["risk_decision"]["execution_allowed"] is True
    assert record.paper_trade_outcome["sell"]["realized_net_pnl"] > 0
