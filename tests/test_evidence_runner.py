from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.evidence_runner import run_daily_evidence_pipeline


class DeterministicCcxtCollector:
    def __init__(self, *, bar_count: int = 72, funding_hours: tuple[int, ...] = (24, 32, 40, 48, 56)) -> None:
        self.bar_count = bar_count
        self.funding_hours = funding_hours
        self.ohlcv_calls = []
        self.funding_calls = []

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
        self.ohlcv_calls.append((symbol, timeframe, since, limit, params))
        start = datetime(2026, 5, 17, tzinfo=UTC)
        closes = []
        for index in range(self.bar_count):
            close = 100.0 + (index % 6)
            if index in self.funding_hours:
                close = 106.0
            if index - 1 in self.funding_hours:
                close = 100.0
            closes.append(close)
        return [
            MarketCandle(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=index),
                timeframe=timeframe,
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1000.0,
            )
            for index, close in enumerate(closes)
        ]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None, params=None):
        self.funding_calls.append((symbol, since, limit, params))
        start = datetime(2026, 5, 17, tzinfo=UTC)
        return [
            FundingRateRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=hour),
                funding_rate=0.0008,
            )
            for hour in self.funding_hours
        ]


class RaisingOptionalClient:
    def search_pairs(self, query):
        raise RuntimeError("optional source unavailable")

    def yield_pools(self, *, min_tvl_usd):
        raise RuntimeError("optional source unavailable")


def test_evidence_runner_executes_complete_research_milestone(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_out = tmp_path / "daily.md"

    report = run_daily_evidence_pipeline(
        db_path=db_path,
        memory_path=memory_path,
        report_out=report_out,
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id="daily-fixture",
        ccxt_collector=DeterministicCcxtCollector(),
    )

    assert [step.name for step in report.steps] == [
        "ingest_ccxt_ohlcv",
        "ingest_ccxt_funding",
        "research_loop",
        "strategy_validation",
        "validation_memory",
        "paper_simulation",
        "paper_memory",
        "daily_report",
    ]
    assert report.records_written > 0
    assert report.validation_evidence_written > 0
    assert report.paper_outcomes_written > 0
    assert report.memory_records_written > 0
    assert report.research_milestone.loaded_records > 0
    assert report.research_milestone.signal_count > 0
    assert report.research_milestone.anomaly_count > 0
    assert report.research_milestone.hypothesis_count > 0
    assert report.research_milestone.reflection_count > 0
    assert report.research_milestone.accept_reject_reason_count > 0
    assert report.source_health.optional_source_skipped > 0
    assert ("dexscreener", "skipped", "not_configured") in {
        (item.source, item.status, item.reason_code) for item in report.source_health.items
    }
    assert report_out.exists()
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_evidence_runner_blocks_network_sources_without_allow_network(tmp_path):
    collector = DeterministicCcxtCollector()

    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        allow_network=False,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        ccxt_collector=collector,
    )

    assert collector.ohlcv_calls == []
    assert collector.funding_calls == []
    assert report.decision_reason_codes == ["network_not_allowed"]
    assert report.steps[0].status == "blocked"
    assert report.steps[0].reason_code == "network_not_allowed"
    assert report.records_written == 0
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_evidence_runner_writes_blocked_paper_outcome_when_validation_blocks(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    report = run_daily_evidence_pipeline(
        db_path=db_path,
        memory_path=memory_path,
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        run_id="blocked-fixture",
        ccxt_collector=DeterministicCcxtCollector(bar_count=10, funding_hours=(1,)),
    )

    outcomes = PaperOutcomeLedger(db_path).load_outcomes(run_id="blocked-fixture")
    memory_records = MemoryStore(memory_path).list_records()

    assert report.paper_outcomes_written == 1
    assert {outcome.status for outcome in outcomes} == {"blocked"}
    assert outcomes[0].failure_reasons
    assert any(record.rejected_reasons for record in memory_records)


def test_evidence_runner_records_source_health_on_optional_source_failure(tmp_path):
    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        run_id="optional-failure",
        ccxt_collector=DeterministicCcxtCollector(),
        include_dexscreener=True,
        dex_query="BTC",
        dex_client=RaisingOptionalClient(),
        include_defillama=True,
        defillama_client=RaisingOptionalClient(),
    )

    health = {(item.source, item.status, item.reason_code) for item in report.source_health.items}

    assert ("dexscreener", "failure", "optional_source_failed") in health
    assert ("defillama", "failure", "optional_source_failed") in health
    assert report.source_health.optional_source_failures > 0
    assert report.records_written > 0
    assert report.paper_outcomes_written > 0


