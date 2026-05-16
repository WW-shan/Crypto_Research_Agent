from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.ccxt_collector import CcxtResearchCollector
from crypto_alpha_agent.data.binance_public import BinancePublicDataClient
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore


class IngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    db_path: str
    symbols: list[str]
    timeframe: str
    year: int
    month: int
    records_fetched: int
    records_written: int
    network_allowed: bool
    uses_real_capital: bool
    live_order_routing: bool
    notes: list[str]


class CcxtIngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    db_path: str
    feed: Literal["ohlcv", "funding_rate_history"]
    symbols: list[str]
    records_fetched: int
    records_written: int
    network_allowed: bool
    uses_real_capital: bool
    live_order_routing: bool


def ingest_binance_public_month(
    db_path: str | Path,
    *,
    symbol: str,
    interval: str,
    year: int,
    month: int,
    allow_network: bool = False,
    client=None,
) -> IngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for Binance Public Data ingestion")

    binance_client = client or BinancePublicDataClient()
    candles = binance_client.download_monthly_spot_klines(symbol, interval, year, month)
    records = [candle.to_source_record() for candle in candles]
    records_written = ResearchDataStore(db_path).upsert_records(records)

    return IngestionSummary(
        source="binance_public",
        db_path=str(db_path),
        symbols=[symbol],
        timeframe=interval,
        year=year,
        month=month,
        records_fetched=len(candles),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
        notes=["research_and_paper_validation_only"],
    )


def ingest_ccxt_ohlcv(
    db_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector: Any | None = None,
) -> CcxtIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for CCXT ingestion")

    ccxt_collector = collector or CcxtResearchCollector(exchange_id=exchange_id)
    candles = ccxt_collector.fetch_ohlcv(
        symbol,
        timeframe,
        since=since,
        limit=limit,
        params=None,
    )
    records = [_ccxt_ohlcv_to_source_record(candle) for candle in candles]
    records_written = ResearchDataStore(db_path).upsert_records(records)
    return CcxtIngestionSummary(
        source="ccxt",
        db_path=str(db_path),
        feed="ohlcv",
        symbols=[symbol],
        records_fetched=len(candles),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def ingest_ccxt_funding_rate_history(
    db_path: str | Path,
    *,
    symbol: str,
    since: int | None = None,
    limit: int | None = None,
    allow_network: bool = False,
    exchange_id: str = "binance",
    collector: Any | None = None,
) -> CcxtIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for CCXT ingestion")

    ccxt_collector = collector or CcxtResearchCollector(exchange_id=exchange_id)
    funding_history = ccxt_collector.fetch_funding_rate_history(
        symbol,
        since=since,
        limit=limit,
        params=None,
    )
    records = [_funding_rate_to_source_record(record) for record in funding_history]
    records_written = ResearchDataStore(db_path).upsert_records(records)
    return CcxtIngestionSummary(
        source="ccxt",
        db_path=str(db_path),
        feed="funding_rate_history",
        symbols=[symbol],
        records_fetched=len(funding_history),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def _ccxt_ohlcv_to_source_record(candle: MarketCandle) -> SourceRecord:
    safe_venue = _ccxt_safe_component(candle.venue)
    safe_symbol = _ccxt_safe_symbol(candle.symbol)
    safe_timeframe = _ccxt_safe_component(candle.timeframe)
    return SourceRecord(
        record_id=(
            f"{candle.source}:{safe_venue}:{safe_symbol}:ohlcv:"
            f"{safe_timeframe}:{candle.timestamp.isoformat()}"
        ),
        source=candle.source,
        record_type="market_candle",
        observed_at=candle.timestamp,
        payload=candle.model_dump(mode="json"),
    )


def _funding_rate_to_source_record(record: FundingRateRecord) -> SourceRecord:
    safe_venue = _ccxt_safe_component(record.venue)
    safe_symbol = _ccxt_safe_symbol(record.symbol)
    return SourceRecord(
        record_id=f"{record.source}:{safe_venue}:{safe_symbol}:funding:{record.timestamp.isoformat()}",
        source=record.source,
        record_type="funding_rate",
        observed_at=record.timestamp,
        payload=record.model_dump(mode="json"),
    )


def _ccxt_safe_component(value: str) -> str:
    return value.strip().lower().replace("/", "-").replace(":", "-")


def _ccxt_safe_symbol(symbol: str) -> str:
    return symbol.strip().replace("/", "").replace(":", "-").upper()
