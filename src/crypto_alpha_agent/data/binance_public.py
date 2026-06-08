from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import BytesIO, StringIO
from zipfile import ZipFile

import requests

from crypto_alpha_agent.data.models import DataSuitability, MarketCandle


class BinancePublicDataClient:
    def __init__(
        self,
        base_url: str = "https://data.binance.vision",
        session=None,
        timeout_seconds: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def build_monthly_spot_klines_url(
        self, symbol: str, interval: str, year: int, month: int
    ) -> str:
        binance_symbol = _to_binance_symbol(symbol)
        return (
            f"{self.base_url}/data/spot/monthly/klines/"
            f"{binance_symbol}/{interval}/{binance_symbol}-{interval}-{year}-{month:02d}.zip"
        )

    def build_monthly_um_futures_klines_url(
        self, symbol: str, interval: str, year: int, month: int
    ) -> str:
        binance_symbol = _to_binance_symbol(symbol)
        return (
            f"{self.base_url}/data/futures/um/monthly/klines/"
            f"{binance_symbol}/{interval}/{binance_symbol}-{interval}-{year}-{month:02d}.zip"
        )

    def download_monthly_spot_klines(
        self, symbol: str, interval: str, year: int, month: int
    ) -> list[MarketCandle]:
        url = self.build_monthly_spot_klines_url(symbol, interval, year, month)
        return self._download_monthly_klines(
            url=url,
            symbol=symbol,
            interval=interval,
            venue="binance",
        )

    def download_monthly_um_futures_klines(
        self, symbol: str, interval: str, year: int, month: int
    ) -> list[MarketCandle]:
        url = self.build_monthly_um_futures_klines_url(symbol, interval, year, month)
        return self._download_monthly_klines(
            url=url,
            symbol=symbol,
            interval=interval,
            venue="binance_usdm",
        )

    def _download_monthly_klines(
        self,
        *,
        url: str,
        symbol: str,
        interval: str,
        venue: str,
    ) -> list[MarketCandle]:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()

        normalized_symbol = _normalize_symbol(symbol)
        candles: list[MarketCandle] = []
        with ZipFile(BytesIO(response.content)) as archive:
            for name in archive.namelist():
                if not name.endswith(".csv"):
                    continue
                text = archive.read(name).decode("utf-8")
                for row in csv.reader(StringIO(text)):
                    if not row or _is_kline_header(row):
                        continue
                    candles.append(
                        _row_to_market_candle(
                            row,
                            normalized_symbol,
                            interval,
                            name,
                            venue=venue,
                        )
                    )
        if not candles:
            raise ValueError(f"no market candles found in Binance Public Data archive: {url}")
        return candles


def _is_kline_header(row: list[str]) -> bool:
    return bool(row) and row[0].strip().lower() in {"open_time", "open time"}


def _row_to_market_candle(
    row: list[str],
    normalized_symbol: str,
    interval: str,
    archive_name: str,
    *,
    venue: str = "binance",
) -> MarketCandle:
    open_time, open_, high, low, close, volume = row[:6]
    return MarketCandle(
        source="binance_public",
        venue=venue,
        symbol=normalized_symbol,
        timestamp=_parse_binance_timestamp(open_time),
        timeframe=interval,
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(volume),
        suitability=DataSuitability(
            min_capital_usd=25.0,
            latency_dependency="low",
            rpc_dependency="none",
            execution_role="research_and_paper",
        ),
        raw={"archive_name": archive_name, "row": row},
    )


def _parse_binance_timestamp(value: str) -> datetime:
    timestamp = int(value)
    divisor = 1_000_000 if timestamp >= 10**15 else 1_000
    return datetime.fromtimestamp(timestamp / divisor, tz=UTC)


def _to_binance_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def _normalize_symbol(symbol: str) -> str:
    upper_symbol = symbol.upper()
    if "/" in upper_symbol:
        base, quote = upper_symbol.split("/", 1)
        return f"{base}/{quote}"

    for quote in ("FDUSD", "USDT", "USDC", "BUSD", "TUSD", "USD", "BTC", "ETH"):
        if upper_symbol.endswith(quote) and len(upper_symbol) > len(quote):
            return f"{upper_symbol[: -len(quote)]}/{quote}"
    return upper_symbol
