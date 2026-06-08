from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

from crypto_alpha_agent.data.binance_public import BinancePublicDataClient


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, content: bytes):
        self.content = content
        self.requested_urls = []

    def get(self, url, timeout):
        self.requested_urls.append(url)
        return FakeResponse(self.content)


def _zip_csv(name: str, text: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


def test_builds_monthly_um_futures_klines_url():
    client = BinancePublicDataClient()

    url = client.build_monthly_um_futures_klines_url("BTCUSDT", "1h", 2026, 5)

    assert url.endswith(
        "/data/futures/um/monthly/klines/BTCUSDT/1h/"
        "BTCUSDT-1h-2026-05.zip"
    )


def test_downloads_monthly_um_futures_klines_into_market_candles():
    csv_text = (
        "1747353600000,65000,65100,64900,65050,123.4,"
        "1747357199999,0,0,0,0,0\n"
    )
    session = FakeSession(_zip_csv("BTCUSDT-1h-2026-05.csv", csv_text))
    client = BinancePublicDataClient(session=session)

    candles = client.download_monthly_um_futures_klines("BTCUSDT", "1h", 2026, 5)

    assert session.requested_urls[0].endswith(
        "/data/futures/um/monthly/klines/BTCUSDT/1h/"
        "BTCUSDT-1h-2026-05.zip"
    )
    assert candles[0].source == "binance_public"
    assert candles[0].venue == "binance_usdm"
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)
    assert candles[0].timeframe == "1h"
    assert candles[0].open == 65000.0
    assert candles[0].high == 65100.0
    assert candles[0].low == 64900.0
    assert candles[0].close == 65050.0
    assert candles[0].volume == 123.4
    assert candles[0].suitability.rpc_dependency == "none"
    assert candles[0].suitability.execution_role == "research_and_paper"
    source_record = candles[0].to_source_record()
    assert source_record.payload["uses_real_capital"] is False
    assert source_record.payload["live_order_routing"] is False


def test_downloads_monthly_um_futures_klines_skips_csv_header():
    csv_text = (
        "open_time,open,high,low,close,volume,close_time,quote_volume,count,"
        "taker_buy_volume,taker_buy_quote_volume,ignore\n"
        "1747353600000,65000,65100,64900,65050,123.4,"
        "1747357199999,0,0,0,0,0\n"
    )
    session = FakeSession(_zip_csv("BTCUSDT-1h-2026-05.csv", csv_text))
    client = BinancePublicDataClient(session=session)

    candles = client.download_monthly_um_futures_klines("BTCUSDT", "1h", 2026, 5)

    assert len(candles) == 1
    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)
    assert candles[0].close == 65050.0


def test_empty_um_futures_archive_raises_clear_error():
    session = FakeSession(_zip_csv("README.txt", "no csv rows here"))
    client = BinancePublicDataClient(session=session)

    try:
        client.download_monthly_um_futures_klines("BTCUSDT", "1h", 2026, 5)
    except ValueError as exc:
        assert "no market candles" in str(exc)
    else:
        raise AssertionError("expected empty archive to fail closed")
