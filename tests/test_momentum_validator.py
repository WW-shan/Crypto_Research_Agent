from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.validation.market_history import CandleBar
from crypto_alpha_agent.validation.momentum import validate_close_momentum


def _bars(closes: list[float], *, symbol: str = "BTC/USDT", timeframe: str = "1h") -> list[CandleBar]:
    start = datetime(2026, 5, 16, tzinfo=UTC)
    return [
        CandleBar(
            source="binance_public",
            venue="binance",
            symbol=symbol,
            timestamp=start + timedelta(hours=index),
            timeframe=timeframe,
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=1000.0,
        )
        for index, close in enumerate(closes)
    ]


def test_momentum_validator_returns_fee_and_slippage_adjusted_metrics():
    result = validate_close_momentum(
        _bars([100, 103, 106, 104, 108, 112, 109, 113]),
        lookback_bars=1,
        hold_bars=1,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=2,
    )

    assert result.strategy_family == "close_momentum"
    assert result.symbol == "BTC/USDT"
    assert result.timeframe == "1h"
    assert result.bar_count == 8
    assert result.trade_count >= 2
    assert result.gross_expectancy > 0.0
    assert result.net_return > 0.0
    assert result.fee_adjusted_expectancy < result.gross_expectancy
    assert result.slippage_adjusted_expectancy < result.gross_expectancy
    assert result.approved is True
    assert result.blocked_reasons == []


def test_momentum_validator_blocks_when_trade_count_is_too_low():
    result = validate_close_momentum(
        _bars([100, 99, 98, 97]),
        lookback_bars=1,
        hold_bars=1,
        min_trades=1,
    )

    assert result.trade_count == 0
    assert result.approved is False
    assert "insufficient_trades" in result.blocked_reasons


@pytest.mark.parametrize("lookback_bars, hold_bars", [(0, 1), (1, 0)])
def test_momentum_validator_rejects_invalid_windows(lookback_bars: int, hold_bars: int):
    with pytest.raises(ValueError):
        validate_close_momentum(_bars([100, 101, 102]), lookback_bars=lookback_bars, hold_bars=hold_bars)


def test_momentum_validator_rejects_mixed_symbols_or_timeframes():
    mixed_symbols = [*_bars([100, 101]), *_bars([102], symbol="ETH/USDT")]
    with pytest.raises(ValueError, match="one symbol"):
        validate_close_momentum(mixed_symbols)

    mixed_timeframes = [*_bars([100, 101]), *_bars([102], timeframe="4h")]
    with pytest.raises(ValueError, match="one timeframe"):
        validate_close_momentum(mixed_timeframes)