def test_evidence_runner_replaces_run_scoped_validation_and_research_memory(tmp_path):
    run_id = "rerun-fixture"
    memory_path = tmp_path / "memory.jsonl"

    run_daily_evidence_pipeline(
        db_path=tmp_path / "first.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "first.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        ccxt_collector=DeterministicCcxtCollector(),
    )
    first_ids = _research_and_validation_ids(MemoryStore(memory_path).list_records(), run_id)

    run_daily_evidence_pipeline(
        db_path=tmp_path / "second.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "second.md",
        allow_network=True,
        symbol="ETH/USDT",
        funding_symbol="ETH/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        ccxt_collector=DeterministicCcxtCollector(bar_count=10, funding_hours=(1,)),
    )
    second_ids = _research_and_validation_ids(MemoryStore(memory_path).list_records(), run_id)

    baseline_memory_path = tmp_path / "baseline-memory.jsonl"
    run_daily_evidence_pipeline(
        db_path=tmp_path / "baseline.sqlite",
        memory_path=baseline_memory_path,
        report_out=tmp_path / "baseline.md",
        allow_network=True,
        symbol="ETH/USDT",
        funding_symbol="ETH/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        ccxt_collector=DeterministicCcxtCollector(bar_count=10, funding_hours=(1,)),
    )
    baseline_ids = _research_and_validation_ids(MemoryStore(baseline_memory_path).list_records(), run_id)

    assert first_ids != baseline_ids
    assert second_ids == baseline_ids


def test_evidence_runner_clears_stale_paper_memory_when_rerun_has_no_paper_outcomes(tmp_path):
    run_id = "paper-clear-fixture"
    memory_path = tmp_path / "memory.jsonl"

    first = run_daily_evidence_pipeline(
        db_path=tmp_path / "first.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "first.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        ccxt_collector=DeterministicCcxtCollector(),
    )
    assert first.paper_outcomes_written > 0
    assert _paper_ids(MemoryStore(memory_path).list_records(), run_id)

    second = run_daily_evidence_pipeline(
        db_path=tmp_path / "second.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "second.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        strategy_families=["defi_yield_regime_watchlist"],
        ccxt_collector=DeterministicCcxtCollector(),
    )

    assert second.paper_outcomes_written == 0
    assert _paper_ids(MemoryStore(memory_path).list_records(), run_id) == set()


def test_evidence_run_cli_outputs_safe_json_and_writes_report(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda exchange_id: DeterministicCcxtCollector(),
    )
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_out = tmp_path / "daily.md"

    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--report-out",
            str(report_out),
            "--allow-network",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--limit",
            "200",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["command"] == "evidence-run"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["memory_records_written"] > 0
    assert payload["report_artifact"] == str(report_out)
    assert payload["report"]["source_health"]["optional_source_skipped"] > 0
    assert [step["name"] for step in payload["steps"]] == [
        "ingest_ccxt_ohlcv",
        "ingest_ccxt_funding",
        "research_loop",
        "strategy_validation",
        "validation_memory",
        "paper_simulation",
        "paper_memory",
        "daily_report",
    ]
    assert report_out.exists()


def _research_and_validation_ids(records, run_id):
    return {
        record.record_id
        for record in records
        if run_id in record.tags and ({"research-loop", "validation-evidence"} & set(record.tags))
    }


def _paper_ids(records, run_id):
    return {
        record.record_id
        for record in records
        if "paper-evidence" in record.tags
        and (record.opportunity or {}).get("run_id") == run_id
    }
