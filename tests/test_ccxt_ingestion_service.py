from __future__ import annotations

from datetime import UTC, datetime
import json

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.ingestion import (
    ingest_ccxt_funding_rate_history,
    ingest_ccxt_ohlcv,
)
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


class FakeCcxtCollector:
    def __init__(self):
        self.ohlcv_calls = []
        self.funding_calls = []

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
        self.ohlcv_calls.append((symbol, timeframe, since, limit, params))
        return [
            MarketCandle(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                timeframe=timeframe,
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000.0,
            )
        ]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None, params=None):
        self.funding_calls.append((symbol, since, limit, params))
        return [
            FundingRateRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                funding_rate=0.0007,
            )
        ]


def test_ingest_ccxt_ohlcv_writes_market_candles(tmp_path):
    db_path = tmp_path / "research.sqlite"
    collector = FakeCcxtCollector()

    summary = ingest_ccxt_ohlcv(
        db_path,
        symbol="BTC/USDT",
        timeframe="1h",
        limit=1,
        allow_network=True,
        collector=collector,
    )

    records = ResearchDataStore(db_path).load_records(record_type="market_candle", source="ccxt")
    assert summary.source == "ccxt"
    assert summary.feed == "ohlcv"
    assert summary.records_written == 1
    assert records[0].payload["symbol"] == "BTC/USDT"
    assert collector.ohlcv_calls == [("BTC/USDT", "1h", None, 1, None)]


def test_ingest_ccxt_funding_writes_funding_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    collector = FakeCcxtCollector()

    summary = ingest_ccxt_funding_rate_history(
        db_path,
        symbol="BTC/USDT:USDT",
        limit=1,
        allow_network=True,
        collector=collector,
    )

    records = ResearchDataStore(db_path).load_records(record_type="funding_rate", source="ccxt")
    assert summary.feed == "funding_rate_history"
    assert summary.records_written == 1
    assert records[0].payload["funding_rate"] == 0.0007


def test_ccxt_ingestion_requires_explicit_network_gate(tmp_path):
    collector = FakeCcxtCollector()

    try:
        ingest_ccxt_ohlcv(tmp_path / "research.sqlite", symbol="BTC/USDT", timeframe="1h", collector=collector)
    except ValueError as exc:
        assert "allow_network" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_ingest_cli_runs_ccxt_ohlcv_with_network_gate(capsys, tmp_path, monkeypatch):
    db_path = tmp_path / "research.sqlite"

    class PatchedCollector(FakeCcxtCollector):
        pass

    monkeypatch.setattr(
        "crypto_alpha_agent.data.ingestion.CcxtResearchCollector",
        lambda exchange_id="binance": PatchedCollector(),
    )

    exit_code = main(
        [
            "ingest",
            "--db",
            str(db_path),
            "--source",
            "ccxt",
            "--allow-network",
            "--ccxt-feed",
            "ohlcv",
            "--symbol",
            "ETH/USDT",
            "--timeframe",
            "1h",
            "--limit",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "ingest"
    assert payload["ingestion"]["feed"] == "ohlcv"
    assert payload["uses_real_capital"] is False
    assert ResearchDataStore(db_path).load_records(record_type="market_candle", source="ccxt")
