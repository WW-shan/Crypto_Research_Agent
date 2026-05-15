from __future__ import annotations


def test_deterministic_research_loop_persists_memory_and_paper_trade(
    tmp_path,
    deterministic_alpha_signal,
):
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.observability.logging import load_events
    from crypto_alpha_agent.observability.reports import generate_daily_report
    from crypto_alpha_agent.orchestrator import run_deterministic_research_loop

    memory_path = tmp_path / "memory.jsonl"
    event_path = tmp_path / "events.jsonl"

    result = run_deterministic_research_loop(
        signal_fixtures=[deterministic_alpha_signal],
        memory_path=memory_path,
        event_log_path=event_path,
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
    assert record.backtest_artifacts["engine"] == "vectorbt"
    assert record.backtest_artifacts["metrics"]["trade_count"] == result["backtest"]["trade_count"]
    assert record.paper_trade_outcome["status"] == "closed"
    assert record.paper_trade_outcome["risk_decision"]["execution_allowed"] is True
    assert record.paper_trade_outcome["sell"]["realized_net_pnl"] > 0

    replay = load_events(event_path)
    report = generate_daily_report(
        replay.events,
        "2026-05-16",
        skipped_event_lines=replay.skipped_count,
    )

    assert replay.skipped_count == 0
    assert report.total_events >= 3
    assert report.event_type_counts["opportunity_scored"] == 1
    assert report.event_type_counts["backtest_completed"] == 1
    assert report.event_type_counts["risk_guard"] == 1
    assert report.approvals >= 1
    assert report.action_counts["paper_trade"] == 1
    assert report.metrics["expected_net_pnl_usd"].sum == 60.0
    assert report.metrics["backtest_trade_count"].sum == result["backtest"]["trade_count"]
    assert report.events[0].run_id == result["run_id"]
