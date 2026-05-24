from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, OpenInterestRecord, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.pipeline.historical_bootstrap import build_historical_bootstrap_report
from crypto_alpha_agent.pipeline.markdown import render_historical_bootstrap_markdown


PAPER_FAMILIES = {
    "funding_extremity_price_confirmation",
    "funding_mean_reversion_after_extreme",
    "funding_open_interest_crowding",
}


def test_historical_bootstrap_report_classifies_windowed_strategy_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_bootstrap_fixture(db_path)

    report = build_historical_bootstrap_report(
        db_path=db_path,
        memory_path=memory_path,
        run_id="phase7-fixture",
        current_capital_usd=300.0,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        bootstrap_windows=[
            "2026-02-01/2026-03-01",
            "2026-03-01/2026-04-01",
            "2026-04-01/2026-05-01",
        ],
        allow_network=False,
    )

    assert report.command == "historical-bootstrap"
    assert report.run_id == "phase7-fixture"
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.network_route == "blocked"
    assert [window.window_id for window in report.bootstrap_windows] == [
        "2026-02-01_2026-03-01",
        "2026-03-01_2026-04-01",
        "2026-04-01_2026-05-01",
    ]
    assert report.bootstrap_windows[0].price_symbol == "BTC/USDT"
    assert report.bootstrap_windows[0].funding_symbol == "BTC/USDT:USDT"
    assert report.bootstrap_windows[0].timeframe == "1h"
    assert report.bootstrap_windows[0].start_at == datetime(2026, 2, 1, tzinfo=UTC)
    assert report.bootstrap_windows[0].end_at == datetime(2026, 3, 1, tzinfo=UTC)

    source_ids = {step.source_id for step in report.source_steps}
    assert {
        "binance_public_klines",
        "ccxt_funding_rate_history",
        "ccxt_open_interest_history",
        "binance_usdm_open_interest_history",
        "binance_usdm_basis",
        "binance_usdm_global_long_short_account_ratio",
    }.issubset(source_ids)
    assert all(step.network_route == "blocked" for step in report.source_steps)
    assert all(step.records_written == 0 for step in report.source_steps)

    paper_results = [
        result
        for result in report.strategy_results
        if result.paper_simulation_supported
    ]
    assert {result.strategy_family for result in paper_results} == PAPER_FAMILIES
    assert {result.window_id for result in paper_results} == {
        "2026-02-01_2026-03-01",
        "2026-03-01_2026-04-01",
        "2026-04-01_2026-05-01",
    }
    assert all(result.validation_status in {"passed", "blocked"} for result in paper_results)
    assert all(result.paper_outcome_count >= 1 for result in paper_results)
    assert all(result.cost_model_modes == ["pessimistic"] for result in paper_results)
    assert all(result.classification in {"usable", "blocked", "negative_after_costs", "observe_out_of_sample"} for result in paper_results)

    assert report.sample_targets.paper_observation_targets == [30, 60]
    assert report.sample_targets.calendar_day_target == 90
    assert report.sample_targets.current_observations_by_family == {}
    assert report.weekly_sample_progress == {}
    assert report.out_of_sample_policy == "future_evidence_run_observations_only"
    assert report.manifest.status == "success"
    assert report.manifest.memory_path == str(memory_path)
    assert PaperOutcomeLedger(db_path).load_outcomes() == []
    assert ValidationEvidenceLedger(db_path).load_evidence() == []


