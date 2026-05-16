from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


def test_research_loop_cli_rejects_non_finite_current_capital(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    with pytest.raises(SystemExit):
        main(
            [
                "research-loop",
                "--db",
                str(db_path),
                "--current-capital-usd",
                "nan",
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
