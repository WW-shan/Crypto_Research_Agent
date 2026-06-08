from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import pytest

from crypto_alpha_agent.data.binance_public import BinancePublicDataClient
from crypto_alpha_agent.data.models import DataSuitability, MarketCandle
from crypto_alpha_agent.data.ingestion import (
    IngestionSummary,
    ingest_binance_public_month,
    ingest_binance_public_um_futures_month,
)
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

    def download_monthly_um_futures_klines(
        self, symbol: str, interval: str, year: int, month: int
    ) -> list[MarketCandle]:
        self.calls.append((symbol, interval, year, month))
        return [
            MarketCandle(
                source="binance_public",
                venue="binance_usdm",
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
                raw={"row": 1, "market": "um_futures"},
            )
        ]


class FailingBinancePublicDataClient:
    def download_monthly_um_futures_klines(
        self, symbol: str, interval: str, year: int, month: int
    ) -> list[MarketCandle]:
        raise ValueError("empty futures archive")


class FakePublicDataResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class FakePublicDataSession:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def get(self, url, timeout):
        return FakePublicDataResponse(self.content)


def _zip_csv(name: str, text: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


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


def test_binance_ingestion_filters_records_by_observed_window(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinancePublicDataClient()

    summary = ingest_binance_public_month(
        db_path,
        symbol="BTC/USDT",
        interval="1h",
        year=2026,
        month=5,
        allow_network=True,
        observed_at_start=datetime(2026, 5, 1, 1, tzinfo=UTC),
        observed_at_end=datetime(2026, 5, 1, 2, tzinfo=UTC),
        client=client,
    )

    records = ResearchDataStore(db_path).load_records(record_type="market_candle")

    assert summary.records_fetched == 2
    assert summary.records_written == 1
    assert [record.observed_at for record in records] == [
        datetime(2026, 5, 1, 1, tzinfo=UTC)
    ]


def test_binance_um_futures_ingestion_persists_candles_and_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinancePublicDataClient()

    summary = ingest_binance_public_um_futures_month(
        db_path,
        symbol="BTCUSDT",
        interval="1h",
        year=2026,
        month=5,
        allow_network=True,
        client=client,
    )

    store = ResearchDataStore(db_path)
    records = store.load_records(record_type="market_candle", source="binance_public")
    health = store.load_records(record_type="source_health", source="binance_public")

    assert isinstance(summary, IngestionSummary)
    assert summary.source == "binance_public"
    assert summary.symbols == ["BTCUSDT"]
    assert summary.records_fetched == 1
    assert summary.records_written == 1
    assert summary.uses_real_capital is False
    assert summary.live_order_routing is False
    assert records[0].payload["venue"] == "binance_usdm"
    assert records[0].payload["symbol"] == "BTC/USDT"
    assert records[0].payload["suitability"]["rpc_dependency"] == "none"
    assert records[0].payload["uses_real_capital"] is False
    assert records[0].payload["live_order_routing"] is False
    assert health[-1].payload["feed"] == "um_futures_ohlcv"
    assert health[-1].payload["success"] is True


def test_binance_spot_and_um_futures_candles_do_not_overwrite_each_other(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinancePublicDataClient()

    ingest_binance_public_month(
        db_path,
        symbol="BTCUSDT",
        interval="1h",
        year=2026,
        month=5,
        allow_network=True,
        client=client,
    )
    ingest_binance_public_um_futures_month(
        db_path,
        symbol="BTCUSDT",
        interval="1h",
        year=2026,
        month=5,
        allow_network=True,
        client=client,
    )

    records = ResearchDataStore(db_path).load_records(
        record_type="market_candle",
        source="binance_public",
    )

    assert len(records) == 3
    assert {record.payload["venue"] for record in records} == {
        "binance",
        "binance_usdm",
    }
    assert len({record.record_id for record in records}) == 3


def test_binance_um_futures_ingestion_requires_network_gate(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeBinancePublicDataClient()

    with pytest.raises(ValueError, match="allow_network"):
        ingest_binance_public_um_futures_month(
            db_path,
            symbol="BTCUSDT",
            interval="1h",
            year=2026,
            month=5,
            allow_network=False,
            client=client,
        )

    assert client.calls == []
    assert not db_path.exists()


def test_binance_um_futures_ingestion_writes_failure_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"

    with pytest.raises(ValueError, match="empty futures archive"):
        ingest_binance_public_um_futures_month(
            db_path,
            symbol="BTCUSDT",
            interval="1h",
            year=2026,
            month=5,
            allow_network=True,
            client=FailingBinancePublicDataClient(),
        )

    health = ResearchDataStore(db_path).load_records(
        record_type="source_health",
        source="binance_public",
    )
    assert health[-1].payload["feed"] == "um_futures_ohlcv"
    assert health[-1].payload["success"] is False
    assert health[-1].payload["records_fetched"] == 0
    assert health[-1].payload["records_written"] == 0


def test_binance_um_futures_ingestion_writes_failure_for_empty_archive(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = BinancePublicDataClient(
        session=FakePublicDataSession(_zip_csv("README.txt", "no csv rows here"))
    )

    with pytest.raises(ValueError, match="no market candles"):
        ingest_binance_public_um_futures_month(
            db_path,
            symbol="BTCUSDT",
            interval="1h",
            year=2026,
            month=5,
            allow_network=True,
            client=client,
        )

    health = ResearchDataStore(db_path).load_records(
        record_type="source_health",
        source="binance_public",
    )
    assert health[-1].payload["feed"] == "um_futures_ohlcv"
    assert health[-1].payload["success"] is False
    assert health[-1].payload["failure"]
