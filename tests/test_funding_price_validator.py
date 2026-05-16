from datetime import UTC, datetime

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.validation.funding_price import validate_funding_price_confirmation


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
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


def test_funding_price_validator_measures_extreme_reversion_edge(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [_candle(i, close) for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])]
    fundings = [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([_funding_record(item) for item in fundings])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=2,
        require_walk_forward=False,
    )

    assert result.strategy_family == "funding_extremity_price_confirmation"
    assert result.trade_count == 3
    assert result.extreme_count == 3
    assert result.fee_adjusted_expectancy != result.gross_expectancy
    assert result.slippage_adjusted_expectancy != result.gross_expectancy
    assert result.approved is True
    assert result.blocked_reasons == []


def test_funding_price_validator_blocks_without_enough_trades(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records([_candle(i, 100.0 + i).to_source_record() for i in range(4)])
    store.upsert_records([_funding_record(_funding(1, 0.0008))])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        min_trades=2,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "insufficient_trades" in result.blocked_reasons


def test_funding_price_validator_blocks_missing_price_or_funding_data(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        require_walk_forward=False,
    )

    assert result.trade_count == 0
    assert "insufficient_price_bars" in result.blocked_reasons
    assert "insufficient_funding_samples" in result.blocked_reasons
