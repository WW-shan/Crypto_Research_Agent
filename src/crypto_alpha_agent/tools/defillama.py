from __future__ import annotations

from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field


class DefiLlamaProtocolSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "defillama"
    protocol: str
    slug: str
    chain_tvls: dict[str, float] = Field(default_factory=dict)
    raw: dict[str, Any]


def normalize_defillama_protocol_snapshot(raw: dict[str, Any]) -> DefiLlamaProtocolSnapshot:
    chain_tvls: dict[str, float] = {}
    for chain, payload in raw.get("chainTvls", {}).items():
        if isinstance(payload, dict) and payload.get("tvl") is not None:
            chain_tvls[str(chain)] = float(payload["tvl"])

    return DefiLlamaProtocolSnapshot(
        protocol=str(raw["name"]),
        slug=str(raw["slug"]),
        chain_tvls=chain_tvls,
        raw=raw,
    )


class DefiLlamaClient:
    def __init__(self, *, base_url: str = "https://api.llama.fi", session: Any | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def protocol(self, slug: str) -> DefiLlamaProtocolSnapshot:
        response = self.session.get(f"{self.base_url}/protocol/{slug}")
        response.raise_for_status()
        return normalize_defillama_protocol_snapshot(response.json())
