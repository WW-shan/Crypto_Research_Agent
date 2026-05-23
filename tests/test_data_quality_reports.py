from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.data.ingestion import ingest_ccxt_ohlcv
from crypto_alpha_agent.data.models import MarketCandle, OpenInterestRecord, SourceRecord
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


def test_quality_report_flags_open_interest_gaps_staleness_and_timestamp_skew():
    records = [
        _open_interest_record(NOW - timedelta(hours=4)),
        _open_interest_record(
            NOW - timedelta(hours=1),
            payload_timestamp=NOW - timedelta(hours=3),
        ),
    ]

    report = build_data_quality_report(records, now=NOW)

    assert "missing_open_interest_bars" in _reason_codes(report)
    assert "timestamp_skew" in _reason_codes(report)

    stale_report = build_data_quality_report([_open_interest_record(NOW - timedelta(hours=4))], now=NOW)
    assert "stale_source" in _reason_codes(stale_report)


def test_quality_report_flags_non_positive_open_interest():
    record = _open_interest_record(NOW - timedelta(hours=1))
    record.payload["open_interest"] = 0.0

    report = build_data_quality_report([record], now=NOW)

    assert "non_positive_open_interest" in _reason_codes(report)


def test_quality_report_flags_malformed_open_interest_timestamp_as_source_error():
    record = _open_interest_record(NOW - timedelta(hours=1))
    record.payload["timestamp"] = "not-a-date"

    report = build_data_quality_report([record], now=NOW)

    assert "source_error" in _reason_codes(report)


def test_quality_report_flags_duplicate_open_interest_by_semantic_key():
    timestamp = NOW - timedelta(hours=1)
    records = [
        _open_interest_record(timestamp, record_id="open-interest-a"),
        _open_interest_record(timestamp, record_id="open-interest-b"),
    ]

    report = build_data_quality_report(records, now=NOW)

    assert "duplicate_semantic_record" in _reason_codes(report)


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


def test_malformed_source_health_missing_feed_reports_source_error():
    record = SourceRecord(
        record_id="ccxt:source_health:malformed",
        source="ccxt",
        record_type="source_health",
        observed_at=NOW,
        payload={
            "source": "ccxt",
            "success": True,
            "attempts": 1,
            "observed_at": NOW.isoformat(),
            "records_fetched": 1,
            "records_written": 1,
        },
    )

    report = build_data_quality_report([record], now=NOW)

    assert _reason_codes(report) == ["source_error"]
    assert report.issues[0].message == "malformed source_health payload"


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


def _open_interest_record(
    timestamp: datetime,
    *,
    record_id: str | None = None,
    payload_timestamp: datetime | None = None,
) -> SourceRecord:
    record = OpenInterestRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=timestamp,
        timeframe="1h",
        open_interest=1000.0,
        open_interest_value=100000.0,
    ).to_source_record()
    if payload_timestamp is not None:
        record.payload["timestamp"] = payload_timestamp.isoformat()
    if record_id is None:
        return record
    return record.model_copy(update={"record_id": record_id})


def _reason_codes(report) -> list[str]:
    return sorted(issue.reason_code for issue in report.issues)
