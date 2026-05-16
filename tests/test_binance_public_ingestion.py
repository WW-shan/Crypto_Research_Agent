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


def test_downloads_monthly_klines_into_market_candles():
    csv_text = "1747353600000,65000,65100,64900,65050,123.4,1747357199999,0,0,0,0,0\n"
    session = FakeSession(_zip_csv("BTCUSDT-1h-2026-05.csv", csv_text))
    client = BinancePublicDataClient(session=session)

    candles = client.download_monthly_spot_klines("BTCUSDT", "1h", 2026, 5)

    assert session.requested_urls[0].endswith(
        "/data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2026-05.zip"
    )
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)
    assert candles[0].close == 65050.0
    assert candles[0].suitability.rpc_dependency == "none"


def test_parses_microsecond_open_time_after_2025():
    csv_text = "1747353600000000,65000,65100,64900,65050,123.4,1747357199999999,0,0,0,0,0\n"
    session = FakeSession(_zip_csv("BTCUSDT-1h-2026-05.csv", csv_text))
    client = BinancePublicDataClient(session=session)

    candles = client.download_monthly_spot_klines("BTCUSDT", "1h", 2026, 5)

    assert candles[0].timestamp == datetime.fromtimestamp(1747353600, tz=UTC)


def test_normalizes_stablecoin_quote_suffixes_before_usd_suffix():
    csv_text = "1747353600000,65000,65100,64900,65050,123.4,1747357199999,0,0,0,0,0\n"
    session = FakeSession(_zip_csv("DOGEFDUSD-1h-2026-05.csv", csv_text))
    client = BinancePublicDataClient(session=session)

    candles = client.download_monthly_spot_klines("DOGEFDUSD", "1h", 2026, 5)

    assert candles[0].symbol == "DOGE/FDUSD"
