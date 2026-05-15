from __future__ import annotations

from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field


class DuneQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["dune"] = "dune"
    query_id: int
    rows: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any]


def normalize_dune_query_result(raw: dict[str, Any], *, query_id: int) -> DuneQueryResult:
    if not isinstance(raw, dict):
        raise ValueError("Dune result raw payload must be an object")

    result = raw.get("result")
    if not isinstance(result, dict) or "rows" not in result:
        raise ValueError("Dune result must contain result.rows")

    rows = result["rows"]
    if not isinstance(rows, list):
        raise ValueError("Dune result rows must be a list")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Dune result rows must contain objects")

    return DuneQueryResult(query_id=query_id, rows=list(rows), raw=raw)


class DuneClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.dune.com/api/v1",
        session: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def execute_query(self, query_id: int, *, params: dict[str, Any] | None = None) -> DuneQueryResult:
        response = self.session.get(
            f"{self.base_url}/query/{query_id}/results",
            headers={"x-dune-api-key": self.api_key},
            params=params,
        )
        response.raise_for_status()
        return normalize_dune_query_result(response.json(), query_id=query_id)
