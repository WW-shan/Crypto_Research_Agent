from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

import ccxt
from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.tools.http import SourceHealth


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
    max_attempts: int = 3,
    timeout_seconds: float = 30.0,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    snapshot, _health = fetch_cex_snapshot_with_health(
        exchange_id,
        symbols,
        exchange=exchange,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        backoff_seconds=backoff_seconds,
        sleep=sleep,
    )
    return snapshot


def fetch_cex_snapshot_with_health(
    exchange_id: str,
    symbols: list[str],
    *,
    exchange: Any | None = None,
    max_attempts: int = 3,
    timeout_seconds: float = 30.0,
    backoff_seconds: float = 0.5,
    sleep: Callable[[float], None] | None = None,
) -> tuple[dict[str, dict[str, dict[str, Any]]], SourceHealth]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be non-negative")

    client = exchange or getattr(ccxt, exchange_id)()
    _set_exchange_timeout(client, timeout_seconds)

    nap = sleep or time.sleep
    last_failure: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            tickers = {symbol: client.fetch_ticker(symbol) for symbol in symbols}
            health = SourceHealth(source="cex", attempts=attempt, success=True)
            return {exchange_id: tickers}, health
        except Exception as exc:
            last_failure = str(exc) or exc.__class__.__name__
            if attempt < max_attempts and backoff_seconds > 0:
                nap(backoff_seconds)

    health = SourceHealth(source="cex", attempts=max_attempts, success=False, failure=last_failure)
    raise RuntimeError(
        f"cex request failed after {health.attempts} attempts: {health.failure}; "
        f"health={health.model_dump()}"
    )


def _set_exchange_timeout(client: Any, timeout_seconds: float) -> None:
    try:
        setattr(client, "timeout", int(timeout_seconds * 1000))
    except Exception:
        return


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def normalize_cex_snapshot(raw: dict[str, Any]) -> CexMarketSnapshot:
    if not isinstance(raw, dict):
        raise ValueError("CEX snapshot raw payload must be an object")

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
