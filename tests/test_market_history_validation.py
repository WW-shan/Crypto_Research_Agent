from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation import CandleBar
from crypto_alpha_agent.validation.market_history import load_candle_history


def _candle(
    symbol: str,
    hour: int,
    close: float,
    source: str = "binance_public",
) -> MarketCandle:
    return MarketCandle(
        source=source,
        venue="binance",
        symbol=symbol,
        timestamp=datetime(2026, 5, 16, hour, tzinfo=UTC),
        timeframe="1h",
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=1000.0 + hour,
    )


def test_load_candle_history_filters_symbol_timeframe_and_sorts(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    records = [
        _candle("ETH/USDT", 1, 201.0).to_source_record(),
        _candle("BTC/USDT", 2, 102.0).to_source_record(),
        _candle("BTC/USDT", 0, 100.0).to_source_record(),
        _candle("BTC/USDT", 1, 101.0).to_source_record(),
    ]
    store.upsert_records(records)

    bars = load_candle_history(db_path, symbol="BTC/USDT", timeframe="1h")

    assert [bar.close for bar in bars] == [100.0, 101.0, 102.0]
    assert [bar.timestamp.hour for bar in bars] == [0, 1, 2]
    assert bars[0].source == "binance_public"
    assert isinstance(bars[0], CandleBar)


def test_load_candle_history_applies_date_range_source_and_recent_limit(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle("BTC/USDT", 0, 100.0).to_source_record(),
            _candle("BTC/USDT", 1, 101.0, source="ccxt").to_source_record(),
            _candle("BTC/USDT", 2, 102.0).to_source_record(),
            _candle("BTC/USDT", 3, 103.0).to_source_record(),
        ]
    )

    bars = load_candle_history(
        db_path,
        symbol="BTC/USDT",
        timeframe="1h",
        source="binance_public",
        start=datetime(2026, 5, 16, 1, tzinfo=UTC),
        end=datetime(2026, 5, 16, 4, tzinfo=UTC),
        limit=2,
    )

    assert [bar.close for bar in bars] == [102.0, 103.0]


def test_load_candle_history_rejects_non_positive_limit(tmp_path):
    db_path = tmp_path / "research.sqlite"

    with pytest.raises(ValueError, match="limit must be greater than 0"):
        load_candle_history(db_path, symbol="BTC/USDT", timeframe="1h", limit=0)
