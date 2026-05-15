from __future__ import annotations

from typing import Any, Literal

import ccxt
from pydantic import BaseModel, ConfigDict, Field


class CexMarketSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["cex"] = "cex"
    venue: str
    symbol: str
    asset: str
    best_bid: float = Field(ge=0)
    best_ask: float = Field(ge=0)
    raw: dict[str, Any]


def fetch_cex_snapshot(
    exchange_id: str,
    symbols: list[str],
    *,
    exchange: Any | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    client = exchange or getattr(ccxt, exchange_id)()
    tickers = {symbol: client.fetch_ticker(symbol) for symbol in symbols}
    return {exchange_id: tickers}


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def normalize_cex_snapshot(raw: dict[str, Any]) -> CexMarketSnapshot:
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for venue, markets in raw.items():
        if not isinstance(markets, dict):
            raise ValueError("CEX snapshot must contain venues with market quote objects")
        for symbol, ticker in markets.items():
            if not isinstance(ticker, dict):
                raise ValueError("CEX snapshot must contain venues with market quote objects")
            if not _is_number(ticker.get("bid")) or not _is_number(ticker.get("ask")):
                raise ValueError(f"CEX quote for {venue} {symbol} must contain numeric bid and ask")
            candidates.append((str(venue), str(symbol), ticker))

    if not candidates:
        raise ValueError("CEX snapshot does not contain a market with bid and ask")

    venue, symbol, ticker = max(candidates, key=lambda item: float(item[2]["bid"]))
    asset = symbol.split("/", maxsplit=1)[0]
    return CexMarketSnapshot(
        venue=venue,
        symbol=symbol,
        asset=asset,
        best_bid=float(ticker["bid"]),
        best_ask=float(ticker["ask"]),
        raw=raw,
    )
