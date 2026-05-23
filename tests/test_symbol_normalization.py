from __future__ import annotations

from crypto_alpha_agent.data.symbols import (
    normalize_dex_identifier,
    normalize_exchange_symbol,
)


def test_normalizes_spot_and_perpetual_exchange_symbols():
    assert normalize_exchange_symbol("BTCUSDT").canonical == "BTC/USDT"
    assert normalize_exchange_symbol("BTC/USDT:USDT").canonical == "BTC/USDT:USDT"
    assert normalize_exchange_symbol("BTC-USDT-SWAP", venue="okx").canonical == "BTC/USDT:USDT"
    assert normalize_exchange_symbol("BTCUSD", instrument_type="perpetual").canonical == "BTC/USD:USD"


def test_dex_identifier_keeps_chain_and_address_scope():
    token = normalize_dex_identifier("ethereum", "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")

    assert token.canonical == "ethereum:0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert token.instrument_type == "dex_token"
