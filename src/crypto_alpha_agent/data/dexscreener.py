from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

import requests

from crypto_alpha_agent.data.models import DataSuitability, DexPairSnapshot


class DexScreenerClient:
    def __init__(
        self,
        base_url: str = "https://api.dexscreener.com",
        session=None,
        timeout_seconds: float = 30.0,
        now=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(UTC))

    def search_pairs(self, query: str) -> list[DexPairSnapshot]:
        url = f"{self.base_url}/latest/dex/search?{urlencode({'q': query})}"
        payload = self._get_json(url)
        return self._normalize_pairs(payload.get("pairs", []) if isinstance(payload, dict) else [])

    def pairs_by_token_addresses(
        self, chain_id: str, token_addresses: list[str]
    ) -> list[DexPairSnapshot]:
        addresses = ",".join(token_addresses)
        url = (
            f"{self.base_url}/tokens/v1/"
            f"{quote(chain_id, safe='')}/{quote(addresses, safe=',')}"
        )
        payload = self._get_json(url)
        return self._normalize_pairs(payload if isinstance(payload, list) else [])

    def _get_json(self, url: str) -> Any:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def _normalize_pairs(self, pairs: list[dict[str, Any]]) -> list[DexPairSnapshot]:
        observed_at = self.now()
        return [_pair_to_snapshot(pair, observed_at) for pair in pairs]


def _pair_to_snapshot(pair: dict[str, Any], observed_at: datetime) -> DexPairSnapshot:
    liquidity_usd = _to_float(_nested_get(pair, "liquidity", "usd"))
    return DexPairSnapshot(
        source="dexscreener",
        chain=str(pair.get("chainId") or ""),
        dex=str(pair.get("dexId") or ""),
        pair_address=str(pair.get("pairAddress") or ""),
        base_token=str(_nested_get(pair, "baseToken", "symbol") or ""),
        quote_token=str(_nested_get(pair, "quoteToken", "symbol") or ""),
        price_usd=_to_float(pair.get("priceUsd")),
        liquidity_usd=liquidity_usd,
        volume_24h_usd=_to_float(_nested_get(pair, "volume", "h24")),
        observed_at=observed_at,
        suitability=_dex_suitability(liquidity_usd),
        raw=pair,
    )


def _dex_suitability(liquidity_usd: float) -> DataSuitability:
    unsuitable_reasons = []
    execution_role = "research_and_paper"
    if liquidity_usd < 10_000:
        execution_role = "research_only"
        unsuitable_reasons.append("liquidity_too_low")

    return DataSuitability(
        min_capital_usd=25.0,
        latency_dependency="medium",
        rpc_dependency="none",
        execution_role=execution_role,
        unsuitable_reasons=unsuitable_reasons,
    )


def _nested_get(payload: dict[str, Any], key: str, nested_key: str) -> Any:
    value = payload.get(key)
    if not isinstance(value, dict):
        return None
    return value.get(nested_key)


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
