from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

from crypto_alpha_agent.data.models import DataSuitability, DefiYieldSnapshot


class DefiLlamaResearchClient:
    def __init__(
        self,
        base_url: str = "https://yields.llama.fi",
        session=None,
        timeout_seconds: float = 30.0,
        now=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.now = now or (lambda: datetime.now(UTC))

    def yield_pools(self, min_tvl_usd: float = 10000) -> list[DefiYieldSnapshot]:
        response = self.session.get(f"{self.base_url}/pools", timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        observed_at = self.now()
        return [
            _pool_to_snapshot(row, observed_at)
            for row in rows
            if _to_float(row.get("tvlUsd")) >= min_tvl_usd
        ]


def _pool_to_snapshot(pool: dict[str, Any], observed_at: datetime) -> DefiYieldSnapshot:
    return DefiYieldSnapshot(
        source="defillama",
        chain=str(pool.get("chain") or ""),
        project=str(pool.get("project") or ""),
        symbol=str(pool.get("symbol") or ""),
        tvl_usd=_to_float(pool.get("tvlUsd")),
        apy=_to_float(pool.get("apy")),
        observed_at=observed_at,
        suitability=DataSuitability(
            min_capital_usd=25.0,
            latency_dependency="low",
            rpc_dependency="none",
            execution_role="research_and_paper",
        ),
        raw=pool,
    )


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
