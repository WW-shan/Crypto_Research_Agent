from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.ccxt_collector import CcxtResearchCollector


class FakeExchange:
    id = "binance"

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        return [[1747353600000, 65000.0, 65100.0, 64900.0, 65050.0, 123.4]]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None):
        return [{"symbol": symbol, "timestamp": 1747353600000, "fundingRate": 0.0003}]


class FakeExchangeWithoutFundingHistory:
    id = "coinbase"


class FakeExchangeWithParams:
    id = "okx"

    def __init__(self):
        self.ohlcv_params = None
        self.funding_params = None

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
        self.ohlcv_params = params
        return [[1747353600000, 65000.0, 65100.0, 64900.0, 65050.0, 123.4]]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None, params=None):
        self.funding_params = params
        return [{"symbol": symbol, "timestamp": 1747353600000, "fundingRate": 0.0003}]


def test_collects_ohlcv_with_low_latency_suitability():
    collector = CcxtResearchCollector(exchange=FakeExchange())

    candles = collector.fetch_ohlcv("BTC/USDT", "1h", limit=1)

    assert candles[0].venue == "binance"
    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)
    assert candles[0].suitability.latency_dependency == "low"


def test_collects_funding_history_when_exchange_supports_it():
    collector = CcxtResearchCollector(exchange=FakeExchange())

    funding = collector.fetch_funding_rate_history("BTC/USDT", limit=1)

    assert funding[0].funding_rate == 0.0003
    assert funding[0].suitability.execution_role == "research_and_paper"


def test_funding_history_requires_exchange_method_support():
    collector = CcxtResearchCollector(exchange=FakeExchangeWithoutFundingHistory())

    with pytest.raises(NotImplementedError, match="coinbase.*fetch_funding_rate_history"):
        collector.fetch_funding_rate_history("BTC/USDT", limit=1)


def test_passes_exchange_specific_params_to_ccxt_methods():
    exchange = FakeExchangeWithParams()
    collector = CcxtResearchCollector(exchange=exchange)

    collector.fetch_ohlcv("BTC/USDT", "1h", limit=1, params={"price": "mark"})
    collector.fetch_funding_rate_history("BTC/USDT", limit=1, params={"until": 1747353600000})

    assert exchange.ohlcv_params == {"price": "mark"}
    assert exchange.funding_params == {"until": 1747353600000}
