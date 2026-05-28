from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, OpenInterestRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.evidence_runner import run_daily_evidence_pipeline


class DeterministicCcxtCollector:
    def __init__(self, *, bar_count: int = 72, funding_hours: tuple[int, ...] = (24, 32, 40, 48, 56)) -> None:
        self.bar_count = bar_count
        self.funding_hours = funding_hours
        self.ohlcv_calls = []
        self.funding_calls = []
        self.open_interest_calls = []

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

    def fetch_open_interest_history(self, symbol, timeframe, since=None, limit=None, params=None):
        self.open_interest_calls.append((symbol, timeframe, since, limit, params))
        start = datetime(2026, 5, 17, tzinfo=UTC)
        return [
            OpenInterestRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=hour),
                timeframe=timeframe,
                open_interest=1000.0 + (100.0 * index),
                open_interest_value=100000.0 + (10000.0 * index),
            )
            for index, hour in enumerate(self.funding_hours)
        ]


class RaisingOptionalClient:
    def search_pairs(self, query):
        raise RuntimeError("optional source unavailable")

    def yield_pools(self, *, min_tvl_usd):
        raise RuntimeError("optional source unavailable")


class OpenInterestFailingCollector(DeterministicCcxtCollector):
    def fetch_open_interest_history(self, symbol, timeframe, since=None, limit=None, params=None):
        self.open_interest_calls.append((symbol, timeframe, since, limit, params))
        raise NotImplementedError("open interest unavailable")


def test_evidence_run_lock_blocks_second_holder_and_removes_file(tmp_path):
    from crypto_alpha_agent.pipeline.evidence_run_ops import (
        EvidenceRunLock,
        EvidenceRunLockError,
    )

    lock_path = tmp_path / "locks" / "evidence-run.lock"
    with EvidenceRunLock(lock_path, run_id="run-a"):
        assert lock_path.exists()
        try:
            with EvidenceRunLock(lock_path, run_id="run-b"):
                raise AssertionError("second lock should not be acquired")
        except EvidenceRunLockError as exc:
            assert exc.reason_code == "evidence_run_lock_held"
    assert not lock_path.exists()


def test_write_json_artifact_replaces_atomically_and_updates_latest(tmp_path):
    from crypto_alpha_agent.pipeline.evidence_run_ops import write_json_artifact

    target = tmp_path / "manifests" / "run.json"
    latest = tmp_path / "manifests" / "latest.json"
    write_json_artifact(target, {"status": "success", "run_id": "run-a"}, latest_path=latest)
    write_json_artifact(target, {"status": "failed", "run_id": "run-a"}, latest_path=latest)

    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "failed"
    assert json.loads(latest.read_text(encoding="utf-8"))["status"] == "failed"


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


def test_evidence_runner_ingests_open_interest_for_oi_strategy_family(tmp_path):
    collector = DeterministicCcxtCollector()

    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id="oi-strategy-fixture",
        strategy_families=["funding_open_interest_crowding"],
        ccxt_collector=collector,
    )

    assert collector.open_interest_calls == [("BTC/USDT:USDT", "1h", None, 200, None)]
    assert [step.name for step in report.steps][:3] == [
        "ingest_ccxt_ohlcv",
        "ingest_ccxt_funding",
        "ingest_ccxt_open_interest",
    ]
    assert any(
        item.source == "ccxt"
        and item.feed == "open_interest_history"
        and item.status == "success"
        and item.records_written > 0
        for item in report.source_health.items
    )
    assert report.records_written > collector.bar_count + len(collector.funding_hours)
    assert report.validation_evidence_written > 0


def test_evidence_runner_isolates_open_interest_ingestion_failure_to_oi_families(tmp_path):
    collector = OpenInterestFailingCollector()

    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id="oi-failure-fixture",
        strategy_families=[
            "funding_extremity_price_confirmation",
            "funding_open_interest_crowding",
        ],
        ccxt_collector=collector,
    )

    assert collector.open_interest_calls == [("BTC/USDT:USDT", "1h", None, 200, None)]
    assert ("open_interest_source_failed" in report.decision_reason_codes)
    assert any(
        step.name == "ingest_ccxt_open_interest"
        and step.status == "failed"
        and step.reason_code == "open_interest_source_failed"
        for step in report.steps
    )
    assert any(
        item.source == "ccxt"
        and item.feed == "open_interest_history"
        and item.status == "failure"
        and item.reason_code == "open_interest_source_failed"
        for item in report.source_health.items
    )
    assert report.paper_outcomes_written > 0
    assert report.validation_evidence_written > 0


