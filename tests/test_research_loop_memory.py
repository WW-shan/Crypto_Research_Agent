import copy
import json

from crypto_alpha_agent.agents.anomaly import AnomalyDetector
from crypto_alpha_agent.agents.hypothesis import HypothesisGenerator
from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.memory import persist_research_loop_memory
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport, ValidationSummary


def _signal(
    *,
    asset: str,
    metric: str,
    z_score: float | None = None,
    liquidity_usd: float = 10_000.0,
    capital_required_usd: float = 250.0,
    speed_dependency: str = "low",
    rpc_dependency: str = "low",
) -> ScannerSignal:
    return ScannerSignal(
        category="cex",
        source="ccxt",
        asset=asset,
        metric=metric,
        value=1.25,
        evidence=["funding dislocated", "spot depth stable"],
        raw={"timeframe": "1h"},
        venue="binance",
        z_score=z_score,
        persistence_seconds=600.0,
        liquidity_usd=liquidity_usd,
        capital_required_usd=capital_required_usd,
        speed_dependency=speed_dependency,
        rpc_dependency=rpc_dependency,
        evidence_count=2,
    )


def _report() -> ResearchLoopReport:
    executable_signal = _signal(asset="BTC/USDT", metric="funding_rate", z_score=3.2)
    blocked_signal = _signal(
        asset="ETH/USDT",
        metric="spread",
        liquidity_usd=100.0,
        capital_required_usd=2_500.0,
        speed_dependency="high",
        rpc_dependency="high",
    )
    anomalies = AnomalyDetector().rank([executable_signal, blocked_signal])
    hypotheses = HypothesisGenerator().generate(anomalies)

    return ResearchLoopReport(
        run_id="memory-run-001",
        db_path="/tmp/research.sqlite",
        source_filter="ccxt",
        record_type_filter="market_candle",
        current_capital_usd=500.0,
        loaded_records=2,
        signal_count=2,
        anomaly_count=2,
        hypothesis_count=2,
        weak_signal_count=0,
        blocked_hypothesis_count=1,
        uses_real_capital=False,
        live_order_routing=False,
        records=[],
        signals=[executable_signal, blocked_signal],
        anomalies=anomalies,
        hypotheses=hypotheses,
        notes=["test-report"],
        validation_summaries=[
            ValidationSummary(
                strategy_family="momentum",
                asset="BTC/USDT",
                timeframe="1h",
                status="passed",
                trade_count=3,
                net_return=0.04,
                max_drawdown=-0.01,
                fee_adjusted_expectancy=0.02,
                slippage_adjusted_expectancy=0.018,
                blocked_reasons=[],
            ),
            ValidationSummary(
                strategy_family="momentum",
                asset="ETH/USDT",
                timeframe="1h",
                status="blocked",
                trade_count=1,
                blocked_reasons=["insufficient_trades"],
            ),
        ],
    )


