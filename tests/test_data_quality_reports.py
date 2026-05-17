from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.data.ingestion import ingest_ccxt_ohlcv
from crypto_alpha_agent.data.models import MarketCandle, SourceRecord
from crypto_alpha_agent.data.quality import build_data_quality_report
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.markdown import render_research_loop_markdown
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


NOW = datetime(2026, 5, 17, 12, tzinfo=UTC)


class SuccessfulOhlcvCollector:
    def fetch_ohlcv(self, symbol, timeframe, *, since=None, limit=None, params=None):
        return [
            MarketCandle(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=NOW - timedelta(hours=1),
                timeframe=timeframe,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=25.0,
            )
        ]


class FailingOhlcvCollector:
    def fetch_ohlcv(self, symbol, timeframe, *, since=None, limit=None, params=None):
        raise RuntimeError("upstream unavailable")


def test_quality_report_flags_missing_ohlcv_timestamp_gaps():
    records = [
        _market_record(NOW - timedelta(hours=3)),
        _market_record(NOW - timedelta(hours=1)),
    ]

    report = build_data_quality_report(records, now=NOW)

    assert _reason_codes(report) == ["missing_ohlcv_bars"]
    assert report.issues[0].semantic_key == "ccxt:binance:BTC/USDT:1h"


def test_quality_report_flags_duplicate_source_records_by_semantic_key():
    timestamp = NOW - timedelta(hours=1)
    records = [
        _market_record(timestamp, record_id="record-a"),
        _market_record(timestamp, record_id="record-b"),
    ]

    report = build_data_quality_report(records, now=NOW)

    assert "duplicate_semantic_record" in _reason_codes(report)


def test_quality_report_flags_latest_record_stale_relative_to_supplied_now():
    records = [_market_record(NOW - timedelta(hours=6))]

    report = build_data_quality_report(records, now=NOW)

    assert "stale_source" in _reason_codes(report)


def test_quality_report_flags_non_positive_prices_and_zero_volume():
    record = _market_record(NOW - timedelta(hours=1))
    record.payload["close"] = 0.0
    record.payload["volume"] = 0.0

    report = build_data_quality_report([record], now=NOW)

    assert "non_positive_price" in _reason_codes(report)
    assert "zero_volume" in _reason_codes(report)


def test_source_health_rows_are_written_after_ingestion_success_and_failure(tmp_path):
    db_path = tmp_path / "research.sqlite"

    success = ingest_ccxt_ohlcv(
        db_path,
        symbol="BTC/USDT",
        timeframe="1h",
        allow_network=True,
        collector=SuccessfulOhlcvCollector(),
    )
    with pytest.raises(RuntimeError, match="upstream unavailable"):
        ingest_ccxt_ohlcv(
            db_path,
            symbol="ETH/USDT",
            timeframe="1h",
            allow_network=True,
            collector=FailingOhlcvCollector(),
        )

    records = ResearchDataStore(db_path).load_records(record_type="source_health", source="ccxt")

    assert success.records_written == 1
    assert [record.payload["success"] for record in records] == [True, False]
    assert records[0].payload["feed"] == "ohlcv"
    assert records[0].payload["records_fetched"] == 1
    assert records[0].payload["records_written"] == 1
    assert records[1].payload["failure"] == "upstream unavailable"


def test_research_loop_and_markdown_include_data_quality_section(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records([_market_record(NOW - timedelta(hours=6))])

    report = run_stored_research_loop(db_path, data_quality_now=NOW)
    markdown = render_research_loop_markdown(report)

    assert report.data_quality_reports
    assert "stale_source" in _reason_codes(report.data_quality_reports[0])
    assert "## Data Quality" in markdown
    assert "stale_source" in markdown


def _market_record(
    timestamp: datetime,
    *,
    record_id: str | None = None,
    source: str = "ccxt",
) -> SourceRecord:
    candle = MarketCandle(
        source=source,
        venue="binance",
        symbol="BTC/USDT",
        timestamp=timestamp,
        timeframe="1h",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=25.0,
    ).to_source_record()
    if record_id is None:
        return candle
    return candle.model_copy(update={"record_id": record_id})


def _reason_codes(report) -> list[str]:
    return sorted(issue.reason_code for issue in report.issues)
