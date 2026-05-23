from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.ingestion import IngestionSummary
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


@pytest.mark.parametrize("capital", ["nan", "inf"])
def test_research_loop_cli_rejects_non_finite_current_capital(capsys, tmp_path, capital):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    with pytest.raises(SystemExit):
        main(
            [
                "research-loop",
                "--db",
                str(db_path),
                "--current-capital-usd",
                capital,
            ]
        )

    captured = capsys.readouterr()
    assert "finite positive capital" in captured.err
    assert "Traceback" not in captured.err


def test_research_loop_cli_rejects_missing_db_without_creating_it(tmp_path):
    db_path = tmp_path / "missing.sqlite"

    with pytest.raises(SystemExit):
        main(["research-loop", "--db", str(db_path)])

    assert not db_path.exists()


def test_research_loop_cli_rejects_binance_public_without_network_gate(capsys, tmp_path):
    db_path = tmp_path / "missing.sqlite"

    with pytest.raises(SystemExit):
        main(
            [
                "research-loop",
                "--db",
                str(db_path),
                "--source",
                "binance-public",
                "--symbol",
                "BTCUSDT",
                "--year",
                "2026",
                "--month",
                "5",
            ]
        )

    captured = capsys.readouterr()
    assert "--allow-network is required" in captured.err
    assert "Traceback" not in captured.err
    assert not db_path.exists()


def test_research_loop_cli_filters_binance_public_offline_with_cli_source_spelling(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTCUSDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    )
    ResearchDataStore(db_path).upsert_records([candle.to_source_record()])

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--source",
            "binance-public",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["report"]["loaded_records"] == 1
    assert captured["report"]["source_filter"] == "binance_public"
    assert "ingestion" not in captured


def test_research_loop_cli_rejects_invalid_ingestion_month_before_call(capsys, monkeypatch, tmp_path):
    db_path = tmp_path / "research.sqlite"

    def fail_ingest_binance_public_month(*args, **kwargs):
        raise AssertionError("ingestion should not be called")

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.ingest_binance_public_month",
        fail_ingest_binance_public_month,
    )

    with pytest.raises(SystemExit):
        main(
            [
                "research-loop",
                "--db",
                str(db_path),
                "--source",
                "binance-public",
                "--symbol",
                "BTCUSDT",
                "--year",
                "2026",
                "--month",
                "13",
                "--allow-network",
            ]
        )

    captured = capsys.readouterr()
    assert "invalid month" in captured.err or "1-12" in captured.err
    assert "Traceback" not in captured.err
    assert not db_path.exists()


def test_research_loop_cli_rejects_directory_db_path(capsys, tmp_path):
    db_path = tmp_path / "research-dir"
    db_path.mkdir()

    with pytest.raises(SystemExit):
        main(["research-loop", "--db", str(db_path)])

    captured = capsys.readouterr()
    assert "not a file" in captured.err
    assert "Traceback" not in captured.err


def test_research_loop_cli_reads_existing_sqlite_records(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    candle = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    )
    ResearchDataStore(db_path).upsert_records([candle.to_source_record()])

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--current-capital-usd",
            "300",
            "--run-id",
            "cli-loop",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["command"] == "research-loop"
    assert captured["mode"] == "research_only"
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert captured["report"]["run_id"] == "cli-loop"
    assert captured["report"]["loaded_records"] == 1
    assert captured["report"]["signal_count"] == 1
    assert captured["report"]["anomaly_count"] == 1
    assert captured["report"]["hypothesis_count"] == 1


