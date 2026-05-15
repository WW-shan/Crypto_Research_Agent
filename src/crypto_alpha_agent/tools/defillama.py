from __future__ import annotations

from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.tools.http import HttpClient, SourceHealth


class DefiLlamaProtocolSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["defillama"] = "defillama"
    protocol: str
    slug: str
    chain_tvls: dict[str, float] = Field(default_factory=dict)
    raw: dict[str, Any]


def normalize_defillama_protocol_snapshot(raw: dict[str, Any]) -> DefiLlamaProtocolSnapshot:
    if not isinstance(raw, dict):
        raise ValueError("DefiLlama protocol snapshot raw payload must be an object")

    if not raw.get("name"):
        raise ValueError("DefiLlama protocol snapshot must contain name")
    if not raw.get("slug"):
        raise ValueError("DefiLlama protocol snapshot must contain slug")

    raw_chain_tvls = raw.get("chainTvls", {})
    if not isinstance(raw_chain_tvls, dict):
        raise ValueError("DefiLlama chainTvls must be an object")

    chain_tvls: dict[str, float] = {}
    for chain, payload in raw_chain_tvls.items():
        if isinstance(payload, dict) and payload.get("tvl") is not None:
            if not isinstance(payload["tvl"], int | float) or isinstance(payload["tvl"], bool):
                raise ValueError(f"DefiLlama TVL for {chain} must be numeric")
            chain_tvls[str(chain)] = float(payload["tvl"])

    return DefiLlamaProtocolSnapshot(
        protocol=str(raw["name"]),
        slug=str(raw["slug"]),
        chain_tvls=chain_tvls,
        raw=raw,
    )


class DefiLlamaClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.llama.fi",
        session: Any | None = None,
        max_attempts: int = 3,
        timeout_seconds: float = 30.0,
        backoff_seconds: float = 0.5,
        sleep: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.http = HttpClient(
            source="defillama",
            session=self.session,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            backoff_seconds=backoff_seconds,
            sleep=sleep,
        )
        self.last_health: SourceHealth | None = None

    def protocol(self, slug: str) -> DefiLlamaProtocolSnapshot:
        response, health = self.http.get(f"{self.base_url}/protocol/{slug}")
        self.last_health = health
        return normalize_defillama_protocol_snapshot(response.json())
