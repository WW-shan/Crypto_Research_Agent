from datetime import UTC, datetime

from crypto_alpha_agent.data.models import (
    DataSuitability,
    MarketCandle,
    OpenInterestRecord,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


def test_market_candle_preserves_low_capital_suitability():
    candle = MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=65000.0,
        high=65100.0,
        low=64900.0,
        close=65050.0,
        volume=123.4,
        suitability=DataSuitability(
            min_capital_usd=25.0,
            latency_dependency="low",
            rpc_dependency="none",
            execution_role="research_and_paper",
        ),
        raw={"source_line": "fixture"},
    )

    assert candle.suitability.execution_role == "research_and_paper"
    assert candle.suitability.latency_dependency == "low"


def test_store_round_trips_source_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    record = SourceRecord(
        record_id="binance_public:BTCUSDT:1h:2026-05-16T00:00:00+00:00",
        source="binance_public",
        record_type="market_candle",
        observed_at=datetime(2026, 5, 16, tzinfo=UTC),
        payload={
            "symbol": "BTC/USDT",
            "close": 65050.0,
            "suitability": {"latency_dependency": "low", "rpc_dependency": "none"},
        },
    )

    store.upsert_records([record])
    loaded = store.load_records(record_type="market_candle")

    assert [item.record_id for item in loaded] == [record.record_id]
    assert loaded[0].payload["symbol"] == "BTC/USDT"


def test_open_interest_record_round_trips_as_typed_slow_data(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    open_interest = OpenInterestRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open_interest=20403.637,
        open_interest_value=150570784.07809979,
        raw={"sumOpenInterest": "20403.63700000"},
    )

    store.upsert_records([open_interest.to_source_record()])
    loaded = store.load_records(record_type="open_interest", source="ccxt")

    assert [item.record_id for item in loaded] == [
        "ccxt:binance:BTCUSDT-USDT:open_interest:1h:2026-05-16T00:00:00+00:00"
    ]
    assert loaded[0].payload["symbol"] == "BTC/USDT:USDT"
    assert loaded[0].payload["open_interest"] == 20403.637
    assert loaded[0].payload["suitability"]["execution_role"] == "research_and_paper"
