from datetime import UTC, datetime

import pytest

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


def _candle_at(day: int, hour: int, close: float) -> MarketCandle:
    return _candle(hour, close).model_copy(
        update={"timestamp": datetime(2026, 5, day, hour, tzinfo=UTC)}
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        funding_rate=rate,
    )


def _funding_at(day: int, hour: int, rate: float) -> FundingRateRecord:
    return _funding(hour, rate).model_copy(
        update={"timestamp": datetime(2026, 5, day, hour, tzinfo=UTC)}
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


def _write_happy_path_fixture(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])
    ]
    fundings = [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([_funding_record(item) for item in fundings])
    return db_path


def test_funding_price_validator_measures_extreme_reversion_edge(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)

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
    raw_returns = [4 / 103, -1 / 102, 3 / 101]
    adjusted_returns = [trade_return - 0.003 for trade_return in raw_returns]
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for trade_return in adjusted_returns:
        equity *= 1.0 + trade_return
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
    assert result.gross_expectancy == pytest.approx(sum(raw_returns) / len(raw_returns))
    assert result.fee_adjusted_expectancy == pytest.approx(
        sum(trade_return - 0.002 for trade_return in raw_returns) / len(raw_returns)
    )
    assert result.slippage_adjusted_expectancy == pytest.approx(
        sum(adjusted_returns) / len(adjusted_returns)
    )
    assert result.net_return == pytest.approx(equity - 1.0)
    assert result.max_drawdown == pytest.approx(max_drawdown)
    assert result.fee_adjusted_expectancy != result.gross_expectancy
    assert result.slippage_adjusted_expectancy != result.gross_expectancy
    assert result.approved is True
    assert result.blocked_reasons == []


def test_extract_funding_price_trades_returns_canonical_trade_fields(tmp_path):
    from crypto_alpha_agent.validation.funding_price import (
        extract_funding_price_trades,
    )
    from crypto_alpha_agent.validation.market_history import load_candle_history

    db_path = _write_happy_path_fixture(tmp_path)
    bars = load_candle_history(db_path, symbol="BTC/USDT", timeframe="1h")
    funding_rates = [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]

    trades = extract_funding_price_trades(
        bars,
        funding_rates,
        threshold_abs=0.0005,
        hold_bars=2,
    )

    assert len(trades) == 3
    assert trades[0].funding_symbol == "BTC/USDT:USDT"
    assert trades[0].funding_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert trades[0].funding_rate == pytest.approx(0.0008)
    assert trades[0].entry_index == 1
    assert trades[0].exit_index == 3
    assert trades[0].entry_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert trades[0].exit_timestamp == datetime(2026, 5, 17, 3, tzinfo=UTC)
    assert trades[0].entry_price == 103.0
    assert trades[0].exit_price == 99.0
    assert trades[0].direction == "short_price"
    assert trades[0].raw_return == pytest.approx(4.0 / 103.0)
    assert trades[1].direction == "long_price"
    assert trades[1].raw_return == pytest.approx(-1.0 / 102.0)


def test_funding_price_validator_fails_closed_when_walk_forward_required(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)

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
    )

    assert result.approved is False
    assert result.walk_forward_split_count == 0
    assert "insufficient_walk_forward_splits" in result.blocked_reasons


def test_funding_price_validator_fails_closed_on_duplicate_price_timestamp(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)
    duplicate_candle = _candle(4, 999.0).model_copy(
        update={"source": "coinbase_public", "venue": "coinbase"}
    )
    ResearchDataStore(db_path).upsert_records([duplicate_candle.to_source_record()])

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

    assert result.approved is False
    assert "duplicate_price_timestamp" in result.blocked_reasons


def test_funding_price_validator_fails_closed_on_duplicate_funding_timestamp(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)
    duplicate_funding = _funding(4, -0.0009).model_copy(
        update={"source": "okx_ccxt", "venue": "okx"}
    )
    ResearchDataStore(db_path).upsert_records([_funding_record(duplicate_funding)])

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

    assert result.approved is False
    assert "duplicate_funding_timestamp" in result.blocked_reasons


def test_funding_price_validator_fails_closed_on_non_positive_exit_price(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)
    zero_exit_candle = _candle(3, 1.0).model_copy(update={"close": 0.0})
    ResearchDataStore(db_path).upsert_records([zero_exit_candle.to_source_record()])

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

    assert result.approved is False
    assert "non_positive_price" in result.blocked_reasons


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


def test_funding_price_validator_fails_closed_on_unsupported_symbols(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="DOGE/USDT",
        funding_symbol="DOGE/USDT:USDT",
        timeframe="1h",
        supported_price_symbols=("BTC/USDT",),
        supported_funding_symbols=("BTC/USDT:USDT",),
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "unsupported_symbol" in result.blocked_reasons


def test_funding_price_validator_fails_closed_on_stale_source_data(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)

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
        now=datetime(2026, 5, 24, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert result.approved is False
    assert "stale_source" in result.blocked_reasons


def test_funding_price_validator_fails_closed_when_funding_feed_is_stale_but_prices_are_fresh(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle_at(24, index, close).to_source_record()
            for index, close in enumerate([100, 103, 101, 99, 102])
        ]
    )
    store.upsert_records([_funding_record(_funding_at(17, 1, 0.0008))])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=0,
        require_walk_forward=False,
        now=datetime(2026, 5, 24, 4, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert result.approved is False
    assert "stale_source" in result.blocked_reasons


def test_funding_price_validator_fails_closed_when_price_feed_is_stale_but_funding_is_fresh(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle_at(17, index, close).to_source_record()
            for index, close in enumerate([100, 103, 101, 99, 102])
        ]
    )
    store.upsert_records([_funding_record(_funding_at(24, 1, 0.0008))])

    result = validate_funding_price_confirmation(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=0,
        require_walk_forward=False,
        now=datetime(2026, 5, 24, 4, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert result.approved is False
    assert "stale_source" in result.blocked_reasons


def test_funding_price_validator_fails_closed_on_excessive_drawdown(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)

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
        max_drawdown_limit=0.001,
    )

    assert result.approved is False
    assert result.max_drawdown > 0.001
    assert "excessive_drawdown" in result.blocked_reasons


def test_funding_price_validator_fails_closed_on_invalid_funding_alignment(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])
    ]
    invalid_funding = _funding(1, 0.0008).model_copy(
        update={"next_funding_at": datetime(2026, 5, 17, 1, tzinfo=UTC)}
    )
    fundings = [invalid_funding, _funding(4, -0.0009), _funding(6, 0.0007)]
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

    assert result.approved is False
    assert "funding_alignment_invalid" in result.blocked_reasons
