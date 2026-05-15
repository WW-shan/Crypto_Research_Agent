from __future__ import annotations


def _events_and_report(event_path):
    from crypto_alpha_agent.observability.logging import load_events
    from crypto_alpha_agent.observability.reports import generate_daily_report

    replay = load_events(event_path)
    report = generate_daily_report(
        replay.events,
        "2026-05-16",
        skipped_event_lines=replay.skipped_count,
    )
    return replay, report


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


def test_deterministic_research_loop_blocks_infeasible_capital_before_paper_trade(
    tmp_path,
    deterministic_alpha_signal,
):
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.orchestrator import run_deterministic_research_loop

    memory_path = tmp_path / "memory.jsonl"
    event_path = tmp_path / "events.jsonl"

    result = run_deterministic_research_loop(
        signal_fixtures=[deterministic_alpha_signal],
        memory_path=memory_path,
        event_log_path=event_path,
        paper_cash_usd=2_000.0,
        current_capital_usd=100.0,
    )

    assert result["feasibility"]["approved"] is False
    assert "capital_above_budget" in result["feasibility"]["reasons"]
    assert "paper_execute" not in result["trace"]
    assert result["paper_trade"] is None
    assert result["risk_decision"] is None

    persisted = MemoryStore(memory_path).list_records()
    assert len(persisted) == 1
    assert persisted[0].paper_trade_outcome == {
        "status": "blocked",
        "stage": "score_feasibility",
        "reason_codes": ["capital_above_budget"],
    }

    replay, report = _events_and_report(event_path)
    assert replay.skipped_count == 0
    assert report.event_type_counts["opportunity_scored"] == 1
    assert report.event_type_counts["execution_blocked"] == 1
    assert report.action_counts == {"block": 1, "revise": 1}
    assert report.blocks == 2
    assert report.reason_code_counts["capital_above_budget"] == 2


def test_deterministic_research_loop_records_paper_execution_failure_without_success_event(
    tmp_path,
    deterministic_alpha_signal,
):
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.orchestrator import run_deterministic_research_loop

    signal = {
        **deterministic_alpha_signal,
        "capital_required_usd": 500.0,
        "raw": {
            **deterministic_alpha_signal["raw"],
            "expected_net_pnl_usd": 60.0,
            "max_downside_usd": 30.0,
        },
    }
    memory_path = tmp_path / "memory.jsonl"
    event_path = tmp_path / "events.jsonl"

    result = run_deterministic_research_loop(
        signal_fixtures=[signal],
        memory_path=memory_path,
        event_log_path=event_path,
        paper_cash_usd=500.0,
    )

    assert result["feasibility"]["approved"] is True
    assert result["risk_decision"]["execution_allowed"] is True
    assert result["paper_trade"] is None

    persisted = MemoryStore(memory_path).list_records()
    assert len(persisted) == 1
    assert persisted[0].paper_trade_outcome["status"] == "failed"
    assert persisted[0].paper_trade_outcome["stage"] == "paper_execute"
    assert persisted[0].paper_trade_outcome["reason_codes"] == ["insufficient_paper_cash"]
    assert "insufficient paper cash" in persisted[0].paper_trade_outcome["error"]

    replay, report = _events_and_report(event_path)
    assert replay.skipped_count == 0
    assert report.event_type_counts["risk_guard"] == 1
    assert report.event_type_counts["paper_execution_failed"] == 1
    assert report.action_counts.get("paper_trade") is None
    assert report.action_counts["risk_approved"] == 1
    assert report.action_counts["block"] == 1
    assert report.reason_code_counts["insufficient_paper_cash"] == 1


def test_deterministic_research_loop_persists_stable_memory_timestamps(
    tmp_path,
    deterministic_alpha_signal,
):
    from crypto_alpha_agent.memory.store import MemoryStore
    from crypto_alpha_agent.orchestrator import run_deterministic_research_loop

    memory_path = tmp_path / "memory.jsonl"

    first = run_deterministic_research_loop(
        signal_fixtures=[deterministic_alpha_signal],
        memory_path=memory_path,
        paper_cash_usd=2_000.0,
    )
    first_content = memory_path.read_text()
    first_record = MemoryStore(memory_path).get(first["memory_record_id"])

    second = run_deterministic_research_loop(
        signal_fixtures=[deterministic_alpha_signal],
        memory_path=memory_path,
        paper_cash_usd=2_000.0,
    )
    second_content = memory_path.read_text()
    second_record = MemoryStore(memory_path).get(second["memory_record_id"])

    assert first_content == second_content
    assert first_record.created_at == "2026-05-16T12:00:00+00:00"
    assert first_record.updated_at == "2026-05-16T12:00:00+00:00"
    assert second_record.created_at == first_record.created_at
    assert second_record.updated_at == first_record.updated_at
