from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.binance_public import BinancePublicDataClient
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