def test_historical_bootstrap_markdown_renders_phase7_targets(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_bootstrap_fixture(db_path)
    report = build_historical_bootstrap_report(
        db_path=db_path,
        memory_path=memory_path,
        run_id="phase7-markdown",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        bootstrap_windows=["2026-03-01/2026-04-01"],
        allow_network=False,
    )

    markdown = render_historical_bootstrap_markdown(report)

    assert markdown.startswith("# Phase 7 Historical Bootstrap Report")
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown
    assert "## Bootstrap Windows" in markdown
    assert "## Source Collection" in markdown
    assert "## Strategy Results" in markdown
    assert "## Forward Sample Progress" in markdown
    assert "## Forward 30/60/90 Evidence Targets" in markdown
    assert "future_evidence_run_observations_only" in markdown


def test_historical_bootstrap_cli_writes_markdown_json_and_manifest(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    out = tmp_path / "phase7.md"
    json_out = tmp_path / "phase7.json"
    manifest_out = tmp_path / "phase7.manifest.json"
    _seed_bootstrap_fixture(db_path)

    exit_code = main(
        [
            "historical-bootstrap",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--out",
            str(out),
            "--json-out",
            str(json_out),
            "--manifest-out",
            str(manifest_out),
            "--run-id",
            "phase7-cli",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--bootstrap-window",
            "2026-03-01/2026-04-01",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["command"] == "historical-bootstrap"
    assert payload["historical_bootstrap_report_out"] == str(out)
    assert payload["json_out"] == str(json_out)
    assert payload["manifest_out"] == str(manifest_out)
    assert payload["report"]["uses_real_capital"] is False
    assert payload["report"]["live_order_routing"] is False
    assert json_payload["command"] == "historical-bootstrap"
    assert manifest["run_id"] == "phase7-cli"
    assert manifest["status"] == "success"
    assert manifest["network_route"] == "blocked"
    assert manifest["memory_path"] == str(memory_path)
    assert out.read_text(encoding="utf-8").startswith("# Phase 7 Historical Bootstrap Report")


def test_historical_bootstrap_network_source_failure_marks_manifest_failed(tmp_path, monkeypatch):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    class Summary:
        records_written = 1

    class Probe:
        exit_code = 0
        source = "binance_usdm"
        feed = "probe"
        network_route = "direct"
        blocked_reason = None
        provider_status = "ResearchUsable"
        typed_record_count = 1
        endpoint_family = "probe"

    def fail_binance(*args, **kwargs):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.historical_bootstrap.ingest_binance_public_month",
        fail_binance,
    )
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.historical_bootstrap.ingest_ccxt_funding_rate_history",
        lambda *args, **kwargs: Summary(),
    )
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.historical_bootstrap.ingest_ccxt_open_interest_history",
        lambda *args, **kwargs: Summary(),
    )
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.historical_bootstrap.probe_target",
        lambda *args, **kwargs: Probe(),
    )

    report = build_historical_bootstrap_report(
        db_path=db_path,
        memory_path=memory_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        bootstrap_windows=["2026-03-01/2026-04-01"],
        strategy_families=["funding_extremity_price_confirmation"],
        allow_network=True,
    )

    assert report.manifest.status == "failed"
    assert report.manifest.reason_code == "source_collection_incomplete"
    assert any(step.status == "failed" for step in report.source_steps)


def test_historical_bootstrap_network_mode_requires_explicit_window(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    with pytest.raises(ValueError, match="requires at least one explicit"):
        build_historical_bootstrap_report(
            db_path=db_path,
            memory_path=memory_path,
            price_symbol="BTC/USDT",
            funding_symbol="BTC/USDT:USDT",
            timeframe="1h",
            allow_network=True,
        )


def test_historical_bootstrap_rejects_unknown_strategy_family(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    with pytest.raises(ValueError, match="unknown strategy family"):
        build_historical_bootstrap_report(
            db_path=db_path,
            memory_path=memory_path,
            price_symbol="BTC/USDT",
            funding_symbol="BTC/USDT:USDT",
            timeframe="1h",
            bootstrap_windows=["2026-03-01/2026-04-01"],
            strategy_families=["unknown_family"],
            allow_network=False,
        )


def test_historical_bootstrap_rejects_non_date_windows(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    with pytest.raises(ValueError, match="YYYY-MM-DD/YYYY-MM-DD"):
        build_historical_bootstrap_report(
            db_path=db_path,
            memory_path=memory_path,
            price_symbol="BTC/USDT",
            funding_symbol="BTC/USDT:USDT",
            timeframe="1h",
            bootstrap_windows=["2026-03-01T00:00:00/2026-04-01"],
            allow_network=False,
        )


def _seed_bootstrap_fixture(db_path) -> None:
    store = ResearchDataStore(db_path)
    for month in (2, 3, 4):
        start = datetime(2026, month, 1, tzinfo=UTC)
        closes = [100, 103, 101, 99, 102, 104, 101, 100, 98, 101]
        candles = [
            _candle_at(start + timedelta(hours=index), close)
            for index, close in enumerate(closes)
        ]
        fundings = [
            _funding_at(start + timedelta(hours=1), 0.0008),
            _funding_at(start + timedelta(hours=4), -0.0009),
            _funding_at(start + timedelta(hours=6), 0.0007),
        ]
        open_interest = [
            _open_interest_at(start + timedelta(hours=hour), 1000.0 + 100.0 * index)
            for index, hour in enumerate((0, 1, 4, 6))
        ]
        store.upsert_records([item.to_source_record() for item in candles])
        store.upsert_records([_funding_record(item) for item in fundings])
        store.upsert_records([item.to_source_record() for item in open_interest])


def _candle_at(timestamp: datetime, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=timestamp,
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=max(close - 1.0, 0.0),
        close=close,
        volume=1000.0,
    )


def _funding_at(timestamp: datetime, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=timestamp,
        funding_rate=rate,
    )


def _funding_record(funding: FundingRateRecord) -> SourceRecord:
    safe_symbol = funding.symbol.replace("/", "").replace(":", "-")
    return SourceRecord(
        record_id=f"{funding.source}:{safe_symbol}:funding:{funding.timestamp.isoformat()}",
        source=funding.source,
        record_type="funding_rate",
        observed_at=funding.timestamp,
        payload=funding.model_dump(mode="json"),
    )


def _open_interest_at(timestamp: datetime, value: float) -> OpenInterestRecord:
    return OpenInterestRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=timestamp,
        timeframe="1h",
        open_interest=value,
        open_interest_value=value * 100.0,
    )
