from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


class CandleBar(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    source: str
    venue: str
    symbol: str
    timestamp: datetime
    timeframe: str
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: float = Field(ge=0)


def _require_existing_file(db_path: str | Path) -> Path:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"database path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"database path is not a file: {path}")
    return path


def _require_timezone_aware(name: str, value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{name} must be timezone-aware")


def load_candle_history(
    db_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    source: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
) -> list[CandleBar]:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than 0")
    _require_timezone_aware("start", start)
    _require_timezone_aware("end", end)

    store = ResearchDataStore(_require_existing_file(db_path))
    records = store.load_records(record_type="market_candle", source=source)
    bars: list[CandleBar] = []

    for record in records:
        candle = MarketCandle.model_validate_json(json.dumps(record.payload))
        if source is not None and (candle.source != record.source or candle.source != source):
            continue
        if candle.symbol != symbol or candle.timeframe != timeframe:
            continue
        if start is not None and candle.timestamp < start:
            continue
        if end is not None and candle.timestamp >= end:
            continue

        bars.append(
            CandleBar(
                source=candle.source,
                venue=candle.venue,
                symbol=candle.symbol,
                timestamp=candle.timestamp,
                timeframe=candle.timeframe,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
        )

    bars.sort(key=lambda bar: (bar.timestamp, bar.source, bar.venue, bar.symbol))
    if limit is not None:
        bars = bars[-limit:]
    return bars