def test_evidence_runner_blocks_oi_family_after_open_interest_ingestion_failure_even_with_cached_oi(tmp_path):
    db_path = tmp_path / "research.sqlite"
    cached_open_interest = DeterministicCcxtCollector().fetch_open_interest_history(
        "BTC/USDT:USDT",
        "1h",
        limit=200,
    )
    ResearchDataStore(db_path).upsert_records(
        [item.to_source_record() for item in cached_open_interest]
    )

    report = run_daily_evidence_pipeline(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id="oi-cached-failure-fixture",
        strategy_families=["funding_open_interest_crowding"],
        ccxt_collector=OpenInterestFailingCollector(),
    )

    evidence = ValidationEvidenceLedger(db_path).load_evidence(
        run_id="oi-cached-failure-fixture"
    )

    assert "open_interest_source_failed" in report.decision_reason_codes
    assert report.paper_outcomes_written == 0
    assert len(evidence) == 1
    assert evidence[0].strategy_family == "funding_open_interest_crowding"
    assert evidence[0].approved is False
    assert evidence[0].blocked_reasons == ("open_interest_source_failed",)


def test_evidence_runner_clears_stale_oi_paper_outcomes_after_open_interest_failure(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    run_id = "oi-rerun-failure-fixture"

    first = run_daily_evidence_pipeline(
        db_path=db_path,
        memory_path=memory_path,
        report_out=tmp_path / "first.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        strategy_families=["funding_open_interest_crowding"],
        ccxt_collector=DeterministicCcxtCollector(),
    )
    assert first.paper_outcomes_written > 0
    assert PaperOutcomeLedger(db_path).load_outcomes(run_id=run_id)

    second = run_daily_evidence_pipeline(
        db_path=db_path,
        memory_path=memory_path,
        report_out=tmp_path / "second.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        limit=200,
        run_id=run_id,
        strategy_families=["funding_open_interest_crowding"],
        ccxt_collector=OpenInterestFailingCollector(),
    )

    assert "open_interest_source_failed" in second.decision_reason_codes
    assert second.paper_outcomes_written == 0
    assert PaperOutcomeLedger(db_path).load_outcomes(run_id=run_id) == []


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


class SecretUrlFailingGraphClient:
    def query(self, subgraph_url, query, *, variables=None):
        raise RuntimeError(
            f"failed request to {subgraph_url} {query} {variables} "
            "https://signed.example/path?token=abc"
        )


def test_evidence_runner_records_network_route_and_redacts_core_failure(
    tmp_path,
    monkeypatch,
):
    class FailingCoreCollector:
        def fetch_ohlcv(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("failed via https://secret.example/path")

    monkeypatch.setenv("CRYPTO_ALPHA_AGENT_PROXY", "http://127.0.0.1:" + "10808")
    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "research.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        ccxt_collector=FailingCoreCollector(),
    )

    assert report.source_health.items[0].network_route == "proxy"
    assert report.source_health.items[0].failure == "failed via [REDACTED_URL]"


def test_evidence_runner_can_write_research_report_to_distinct_path(tmp_path):
    research_out = tmp_path / "daily.research.md"
    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=research_out,
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        run_id="distinct-report",
        ccxt_collector=DeterministicCcxtCollector(),
    )

    assert report.report_artifact == str(research_out)
    assert research_out.exists()
    assert "# Crypto Alpha Research Loop" in research_out.read_text(encoding="utf-8")


