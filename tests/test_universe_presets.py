import pytest


def test_resolve_liquid_universe_preset_preserves_explicit_priority_and_cap():
    from crypto_alpha_agent.pipeline.universe_presets import resolve_universe_symbols

    symbols = resolve_universe_symbols(
        ["BTC/USDT"],
        universe_preset="liquid-usdm-top20",
        max_symbols=3,
    )

    assert symbols == ["BTC/USDT", "ETH/USDT", "BNB/USDT"]


def test_resolve_liquid_universe_preset_dedupes_by_exchange_symbol():
    from crypto_alpha_agent.pipeline.universe_presets import resolve_universe_symbols

    symbols = resolve_universe_symbols(
        ["BTCUSDT", "BTC/USDT", "ETH/USDT"],
        universe_preset="liquid-usdm-top20",
        max_symbols=4,
    )

    assert symbols == ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]


def test_resolve_liquid_universe_preset_rejects_unknown_preset():
    from crypto_alpha_agent.pipeline.universe_presets import resolve_universe_symbols

    with pytest.raises(ValueError, match="unknown universe preset"):
        resolve_universe_symbols(["BTC/USDT"], universe_preset="unknown")


def test_resolve_liquid_universe_preset_rejects_non_positive_cap():
    from crypto_alpha_agent.pipeline.universe_presets import resolve_universe_symbols

    with pytest.raises(ValueError, match="max_symbols"):
        resolve_universe_symbols(
            ["BTC/USDT"],
            universe_preset="liquid-usdm-top20",
            max_symbols=0,
        )
