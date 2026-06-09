from __future__ import annotations

from typing import Literal

UniversePreset = Literal["liquid-usdm-top20"]

LIQUID_USDM_TOP20_SYMBOLS: tuple[str, ...] = (
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "BCH/USDT",
    "DOT/USDT",
    "TRX/USDT",
    "NEAR/USDT",
    "AAVE/USDT",
    "UNI/USDT",
    "ETC/USDT",
    "FIL/USDT",
    "ATOM/USDT",
    "OP/USDT",
)

_PRESETS: dict[str, tuple[str, ...]] = {
    "liquid-usdm-top20": LIQUID_USDM_TOP20_SYMBOLS,
}


def resolve_universe_symbols(
    symbols: list[str] | tuple[str, ...] | None,
    *,
    universe_preset: str | None = None,
    max_symbols: int | None = None,
) -> list[str]:
    if max_symbols is not None and max_symbols <= 0:
        raise ValueError("max_symbols must be a positive integer")

    resolved: list[str] = []
    seen_exchange_symbols: set[str] = set()

    for symbol in symbols or ():
        _append_symbol(resolved, seen_exchange_symbols, symbol)

    if universe_preset is not None:
        preset_symbols = _PRESETS.get(universe_preset)
        if preset_symbols is None:
            raise ValueError(f"unknown universe preset: {universe_preset}")
        for symbol in preset_symbols:
            _append_symbol(resolved, seen_exchange_symbols, symbol)
            if max_symbols is not None and len(resolved) >= max_symbols:
                break

    if max_symbols is not None:
        resolved = resolved[:max_symbols]

    return resolved


def _append_symbol(
    resolved: list[str],
    seen_exchange_symbols: set[str],
    raw_symbol: str,
) -> None:
    symbol = _normalize_symbol(raw_symbol)
    exchange_symbol = _exchange_symbol(symbol)
    if exchange_symbol in seen_exchange_symbols:
        return
    seen_exchange_symbols.add(exchange_symbol)
    resolved.append(symbol)


def _normalize_symbol(raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper().split(":", maxsplit=1)[0]
    if "/" in symbol:
        base, quote = symbol.split("/", maxsplit=1)
        return f"{base}/{quote}"
    if symbol.endswith("USDT") and len(symbol) > 4:
        return f"{symbol[:-4]}/USDT"
    return symbol


def _exchange_symbol(symbol: str) -> str:
    return symbol.replace("/", "")
