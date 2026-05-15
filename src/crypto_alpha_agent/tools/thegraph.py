from __future__ import annotations

from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.tools.http import HttpClient, SourceHealth


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
    def __init__(
        self,
        *,
        session: Any | None = None,
        max_attempts: int = 3,
        timeout_seconds: float = 30.0,
        backoff_seconds: float = 0.5,
        sleep: Any | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.http = HttpClient(
            source="thegraph",
            session=self.session,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            backoff_seconds=backoff_seconds,
            sleep=sleep,
        )
        self.last_health: SourceHealth | None = None

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

        response, health = self.http.post(subgraph_url, json=payload)
        self.last_health = health
        return normalize_thegraph_query_result(response.json(), subgraph_url=subgraph_url)