def test_research_loop_can_run_configured_llm_and_persist_metadata_only(
    capsys,
    monkeypatch,
    tmp_path,
):
    from crypto_alpha_agent.memory.store import MemoryStore

    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    candle = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    )
    ResearchDataStore(db_path).upsert_records([candle.to_source_record()])
    seen: dict[str, Any] = {}
    monkeypatch.setenv("CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS", "1")

    def fake_llm(task):
        seen["task"] = task
        return json.dumps(
            {
                "proposal_id": "llm-cli-research-001",
                "thesis": "Public funding and price evidence can be researched at low frequency.",
                "hypothesis": "Funding extremity plus price confirmation may identify a paper-testable setup.",
                "assumptions": ["Public candle data and funding data remain available."],
                "evidence": ["Stored research loop produced one BTC/USDT signal."],
                "disconfirmation": ["Reject if validation expectancy is non-positive after costs."],
                "data_needed": ["market_candle", "funding_rate"],
                "capital_required_usd": 25.0,
                "speed_dependency": "none",
                "rpc_dependency": "none",
                "action_mode": "research_only",
            }
        )

    def fake_build_configured_llm(*, role, required=False, **_kwargs):
        seen["role"] = role
        seen["required"] = required
        return fake_llm

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_configured_llm",
        fake_build_configured_llm,
        raising=False,
    )

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--run-id",
            "llm-cli-research",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    records = MemoryStore(memory_path).list_records()
    llm_records = [record for record in records if "llm" in record.tags]
    persisted_records = [record.model_dump(mode="json") for record in llm_records]

    assert exit_code == 0
    assert seen["role"] == "research"
    assert seen["required"] is False
    assert seen["task"].task_id == "llm-research"
    assert payload["llm_used"] is True
    assert payload["llm_research_result"]["accepted"] is True
    assert "raw_response" not in payload["llm_research_result"]
    assert payload["llm_research_result"]["raw_response_metadata"]["raw_response_omitted"] is True
    assert len(llm_records) == 1
    assert not _contains_key(persisted_records, "raw_response")
    assert llm_records[0].hypothesis["llm_response"]["raw_response_omitted"] is True


def test_research_loop_cli_writes_markdown_report(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "reports" / "daily.md"
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="SOL/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    )
    ResearchDataStore(db_path).upsert_records([candle.to_source_record()])

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--report-out",
            str(report_path),
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["report_artifact"] == str(report_path)
    report_text = report_path.read_text(encoding="utf-8")
    assert "# Crypto Alpha Research Loop" in report_text
    assert "SOL/USDT" in report_text
    assert "Live order routing: false" in report_text
    assert "Hypotheses: 1" in report_text


def test_research_loop_cli_can_ingest_binance_before_loop(capsys, monkeypatch, tmp_path):
    db_path = tmp_path / "research.sqlite"

    def fake_ingest_binance_public_month(*args, **kwargs):
        assert args == ()
        assert kwargs["allow_network"] is True
        candle = MarketCandle(
            source="binance_public",
            venue="binance",
            symbol="BTCUSDT",
            timestamp=datetime(2026, 5, 1, tzinfo=UTC),
            timeframe="1h",
            open=100.0,
            high=110.0,
            low=99.0,
            close=108.0,
            volume=1000.0,
        )
        records_written = ResearchDataStore(kwargs["db_path"]).upsert_records(
            [candle.to_source_record()]
        )
        return IngestionSummary(
            source="binance_public",
            db_path=str(kwargs["db_path"]),
            symbols=[kwargs["symbol"]],
            timeframe=kwargs["interval"],
            year=kwargs["year"],
            month=kwargs["month"],
            records_fetched=1,
            records_written=records_written,
            network_allowed=True,
            uses_real_capital=False,
            live_order_routing=False,
            notes=["fake_ingestion"],
        )

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.ingest_binance_public_month",
        fake_ingest_binance_public_month,
    )

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--source",
            "binance-public",
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--year",
            "2026",
            "--month",
            "5",
            "--allow-network",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["ingestion"]["records_written"] == 1
    assert captured["report"]["loaded_records"] == 1
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert captured["ingestion"]["uses_real_capital"] is False
    assert captured["ingestion"]["live_order_routing"] is False


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        if key in value:
            return True
        return any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False
