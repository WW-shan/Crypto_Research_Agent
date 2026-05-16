from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.data.models import (
    FundingRateRecord,
    MarketCandle,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def test_stored_research_loop_generates_hypotheses_from_sqlite_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    observed_at = datetime(2026, 5, 16, tzinfo=UTC)
    candle = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=observed_at,
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    )
    funding = FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=observed_at + timedelta(minutes=1),
        funding_rate=0.0003,
    )
    funding_record = SourceRecord(
        record_id="ccxt:BTCUSDT:funding:2026-05-16T00:01:00+00:00",
        source="ccxt",
        record_type="funding_rate",
        observed_at=funding.timestamp,
        payload=funding.model_dump(mode="json"),
    )
    ResearchDataStore(db_path).upsert_records([candle.to_source_record(), funding_record])

    report = run_stored_research_loop(db_path)

    assert report.loaded_records == 2
    assert report.signal_count == 2
    assert report.anomaly_count == 2
    assert report.hypothesis_count == 2
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.hypotheses[0].action_mode == "research_only"
    assert report.model_dump(mode="json")["hypotheses"][0]["action_mode"] == "research_only"


def test_stored_research_loop_reports_empty_store_without_error(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    ResearchDataStore(db_path)

    report = run_stored_research_loop(db_path)

    assert report.loaded_records == 0
    assert report.signal_count == 0
    assert report.anomaly_count == 0
    assert report.hypothesis_count == 0
    assert "no_stored_records" in report.notes


def test_stored_research_loop_applies_source_filter_and_recent_limit(tmp_path):
    db_path = tmp_path / "filtered.sqlite"
    store = ResearchDataStore(db_path)
    first = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, 0, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    ).to_source_record()
    second = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="ETH/USDT",
        timestamp=datetime(2026, 5, 16, 1, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=109.0,
        volume=1000.0,
    ).to_source_record()
    other_source = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="SOL/USDT",
        timestamp=datetime(2026, 5, 16, 2, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=107.0,
        volume=1000.0,
    ).to_source_record()
    store.upsert_records([first, second, other_source])

    report = run_stored_research_loop(db_path, source="ccxt", limit=1)

    assert report.loaded_records == 1
    assert [record.record_id for record in report.records] == [second.record_id]
    assert report.source_filter == "ccxt"
