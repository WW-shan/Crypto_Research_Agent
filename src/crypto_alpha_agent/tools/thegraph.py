from __future__ import annotations

from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field


class TheGraphQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "thegraph"
    subgraph_url: str
    data: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any]


def normalize_thegraph_query_result(raw: dict[str, Any], *, subgraph_url: str) -> TheGraphQueryResult:
    data = raw.get("data", {})
    return TheGraphQueryResult(subgraph_url=subgraph_url, data=dict(data), raw=raw)


class TheGraphClient:
    def __init__(self, *, session: Any | None = None) -> None:
        self.session = session or requests.Session()

    def query(
        self,
        subgraph_url: str,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
    ) -> TheGraphQueryResult:
        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = variables

        response = self.session.post(subgraph_url, json=payload)
        response.raise_for_status()
        return normalize_thegraph_query_result(response.json(), subgraph_url=subgraph_url)