def test_evidence_runner_redacts_thegraph_failure_urls(tmp_path):
    secret_url = "https://gateway.thegraph.com/api/SECRET_KEY/subgraphs/id/abc"
    graph_query = "{ pools(secret: \"GRAPH_QUERY_SECRET\") { id } }"
    graph_variables = {"owner": "GRAPH_VARIABLE_SECRET"}

    report = run_daily_evidence_pipeline(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        run_id="thegraph-failure",
        ccxt_collector=DeterministicCcxtCollector(),
        include_thegraph=True,
        subgraph_url=secret_url,
        graph_query=graph_query,
        graph_variables=graph_variables,
        thegraph_client=SecretUrlFailingGraphClient(),
    )

    payload = report.model_dump(mode="json")
    payload_json = json.dumps(payload, sort_keys=True)
    assert "SECRET_KEY" not in payload_json
    assert "GRAPH_QUERY_SECRET" not in payload_json
    assert "GRAPH_VARIABLE_SECRET" not in payload_json
    assert secret_url not in payload_json
    assert graph_query not in payload_json
    graph_failures = [
        item
        for item in report.source_health.items
        if item.source == "thegraph" and item.status == "failure"
    ]
    assert graph_failures
    assert "[REDACTED_URL]" in graph_failures[0].failure
    assert "<redacted>" in graph_failures[0].failure


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
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_interpretation"]["schema_name"] == "EvidenceRunInterpretation"
    assert payload["llm_interpretation"]["evidence_refs"][0].startswith("evidence-run:")
    assert payload["memory_records_written"] > 0
    research_report_out = tmp_path / "daily.research.md"
    assert payload["status"] == "success"
    assert payload["exit_code"] == 0
    assert payload["report_artifact"] == str(research_report_out)
    assert payload["research_report_out"] == str(research_report_out)
    assert payload["daily_report_out"] == str(report_out)
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
    assert research_report_out.exists()
    assert "# Daily Evidence Report" in report_out.read_text(encoding="utf-8")
    assert "# Crypto Alpha Research Loop" in research_report_out.read_text(encoding="utf-8")
    assert Path(payload["json_out"]).exists()
    assert Path(payload["manifest_out"]).exists()
    assert Path(payload["latest_report_out"]).exists()
    assert Path(payload["latest_json_out"]).exists()
    assert Path(payload["latest_manifest_out"]).exists()
    manifest = json.loads(Path(payload["manifest_out"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["llm_interpretation"]["schema_name"] == "EvidenceRunInterpretation"
    assert manifest["llm_provider"] == "real"
    assert manifest["used_fake_llm"] is False
    assert manifest["artifacts"]["daily_report"] == str(report_out)
    assert manifest["artifacts"]["research_report"] == str(research_report_out)
    assert manifest["artifact_status"]["daily_report"]["exists"] is True
    assert manifest["artifact_status"]["research_report"]["exists"] is True
    assert manifest["artifact_status"]["json_payload"]["exists"] is True
    assert manifest["artifact_status"]["manifest"]["exists"] is True
    assert manifest["artifact_status"]["lock"]["exists"] is False


def test_evidence_run_cli_fails_closed_when_llm_interpretation_fails(
    tmp_path,
    capsys,
    monkeypatch,
):
    from crypto_alpha_agent.llm.runtime import LLMHealthCheckResult, LLMRuntimeError

    class FailingInterpretationRuntime:
        def llm(self, _task):
            return "{}"

        def health_check(self, *, command: str):
            return LLMHealthCheckResult(
                status="ok",
                schema_name="LLMHealthCheckResult",
                capabilities=["json_schema", "research_only"],
                uses_real_capital=False,
                live_order_routing=False,
            )

        def structured_call(self, _task, _output_model):
            raise LLMRuntimeError(
                "schema_validation_failed",
                "LLM evidence-run interpretation failed schema validation.",
            )

        def metadata(self) -> dict[str, object]:
            return {
                "llm_provider": "real",
                "used_fake_llm": False,
                "llm_role": "research",
                "llm_provider_verified": True,
                "llm_model": "test-real-model",
            }

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": FailingInterpretationRuntime(),
    )
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda exchange_id: DeterministicCcxtCollector(),
    )
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_out = tmp_path / "daily.md"
    json_out = tmp_path / "payload.json"
    manifest_out = tmp_path / "manifest.json"
    failed_marker_out = tmp_path / "failed.json"

    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--report-out",
            str(report_out),
            "--json-out",
            str(json_out),
            "--manifest-out",
            str(manifest_out),
            "--failed-marker-out",
            str(failed_marker_out),
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

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["reason_code"] == "schema_validation_failed"
    assert "llm_interpretation" not in payload
    assert not report_out.exists()
    assert json_out.exists()
    assert manifest_out.exists()
    assert failed_marker_out.exists()
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "failed"
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    marker = json.loads(failed_marker_out.read_text(encoding="utf-8"))
    assert manifest["reason_code"] == "schema_validation_failed"
    assert marker["reason_code"] == "schema_validation_failed"


def test_evidence_run_cli_lock_contention_writes_failed_marker(tmp_path, capsys):
    from crypto_alpha_agent.pipeline.evidence_run_ops import EvidenceRunLock

    lock_path = tmp_path / "locks" / "evidence-run.lock"
    failed_marker_out = tmp_path / "failed" / "locked.json"
    json_out = tmp_path / "payload.json"
    manifest_out = tmp_path / "manifest.json"

    with EvidenceRunLock(lock_path, run_id="active-run"):
        exit_code = main(
            [
                "evidence-run",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--memory",
                str(tmp_path / "memory.jsonl"),
                "--report-out",
                str(tmp_path / "daily.md"),
                "--json-out",
                str(json_out),
                "--manifest-out",
                str(manifest_out),
                "--failed-marker-out",
                str(failed_marker_out),
                "--lock-path",
                str(lock_path),
                "--run-id",
                "locked-run",
                "--symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
                "--timeframe",
                "1h",
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert lock_path.exists()

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["reason_code"] == "evidence_run_lock_held"
    assert failed_marker_out.exists()
    assert json.loads(json_out.read_text(encoding="utf-8"))["status"] == "failed"
    marker = json.loads(failed_marker_out.read_text(encoding="utf-8"))
    assert marker["reason_code"] == "evidence_run_lock_held"
    assert marker["artifact_status"]["lock"]["exists"] is True
    assert not lock_path.exists()


def test_evidence_run_cli_default_lock_uses_db_root_across_report_dirs(tmp_path, capsys):
    from crypto_alpha_agent.pipeline.evidence_run_ops import EvidenceRunLock

    db_path = tmp_path / "state" / "research.sqlite"
    lock_path = db_path.parent / "locks" / "evidence-run.lock"

    with EvidenceRunLock(lock_path, run_id="active-run"):
        exit_code = main(
            [
                "evidence-run",
                "--db",
                str(db_path),
                "--memory",
                str(tmp_path / "state" / "memory.jsonl"),
                "--report-out",
                str(tmp_path / "reports" / "different-dir" / "daily.md"),
                "--run-id",
                "default-lock-run",
                "--symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
                "--timeframe",
                "1h",
            ]
        )
        payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["reason_code"] == "evidence_run_lock_held"
    assert payload["lock_path"] == str(lock_path)


def test_evidence_run_cli_failed_marker_redacts_configured_secret(
    tmp_path,
    capsys,
    monkeypatch,
):
    secret = "dune-secret-token"

    def fail_pipeline(**_kwargs):
        raise RuntimeError(f"failed with {secret}")

    monkeypatch.setattr("crypto_alpha_agent.cli.run_daily_evidence_pipeline", fail_pipeline)

    failed_marker_out = tmp_path / "failed.json"
    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "daily.md"),
            "--failed-marker-out",
            str(failed_marker_out),
            "--include-dune",
            "--dune-query-id",
            "123456",
            "--dune-api-key",
            secret,
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    marker_text = failed_marker_out.read_text(encoding="utf-8")

    assert exit_code == 2
    assert payload["reason_code"] == "evidence_run_failed"
    assert payload["failure"] == "failed with <redacted>"
    assert secret not in stdout
    assert secret not in marker_text
    assert payload["manifest"]["inputs"]["dune_api_key_configured"] is True


def test_evidence_run_cli_redacts_param_variable_and_query_values_from_artifacts(
    tmp_path,
    capsys,
    monkeypatch,
):
    dune_value = "dune-param-secret"
    graph_value = "graph-variable-secret"
    graph_query = "{ token(secret: \"graph-query-secret\") { id } }"

    def fail_pipeline(**_kwargs):
        raise RuntimeError(
            f"failed with {dune_value} {graph_value} {graph_query} "
            "https://signed.example/path?token=abc"
        )

    monkeypatch.setattr("crypto_alpha_agent.cli.run_daily_evidence_pipeline", fail_pipeline)

    json_out = tmp_path / "payload.json"
    manifest_out = tmp_path / "manifest.json"
    failed_marker_out = tmp_path / "failed.json"
    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "daily.md"),
            "--json-out",
            str(json_out),
            "--manifest-out",
            str(manifest_out),
            "--failed-marker-out",
            str(failed_marker_out),
            "--include-dune",
            "--dune-query-id",
            "123456",
            "--dune-param",
            f"alpha={dune_value}",
            "--include-thegraph",
            "--subgraph-url",
            "https://example.test/subgraph",
            "--graph-query",
            graph_query,
            "--graph-variable",
            f"owner={graph_value}",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    artifact_text = "\n".join(
        [
            stdout,
            json_out.read_text(encoding="utf-8"),
            manifest_out.read_text(encoding="utf-8"),
            failed_marker_out.read_text(encoding="utf-8"),
        ]
    )
    manifest_inputs = payload["manifest"]["inputs"]

    assert exit_code == 2
    assert payload["failure"] == (
        "failed with <redacted> <redacted> <redacted> [REDACTED_URL]"
    )
    assert dune_value not in artifact_text
    assert graph_value not in artifact_text
    assert graph_query not in artifact_text
    assert "dune_params" not in manifest_inputs
    assert "graph_variables" not in manifest_inputs
    assert "graph_query" not in manifest_inputs
    assert manifest_inputs["dune_param_keys"] == ["alpha"]
    assert manifest_inputs["graph_variable_keys"] == ["owner"]
    assert manifest_inputs["graph_query_configured"] is True


def test_evidence_run_cli_rejects_artifact_path_collisions(tmp_path, capsys):
    report_out = tmp_path / "daily.md"
    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(report_out),
            "--research-report-out",
            str(report_out),
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["reason_code"] == "evidence_run_path_collision"
    assert "daily_report" in payload["failure"]
    assert "research_report" in payload["failure"]
    assert not report_out.exists()
    assert not Path(payload["json_out"]).exists()
    assert not Path(payload["manifest_out"]).exists()
    assert not Path(payload["failed_marker_out"]).exists()


def test_evidence_run_cli_sanitizes_run_id_for_default_artifact_paths(
    tmp_path,
    capsys,
    monkeypatch,
):
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda _exchange_id: DeterministicCcxtCollector(),
    )
    db_path = tmp_path / "state" / "research.sqlite"
    raw_run_id = "../escape/../../signed?token=abc"

    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(db_path),
            "--memory",
            str(tmp_path / "state" / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "reports" / "daily.md"),
            "--run-id",
            raw_run_id,
            "--allow-network",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    manifest_out = Path(payload["manifest_out"]).resolve()
    failed_marker_out = Path(payload["failed_marker_out"]).resolve()
    manifest_root = (db_path.parent / "run-manifests").resolve()

    assert exit_code == 0
    assert payload["run_id"] == raw_run_id
    assert manifest_out.is_relative_to(manifest_root)
    assert failed_marker_out.is_relative_to(manifest_root)
    assert ".." not in manifest_out.name
    assert "/" not in manifest_out.name
    assert manifest_out.exists()


def test_generated_evidence_run_ids_are_unique_for_fast_retries(tmp_path):
    from crypto_alpha_agent.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(
        [
            "evidence-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "daily.md"),
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
        ]
    )

    first = args.handler.__globals__["_resolve_evidence_run_id"](args)
    second = args.handler.__globals__["_resolve_evidence_run_id"](args)

    assert first != second


def test_evidence_run_cli_reported_core_failure_is_nonzero(
    tmp_path,
    capsys,
    monkeypatch,
):
    class FailingCoreCollector:
        def fetch_ohlcv(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("core source down")

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda _exchange_id: FailingCoreCollector(),
    )
    failed_marker_out = tmp_path / "failed.json"

    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "daily.md"),
            "--failed-marker-out",
            str(failed_marker_out),
            "--allow-network",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["reason_code"] == "core_source_failed"
    assert payload["steps"][0]["status"] == "failed"
    assert failed_marker_out.exists()


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
