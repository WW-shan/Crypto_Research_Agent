from __future__ import annotations

from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field


class TheGraphQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["thegraph"] = "thegraph"
    subgraph_url: str
    data: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any]


def normalize_thegraph_query_result(raw: dict[str, Any], *, subgraph_url: str) -> TheGraphQueryResult:
    if not isinstance(raw, dict):
        raise ValueError("The Graph result raw payload must be an object")

    if "data" not in raw:
        raise ValueError("The Graph result must contain data")

    data = raw["data"]
    if not isinstance(data, dict):
        raise ValueError("The Graph result data must be an object")

    return TheGraphQueryResult(subgraph_url=subgraph_url, data=data, raw=raw)


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
