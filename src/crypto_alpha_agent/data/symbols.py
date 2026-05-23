from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

ExchangeInstrumentType = Literal["spot", "perpetual"]
InstrumentType = Literal["spot", "perpetual", "dex_token"]

_KNOWN_COMPACT_QUOTES = (
    "FDUSD",
    "USDT",
    "USDC",
    "BUSD",
    "TUSD",
    "USDP",
    "USD",
    "BTC",
    "ETH",
    "EUR",
)


class NormalizedSymbol(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    canonical: str = Field(min_length=1)
    base_asset: str | None = None
    quote_asset: str | None = None
    settlement_asset: str | None = None
    instrument_type: InstrumentType
    venue: str | None = None
    raw_symbol: str = Field(min_length=1)


def normalize_exchange_symbol(
    raw_symbol: str,
    *,
    venue: str | None = None,
    instrument_type: ExchangeInstrumentType | None = None,
) -> NormalizedSymbol:
    symbol = _required_text(raw_symbol, "raw_symbol")
    normalized_venue = _optional_text(venue, lower=True)
    requested_type = _optional_exchange_instrument_type(instrument_type)
    base_asset, quote_asset, settlement_asset, inferred_type = _parse_exchange_symbol(
        symbol,
        venue=normalized_venue,
    )
    normalized_type = requested_type or inferred_type
    if normalized_type == "perpetual" and settlement_asset is None:
        settlement_asset = quote_asset

    canonical = f"{base_asset}/{quote_asset}"
    if settlement_asset is not None:
        canonical = f"{canonical}:{settlement_asset}"

    return NormalizedSymbol(
        canonical=canonical,
        base_asset=base_asset,
        quote_asset=quote_asset,
        settlement_asset=settlement_asset,
        instrument_type=normalized_type,
        venue=normalized_venue,
        raw_symbol=symbol,
    )


def normalize_dex_identifier(chain: str, address: str) -> NormalizedSymbol:
    normalized_chain = _required_text(chain, "chain").lower()
    raw_address = _required_text(address, "address")
    normalized_address = raw_address.lower()

    return NormalizedSymbol(
        canonical=f"{normalized_chain}:{normalized_address}",
        base_asset=normalized_address,
        quote_asset=None,
        settlement_asset=None,
        instrument_type="dex_token",
        venue=normalized_chain,
        raw_symbol=raw_address,
    )


def _parse_exchange_symbol(
    symbol: str,
    *,
    venue: str | None,
) -> tuple[str, str, str | None, ExchangeInstrumentType]:
    normalized = symbol.upper()
    if "/" in normalized:
        base_asset, quote_asset, settlement_asset = _parse_slash_symbol(normalized)
        inferred_type: ExchangeInstrumentType = "perpetual" if settlement_asset else "spot"
        return base_asset, quote_asset, settlement_asset, inferred_type
    if venue == "okx" and normalized.endswith("-SWAP"):
        return _parse_okx_swap_symbol(normalized)
    base_asset, quote_asset = _parse_compact_symbol(normalized)
    return base_asset, quote_asset, None, "spot"


def _parse_slash_symbol(symbol: str) -> tuple[str, str, str | None]:
    market_symbol, settlement_asset = _split_settlement(symbol)
    parts = market_symbol.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Unsupported exchange symbol format: {symbol}")
    return parts[0], parts[1], settlement_asset


def _parse_okx_swap_symbol(symbol: str) -> tuple[str, str, str, ExchangeInstrumentType]:
    parts = symbol.split("-")
    if len(parts) != 3 or parts[2] != "SWAP" or not parts[0] or not parts[1]:
        raise ValueError(f"Unsupported OKX swap symbol format: {symbol}")
    return parts[0], parts[1], parts[1], "perpetual"


def _parse_compact_symbol(symbol: str) -> tuple[str, str]:
    for quote_asset in _KNOWN_COMPACT_QUOTES:
        if symbol.endswith(quote_asset) and len(symbol) > len(quote_asset):
            return symbol[: -len(quote_asset)], quote_asset
    raise ValueError(f"Unsupported compact exchange symbol format: {symbol}")


def _split_settlement(symbol: str) -> tuple[str, str | None]:
    if ":" not in symbol:
        return symbol, None
    market_symbol, settlement_asset = symbol.split(":", maxsplit=1)
    if not market_symbol or not settlement_asset:
        raise ValueError(f"Unsupported settled exchange symbol format: {symbol}")
    return market_symbol, settlement_asset


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _optional_text(value: str | None, *, lower: bool = False) -> str | None:
    if value is None:
        return None
    normalized = _required_text(value, "venue")
    if lower:
        return normalized.lower()
    return normalized


def _optional_exchange_instrument_type(value: str | None) -> ExchangeInstrumentType | None:
    if value is None:
        return None
    normalized = _required_text(value, "instrument_type").lower()
    if normalized not in {"spot", "perpetual"}:
        raise ValueError("instrument_type must be spot or perpetual")
    return cast(ExchangeInstrumentType, normalized)


__all__ = [
    "NormalizedSymbol",
    "normalize_dex_identifier",
    "normalize_exchange_symbol",
]
