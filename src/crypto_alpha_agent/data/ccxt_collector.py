from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import ccxt

from crypto_alpha_agent.data.models import (
    DataSuitability,
    FundingRateRecord,
    MarketCandle,
)


class CcxtResearchCollector:
    def __init__(self, exchange=None, exchange_id: str = "binance"):
        self.exchange = exchange or getattr(ccxt, exchange_id)()

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[MarketCandle]:
        if params is None:
            rows = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        else:
            rows = self.exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=since,
                limit=limit,
                params=params,
            )
        return [
            MarketCandle(
                source="ccxt",
                venue=self.exchange.id,
                symbol=symbol,
                timestamp=_timestamp_ms_to_datetime(row[0]),
                timeframe=timeframe,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                suitability=_research_suitability(),
                raw={"row": row},
            )
            for row in rows
        ]

    def fetch_funding_rate_history(
        self,
        symbol: str,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[FundingRateRecord]:
        fetch_history = getattr(self.exchange, "fetch_funding_rate_history", None)
        if not callable(fetch_history):
            raise NotImplementedError(
                f"{self.exchange.id} does not support fetch_funding_rate_history"
            )

        if params is None:
            payloads = fetch_history(symbol, since=since, limit=limit)
        else:
            payloads = fetch_history(symbol, since=since, limit=limit, params=params)
        return [
            FundingRateRecord(
                source="ccxt",
                venue=self.exchange.id,
                symbol=payload.get("symbol", symbol),
                timestamp=_timestamp_ms_to_datetime(payload["timestamp"]),
                funding_rate=float(payload["fundingRate"]),
                next_funding_at=_optional_timestamp_ms_to_datetime(
                    payload.get("nextFundingTimestamp")
                ),
                suitability=_research_suitability(),
                raw=payload,
            )
            for payload in payloads
        ]


def _research_suitability() -> DataSuitability:
    return DataSuitability(
        min_capital_usd=25.0,
        latency_dependency="low",
        rpc_dependency="none",
        execution_role="research_and_paper",
    )


def _timestamp_ms_to_datetime(timestamp: int | float) -> datetime:
    return datetime.fromtimestamp(timestamp / 1_000, tz=UTC)


def _optional_timestamp_ms_to_datetime(timestamp: Any) -> datetime | None:
    if timestamp is None:
        return None
    return _timestamp_ms_to_datetime(timestamp)