def test_persist_research_loop_memory_records_accepted_and_blocked_hypotheses(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    records = persist_research_loop_memory(_report(), memory_path)

    assert len(records) == 2
    accepted = next(record for record in records if "accepted" in record.tags)
    blocked = next(record for record in records if "blocked" in record.tags)

    assert accepted.record_id.startswith(
        "research-loop:memory-run-001:0:btc-usdt:cex:funding-rate:"
    )
    assert accepted.rejected_reasons == []
    assert {"research-loop", "memory-run-001", "btc-usdt", "cex", "executable", "accepted"} <= set(
        accepted.tags
    )
    assert accepted.opportunity["asset"] == "BTC/USDT"
    assert accepted.opportunity["current_capital_usd"] == 500.0
    assert accepted.opportunity["actionability"] == "executable"
    assert accepted.hypothesis["action_mode"] == "research_only"
    assert accepted.score["validation_summaries"][0]["status"] == "passed"

    assert blocked.record_id.startswith("research-loop:memory-run-001:1:eth-usdt:cex:spread:")
    assert "hypothesis_blocked" in blocked.rejected_reasons
    assert "insufficient_trades" in blocked.rejected_reasons
    assert "execution constraints exceed visible liquidity/timing" in blocked.rejected_reasons
    assert {"research-loop", "memory-run-001", "eth-usdt", "cex", "blocked"} <= set(blocked.tags)
    assert blocked.opportunity["actionability"] == "blocked"


def test_persisted_research_loop_memory_survives_reopen_with_stable_fields(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    stored = persist_research_loop_memory(_report(), memory_path)
    reopened = MemoryStore(memory_path)
    loaded = reopened.list_records()

    assert [record.record_id for record in loaded] == [record.record_id for record in stored]
    assert all(record.embedding for record in loaded)
    assert loaded[0].created_at == stored[0].created_at
    assert loaded[0].updated_at == stored[0].updated_at
    assert loaded[0].opportunity["run_id"] == "memory-run-001"
    assert loaded[0].hypothesis["evidence"][0]["metric"] == "funding_rate"
    assert loaded[0].score["report_counts"] == {
        "loaded_records": 2,
        "signal_count": 2,
        "anomaly_count": 2,
        "hypothesis_count": 2,
        "weak_signal_count": 0,
        "blocked_hypothesis_count": 1,
    }


def test_persist_research_loop_memory_is_idempotent_by_record_id(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    report = _report()

    first = persist_research_loop_memory(report, memory_path)
    second = persist_research_loop_memory(report, memory_path)
    reopened = MemoryStore(memory_path)

    assert [record.record_id for record in second] == [record.record_id for record in first]
    reopened_record_ids = [record.record_id for record in reopened.list_records()]
    assert reopened_record_ids == [record.record_id for record in first]
    assert reopened_record_ids[0].startswith(
        "research-loop:memory-run-001:0:btc-usdt:cex:funding-rate:"
    )
    assert reopened_record_ids[1].startswith("research-loop:memory-run-001:1:eth-usdt:cex:spread:")


def test_persist_research_loop_memory_distinguishes_same_rank_hypotheses_by_evidence_identity(
    tmp_path,
):
    memory_path = tmp_path / "memory.jsonl"
    first_report = _report()
    second_report = copy.deepcopy(first_report)
    second_hypothesis = second_report.hypotheses[0]
    second_hypothesis.evidence[0].source = "coinbase"
    second_hypothesis.evidence[0].value = 1.75
    second_hypothesis.evidence[0].raw = {
        "timeframe": "1h",
        "provider_event_id": "distinct-provider-event",
    }

    first_records = persist_research_loop_memory(first_report, memory_path)
    repeated_records = persist_research_loop_memory(first_report, memory_path)
    second_records = persist_research_loop_memory(second_report, memory_path)
    stored_records = MemoryStore(memory_path).list_records()

    assert [record.record_id for record in repeated_records] == [
        record.record_id for record in first_records
    ]
    assert first_records[0].record_id.startswith(
        "research-loop:memory-run-001:0:btc-usdt:cex:funding-rate:"
    )
    assert second_records[0].record_id.startswith(
        "research-loop:memory-run-001:0:btc-usdt:cex:funding-rate:"
    )
    assert second_records[0].record_id != first_records[0].record_id
    assert len(stored_records) == 3
    assert len({record.record_id for record in stored_records}) == 3


def test_persist_research_loop_memory_omits_large_raw_payloads_from_hypothesis(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    report = _report()
    huge_marker = "RAW_PAYLOAD_MARKER_SHOULD_NOT_BE_PERSISTED"
    report.hypotheses[0].evidence[0].raw = {
        "timeframe": "1h",
        "nested": {"blob": huge_marker * 200},
    }

    records = persist_research_loop_memory(report, memory_path)
    stored_json = json.dumps(records[0].hypothesis, sort_keys=True)

    assert huge_marker not in stored_json
    evidence = records[0].hypothesis["evidence"][0]
    assert "raw" not in evidence
    assert evidence["raw_omitted"] is True
    assert evidence["raw_keys"] == ["nested", "timeframe"]
    assert len(evidence["raw_sha256"]) == 64


def test_persist_research_loop_memory_empty_report_returns_empty_without_file(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    report = ResearchLoopReport(
        run_id="empty-run",
        db_path="/tmp/research.sqlite",
        source_filter=None,
        record_type_filter=None,
        current_capital_usd=500.0,
        loaded_records=0,
        signal_count=0,
        anomaly_count=0,
        hypothesis_count=0,
        weak_signal_count=0,
        blocked_hypothesis_count=0,
        uses_real_capital=False,
        live_order_routing=False,
        records=[],
        signals=[],
        anomalies=[],
        hypotheses=[],
        notes=["no_stored_records"],
        validation_summaries=[],
    )

    records = persist_research_loop_memory(report, memory_path)

    assert records == []
    assert MemoryStore(memory_path).list_records() == []
    assert not memory_path.exists()
