from __future__ import annotations

import json
from datetime import UTC, datetime

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
