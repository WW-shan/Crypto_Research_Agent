from __future__ import annotations

from datetime import UTC, datetime

from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.strategy import (
    StrategyPaperRequest,
    StrategyValidationRequest,
    default_strategy_registry,
)


def _candle(hour: int, close: float, volume: float, *, symbol: str = "BTC/USDT") -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol=symbol,
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=max(0.0, close - 1.0),
        close=close,
        volume=volume,
    )


def _records(
    closes: list[float],
    volumes: list[float],
    *,
    symbol: str = "BTC/USDT",
) -> tuple[dict[str, object], ...]:
    return tuple(
        _candle(index, close, volumes[index], symbol=symbol)
        .to_source_record()
        .model_dump(mode="json")
        for index, close in enumerate(closes)
    )


def test_volatility_regime_watchlist_flags_compression_expansion_candidate():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        STRATEGY_FAMILY,
        validate_volatility_regime_watchlist,
    )

    report = validate_volatility_regime_watchlist(
        _records(
            [100.0, 100.1, 100.0, 100.05, 100.0, 100.1, 102.5],
            [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
        ),
        compression_window=5,
        expansion_window=1,
        max_compression_volatility=0.002,
        min_expansion_return_abs=0.01,
        min_volume_change_pct=0.25,
        min_observations=7,
    )

    assert report.strategy_family == STRATEGY_FAMILY
    assert report.validator_name == "volatility_regime_watchlist"
    assert report.approved is True
    assert report.blocked_reasons == ()
    assert report.metrics["execution_role"] == "research_only"
    assert report.metrics["paper_watchlist_only"] is True
    assert report.metrics["candidate_count"] == 1
    candidate = report.metrics["candidates"][0]
    assert candidate["symbol"] == "BTC/USDT"
    assert candidate["direction"] == "expansion_up"
    assert candidate["compression_volatility"] <= 0.002
    assert candidate["volume_change_pct"] >= 0.25


def test_volatility_regime_watchlist_fails_closed_without_market_candles():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        validate_volatility_regime_watchlist,
    )

    report = validate_volatility_regime_watchlist([])

    assert report.approved is False
    assert "missing_market_candle_records" in report.blocked_reasons


def test_volatility_regime_watchlist_fails_closed_on_insufficient_history():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        validate_volatility_regime_watchlist,
    )

    report = validate_volatility_regime_watchlist(
        _records([100.0, 100.1, 100.0], [900.0, 920.0, 910.0]),
        compression_window=5,
        expansion_window=1,
        min_observations=7,
    )

    assert report.approved is False
    assert "insufficient_history" in report.blocked_reasons


def test_volatility_regime_watchlist_fails_closed_on_stale_source_data():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        validate_volatility_regime_watchlist,
    )

    report = validate_volatility_regime_watchlist(
        _records(
            [100.0, 100.1, 100.0, 100.05, 100.0, 100.1, 102.5],
            [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
        ),
        compression_window=5,
        expansion_window=1,
        min_observations=7,
        now=datetime(2026, 5, 24, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert report.approved is False
    assert "stale_source" in report.blocked_reasons


def test_volatility_regime_watchlist_fails_closed_on_unsupported_symbol():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        validate_volatility_regime_watchlist,
    )

    report = validate_volatility_regime_watchlist(
        _records(
            [100.0, 100.1, 100.0, 100.05, 100.0, 100.1, 102.5],
            [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
            symbol="DOGE/USDT",
        ),
        compression_window=5,
        expansion_window=1,
        min_observations=7,
        supported_symbols=("BTC/USDT",),
    )

    assert report.approved is False
    assert "unsupported_symbol" in report.blocked_reasons


def test_volatility_regime_watchlist_fails_closed_on_duplicate_market_candle_timestamp():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        validate_volatility_regime_watchlist,
    )

    records = list(
        _records(
            [100.0, 100.1, 100.0, 100.05, 100.0, 100.1, 102.5],
            [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
        )
    )
    duplicate = (
        _candle(6, 101.0, 1800.0)
        .model_copy(update={"source": "coinbase_public", "venue": "coinbase"})
        .to_source_record()
        .model_dump(mode="json")
    )
    records.append(duplicate)

    report = validate_volatility_regime_watchlist(
        records,
        compression_window=5,
        expansion_window=1,
        min_observations=7,
    )

    assert report.approved is False
    assert "duplicate_market_candle_timestamp" in report.blocked_reasons


def test_volatility_regime_watchlist_fails_closed_on_non_positive_expansion_price():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        STRATEGY_FAMILY,
        validate_volatility_regime_watchlist,
    )

    records = _records(
        [100.0, 100.1, 100.0, 100.05, 100.0, 0.0, 102.5],
        [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
    )

    direct = validate_volatility_regime_watchlist(
        records,
        compression_window=5,
        expansion_window=1,
        min_observations=7,
    )
    registry = default_strategy_registry(current_capital_usd=300.0)
    via_registry = registry.validate(
        StrategyValidationRequest(
            strategy_family=STRATEGY_FAMILY,
            records=records,
            current_capital_usd=300.0,
            parameters={
                "compression_window": 5,
                "expansion_window": 1,
                "min_observations": 7,
            },
        )
    )

    assert direct.approved is False
    assert "non_positive_price" in direct.blocked_reasons
    assert via_registry.approved is False
    assert "non_positive_price" in via_registry.blocked_reasons


def test_volatility_regime_watchlist_fails_closed_on_non_positive_compression_price():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
        STRATEGY_FAMILY,
        validate_volatility_regime_watchlist,
    )

    records = _records(
        [100.0, 100.1, 0.0, 100.05, 100.0, 100.1, 102.5],
        [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
    )

    direct = validate_volatility_regime_watchlist(
        records,
        compression_window=5,
        expansion_window=1,
        min_observations=7,
    )
    via_registry = default_strategy_registry(current_capital_usd=300.0).validate(
        StrategyValidationRequest(
            strategy_family=STRATEGY_FAMILY,
            records=records,
            current_capital_usd=300.0,
            parameters={
                "compression_window": 5,
                "expansion_window": 1,
                "min_observations": 7,
            },
        )
    )

    assert direct.approved is False
    assert "non_positive_price" in direct.blocked_reasons
    assert via_registry.approved is False
    assert "non_positive_price" in via_registry.blocked_reasons


def test_volatility_regime_watchlist_is_not_routed_to_paper_simulation():
    from crypto_alpha_agent.strategy.volatility_regime_watchlist import STRATEGY_FAMILY

    registry = default_strategy_registry(current_capital_usd=300.0)
    validation = registry.validate(
        StrategyValidationRequest(
            strategy_family=STRATEGY_FAMILY,
            records=_records(
                [100.0, 100.1, 100.0, 100.05, 100.0, 100.1, 102.5],
                [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
            ),
            current_capital_usd=300.0,
            parameters={
                "compression_window": 5,
                "expansion_window": 1,
                "min_observations": 7,
                "max_age_hours": 240.0,
                "now": "2026-05-17T06:00:00+00:00",
            },
        )
    )
    paper = registry.run_paper(
        StrategyPaperRequest(
            strategy_family=STRATEGY_FAMILY,
            records=_records(
                [100.0, 100.1, 100.0, 100.05, 100.0, 100.1, 102.5],
                [900.0, 920.0, 910.0, 930.0, 920.0, 950.0, 1400.0],
            ),
            current_capital_usd=300.0,
            notional_usd=0.0,
        )
    )

    assert validation.approved is True
    assert paper.status == "unsupported"
    assert paper.supports_paper_simulation is False
    assert paper.blocked_reasons == ("paper_simulation_not_supported",)
