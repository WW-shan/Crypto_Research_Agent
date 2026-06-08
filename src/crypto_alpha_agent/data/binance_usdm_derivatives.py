from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import requests

from crypto_alpha_agent.data.models import (
    BasisRecord,
    LongShortRatioRecord,
    PremiumIndexKlineRecord,
    TakerBuySellVolumeRecord,
)

_PROXY_ENV_NAMES = (
    "CRYPTO_ALPHA_AGENT_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


class BinanceUsdmDerivativesClient:
    def __init__(
        self,
        base_url: str = "https://fapi.binance.com",
        session=None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def fetch_premium_index_klines(
        self,
        *,
        symbol: str,
        interval: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[PremiumIndexKlineRecord]:
        payload = self._get_json(
            "/fapi/v1/premiumIndexKlines",
            params=_clean_params(
                {
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms,
                }
            ),
        )
        return [
            _premium_index_kline_record(row, symbol=symbol, interval=interval)
            for row in _list_payload(payload, "/fapi/v1/premiumIndexKlines")
        ]

    def fetch_basis(
        self,
        *,
        pair: str,
        contract_type: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[BasisRecord]:
        payload = self._get_json(
            "/futures/data/basis",
            params=_clean_params(
                {
                    "pair": pair,
                    "contractType": contract_type,
                    "period": period,
                    "limit": limit,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms,
                }
            ),
        )
        return [
            _basis_record(
                row,
                fallback_pair=pair,
                contract_type=contract_type,
                period=period,
            )
            for row in _list_payload(payload, "/futures/data/basis")
        ]

    def fetch_global_long_short_account_ratio(
        self,
        *,
        symbol: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[LongShortRatioRecord]:
        payload = self._get_json(
            "/futures/data/globalLongShortAccountRatio",
            params=_clean_params(
                {
                    "symbol": symbol,
                    "period": period,
                    "limit": limit,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms,
                }
            ),
        )
        return [
            _long_short_ratio_record(row, fallback_symbol=symbol, period=period)
            for row in _list_payload(payload, "/futures/data/globalLongShortAccountRatio")
        ]

    def fetch_taker_buy_sell_volume(
        self,
        *,
        symbol: str,
        period: str,
        limit: int | None = None,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[TakerBuySellVolumeRecord]:
        payload = self._get_json(
            "/futures/data/takerlongshortRatio",
            params=_clean_params(
                {
                    "symbol": symbol,
                    "period": period,
                    "limit": limit,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms,
                }
            ),
        )
        return [
            _taker_buy_sell_volume_record(row, fallback_symbol=symbol, period=period)
            for row in _list_payload(payload, "/futures/data/takerlongshortRatio")
        ]

    def _get_json(self, path: str, *, params: dict[str, Any]) -> Any:
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=self.timeout_seconds,
            **_request_route_kwargs(),
        )
        response.raise_for_status()
        return response.json()


def _premium_index_kline_record(
    row: Any,
    *,
    symbol: str,
    interval: str,
) -> PremiumIndexKlineRecord:
    if not isinstance(row, list | tuple) or len(row) < 5:
        raise ValueError("premium index kline row must contain at least 5 fields")
    return PremiumIndexKlineRecord(
        source="binance_usdm",
        venue="binance",
        symbol=symbol,
        timestamp=_timestamp_ms_to_datetime(row[0]),
        interval=interval,
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        raw={"row": list(row)},
    )


def _basis_record(
    row: Any,
    *,
    fallback_pair: str,
    contract_type: str,
    period: str,
) -> BasisRecord:
    payload = _mapping_payload(row, "/futures/data/basis")
    return BasisRecord(
        source="binance_usdm",
        venue="binance",
        pair=str(payload.get("pair") or fallback_pair),
        contract_type=str(payload.get("contractType") or contract_type),
        period=period,
        timestamp=_timestamp_ms_to_datetime(payload["timestamp"]),
        index_price=_payload_float(payload, "indexPrice"),
        futures_price=_payload_float(payload, "futuresPrice"),
        basis=_payload_float(payload, "basis"),
        basis_rate=_payload_float(payload, "basisRate"),
        annualized_basis_rate=_payload_optional_float(payload, "annualizedBasisRate"),
        raw=payload,
    )


def _long_short_ratio_record(
    row: Any,
    *,
    fallback_symbol: str,
    period: str,
) -> LongShortRatioRecord:
    payload = _mapping_payload(row, "/futures/data/globalLongShortAccountRatio")
    return LongShortRatioRecord(
        source="binance_usdm",
        venue="binance",
        symbol=str(payload.get("symbol") or fallback_symbol),
        period=period,
        timestamp=_timestamp_ms_to_datetime(payload["timestamp"]),
        long_short_ratio=_payload_float(payload, "longShortRatio"),
        long_account=_payload_float(payload, "longAccount"),
        short_account=_payload_float(payload, "shortAccount"),
        raw=payload,
    )


def _taker_buy_sell_volume_record(
    row: Any,
    *,
    fallback_symbol: str,
    period: str,
) -> TakerBuySellVolumeRecord:
    payload = _mapping_payload(row, "/futures/data/takerlongshortRatio")
    return TakerBuySellVolumeRecord(
        source="binance_usdm",
        venue="binance",
        symbol=str(payload.get("symbol") or fallback_symbol),
        period=period,
        timestamp=_timestamp_ms_to_datetime(payload["timestamp"]),
        buy_sell_ratio=_payload_float(payload, "buySellRatio"),
        buy_volume=_payload_float(payload, "buyVol"),
        sell_volume=_payload_float(payload, "sellVol"),
        raw=payload,
    )


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def _list_payload(payload: Any, endpoint: str) -> list[Any]:
    if not isinstance(payload, list):
        raise ValueError(f"{endpoint} response must be a list")
    return payload


def _mapping_payload(payload: Any, endpoint: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{endpoint} response rows must be objects")
    return payload


def _timestamp_ms_to_datetime(timestamp: Any) -> datetime:
    return datetime.fromtimestamp(int(timestamp) / 1_000, tz=UTC)


def _payload_float(payload: dict[str, Any], key: str) -> float:
    value = payload[key]
    return float(value)


def _payload_optional_float(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    return float(value)


def _request_route_kwargs() -> dict[str, Any]:
    proxy = _proxy_value()
    if not proxy:
        return {}
    return {"proxies": {"http": proxy, "https": proxy}}


def _proxy_value() -> str | None:
    for name in _PROXY_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            return value
    return None
