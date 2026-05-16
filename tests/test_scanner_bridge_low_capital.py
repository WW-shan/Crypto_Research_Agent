from datetime import UTC, datetime

from crypto_alpha_agent.data.models import (
    DataSuitability,
    DefiYieldSnapshot,
    DexPairSnapshot,
    MarketCandle,
)
from crypto_alpha_agent.data.scanner_bridge import records_to_scanner_signals


def test_candle_becomes_low_capital_scanner_signal():
    candle = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
        suitability=DataSuitability(
            min_capital_usd=25, latency_dependency="low", rpc_dependency="none"
        ),
    )

    signals = records_to_scanner_signals([candle], current_capital_usd=300)

    assert signals[0].category == "cex"
    assert signals[0].capital_required_usd == 25.0
    assert signals[0].speed_dependency == "low"


def test_high_capital_dex_pair_is_research_only_and_weak():
    pair = DexPairSnapshot(
        source="dexscreener",
        chain="base",
        dex="uniswap",
        pair_address="0xabc",
        base_token="ABC",
        quote_token="USDC",
        price_usd=1.0,
        liquidity_usd=1000.0,
        volume_24h_usd=100.0,
        observed_at=datetime(2026, 5, 16, tzinfo=UTC),
        suitability=DataSuitability(
            min_capital_usd=1000.0,
            latency_dependency="medium",
            rpc_dependency="none",
            execution_role="research_only",
            unsuitable_reasons=["liquidity_too_low"],
        ),
    )

    signals = records_to_scanner_signals([pair], current_capital_usd=300)

    assert signals[0].weak_signal is True
    assert "liquidity_too_low" in signals[0].evidence


def test_healthy_defi_yield_becomes_chain_signal():
    yield_snapshot = DefiYieldSnapshot(
        source="defillama",
        chain="base",
        project="aave-v3",
        symbol="USDC",
        tvl_usd=1_000_000.0,
        apy=4.25,
        observed_at=datetime(2026, 5, 16, tzinfo=UTC),
        suitability=DataSuitability(
            min_capital_usd=100.0,
            latency_dependency="low",
            rpc_dependency="none",
        ),
    )

    signals = records_to_scanner_signals([yield_snapshot], current_capital_usd=300)

    assert signals[0].category == "chain"
    assert signals[0].metric == "defi_yield"
    assert signals[0].rpc_dependency == "none"
    assert signals[0].weak_signal is False


def test_capital_requirement_above_current_capital_sets_weak_signal():
    candle = MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="ETH/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
        suitability=DataSuitability(
            min_capital_usd=500.0,
            latency_dependency="low",
            rpc_dependency="none",
            unsuitable_reasons=[],
        ),
    )

    signals = records_to_scanner_signals([candle], current_capital_usd=300)

    assert signals[0].weak_signal is True
