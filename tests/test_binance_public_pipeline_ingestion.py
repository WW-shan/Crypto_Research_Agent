from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import DataSuitability, MarketCandle
from crypto_alpha_agent.data.ingestion import IngestionSummary, ingest_binance_public_month
from crypto_alpha_agent.data.store import ResearchDataStore


class FakeBinancePublicDataClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, int]] = []

    def download_monthly_spot_klines(
        self, symbol: str, interval: str, year: int, month: int
    ) -> list[MarketCandle]:
        self.calls.append((symbol, interval, year, month))
        return [
            MarketCandle(
                source="binance_public",
                venue="binance",
                symbol="BTC/USDT",
                timestamp=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
                timeframe=interval,
                open=65000.0,
                high=65100.0,
                low=64900.0,
                close=65050.0,
                volume=123.4,
                suitability=DataSuitability(
                    min_capital_usd=25.0,
                    latency_dependency="low",
                    rpc_dependency="none",
                    execution_role="research_and_paper",
                ),
                raw={"row": 1},
            ),
            MarketCandle(
                source="binance_public",
                venue="binance",
                symbol="BTC/USDT",
                timestamp=datetime(2026, 5, 1, 1, 0, tzinfo=UTC),
                timeframe=interval,
                open=65050.0,
                high=65200.0,
                low=65000.0,
                close=65100.0,
                volume=234.5,
                suitability=DataSuitability(
                    min_capital_usd=25.0,
                    latency_dependency="low",
                    rpc_dependency="none",
                    execution_role="research_and_paper",
                ),
                raw={"row": 2},
            ),
        ]


def test_binance_ingestion_requires_network_gate(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinancePublicDataClient()

    with pytest.raises(ValueError, match="allow_network"):
        ingest_binance_public_month(
            db_path,
            symbol="BTC/USDT",
            interval="1h",
            year=2026,
            month=5,
            allow_network=False,
            client=client,
        )

    assert client.calls == []
    assert not db_path.exists()


def test_binance_ingestion_persists_candles_with_fake_client(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinancePublicDataClient()

    summary = ingest_binance_public_month(
        db_path,
        symbol="BTC/USDT",
        interval="1h",
        year=2026,
        month=5,
        allow_network=True,
        client=client,
    )

    assert isinstance(summary, IngestionSummary)
    assert summary.source == "binance_public"
    assert summary.records_fetched == 2
    assert summary.records_written == 2
    assert summary.uses_real_capital is False
    assert summary.live_order_routing is False
    assert summary.notes == ["research_and_paper_validation_only"]

    store = ResearchDataStore(db_path)
    records = store.load_records(record_type="market_candle")

    assert [record.payload["symbol"] for record in records] == ["BTC/USDT", "BTC/USDT"]
    assert len(records) == 2
