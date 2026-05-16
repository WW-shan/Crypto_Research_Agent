from __future__ import annotations

import json
from datetime import UTC, datetime

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _store_momentum_candles(db_path) -> None:
    ResearchDataStore(db_path).upsert_records(
        [
            _candle(index, close).to_source_record()
            for index, close in enumerate([100, 103, 106, 104, 108, 112, 109, 113])
        ]
    )


def test_research_loop_can_include_historical_validation_summary(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _store_momentum_candles(db_path)

    report = run_stored_research_loop(db_path, include_validation=True)

    assert len(report.validation_summaries) == 1
    summary = report.validation_summaries[0]
    assert summary.strategy_family == "close_momentum"
    assert summary.asset == "BTC/USDT"
    assert summary.timeframe == "1h"
    assert summary.trade_count >= 2
    assert summary.fee_adjusted_expectancy is not None


def test_research_loop_cli_markdown_includes_validation_section(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "report.md"
    _store_momentum_candles(db_path)

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-validation",
            "--report-out",
            str(report_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["report"]["validation_summaries"][0]["strategy_family"] == "close_momentum"
    text = report_path.read_text(encoding="utf-8")
    assert "## Historical Validation" in text
    assert "close_momentum" in text


def test_research_loop_skips_validation_by_default(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _store_momentum_candles(db_path)

    report = run_stored_research_loop(db_path)

    assert report.validation_summaries == []
