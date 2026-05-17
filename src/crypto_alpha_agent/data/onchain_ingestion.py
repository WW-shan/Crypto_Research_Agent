from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.tools.dune import DuneClient, DuneQueryResult
from crypto_alpha_agent.tools.thegraph import TheGraphClient, TheGraphQueryResult


class SlowEvidenceIngestionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["dune", "thegraph"]
    db_path: str
    feed: Literal["dune_query_result", "thegraph_query_result"]
    records_fetched: int
    records_written: int
    network_allowed: bool
    uses_real_capital: bool
    live_order_routing: bool


def ingest_dune_query_result(
    db_path: str | Path,
    *,
    query_id: int,
    allow_network: bool = False,
    api_key: str | None = None,
    client: Any | None = None,
    params: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> SlowEvidenceIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for Dune ingestion")
    if client is None and not _non_blank(api_key):
        raise ValueError("api_key is required for Dune ingestion")
    if query_id <= 0:
        raise ValueError("query_id must be positive")

    dune_client = client or DuneClient(api_key=api_key.strip())
    result = DuneQueryResult.model_validate(
        dune_client.execute_query(query_id, params=params)
    )
    snapshot_at = observed_at or datetime.now(tz=UTC)
    record = _dune_record(result, observed_at=snapshot_at, params=params)
    records_written = ResearchDataStore(db_path).upsert_records([record])

    return SlowEvidenceIngestionSummary(
        source="dune",
        db_path=str(db_path),
        feed="dune_query_result",
        records_fetched=len(result.rows),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def ingest_thegraph_query_result(
    db_path: str | Path,
    *,
    subgraph_url: str,
    query: str,
    allow_network: bool = False,
    client: Any | None = None,
    variables: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> SlowEvidenceIngestionSummary:
    if not allow_network:
        raise ValueError("allow_network is required for The Graph ingestion")
    if not subgraph_url.strip():
        raise ValueError("subgraph_url cannot be blank")
    if not query.strip():
        raise ValueError("query cannot be blank")

    graph_client = client or TheGraphClient()
    result = TheGraphQueryResult.model_validate(
        graph_client.query(subgraph_url, query, variables=variables)
    )
    snapshot_at = observed_at or datetime.now(tz=UTC)
    record = _thegraph_record(
        result,
        query=query,
        variables=variables,
        observed_at=snapshot_at,
    )
    records_written = ResearchDataStore(db_path).upsert_records([record])

    return SlowEvidenceIngestionSummary(
        source="thegraph",
        db_path=str(db_path),
        feed="thegraph_query_result",
        records_fetched=_thegraph_fetched_count(result.data),
        records_written=records_written,
        network_allowed=True,
        uses_real_capital=False,
        live_order_routing=False,
    )


def _dune_record(
    result: DuneQueryResult,
    *,
    observed_at: datetime,
    params: dict[str, Any] | None,
) -> SourceRecord:
    query_identity = {"query_id": result.query_id, "params": params or {}}
    query_hash = _stable_hash(query_identity)
    payload = {
        **_slow_research_payload(source="dune", observed_at=observed_at),
        "query_id": result.query_id,
        "query_ref": query_hash,
        "params": params or {},
        "rows": result.rows,
        "raw": result.raw,
    }
    return SourceRecord(
        record_id=f"dune:{query_hash}:research_snapshot:{observed_at.isoformat()}",
        source="dune",
        record_type="research_snapshot",
        observed_at=observed_at,
        payload=payload,
    )


def _thegraph_record(
    result: TheGraphQueryResult,
    *,
    query: str,
    variables: dict[str, Any] | None,
    observed_at: datetime,
) -> SourceRecord:
    subgraph_hash = _stable_hash({"subgraph_url": result.subgraph_url})
    query_hash = _stable_hash(
        {
            "subgraph_url": result.subgraph_url,
            "query": query,
            "variables": variables or {},
        }
    )
    payload = {
        **_slow_research_payload(source="thegraph", observed_at=observed_at),
        "subgraph_ref": subgraph_hash,
        "subgraph_host": _safe_url_host(result.subgraph_url),
        "query": query,
        "query_ref": query_hash,
        "variables": variables or {},
        "data": result.data,
        "raw": result.raw,
    }
    return SourceRecord(
        record_id=f"thegraph:{query_hash}:research_snapshot:{observed_at.isoformat()}",
        source="thegraph",
        record_type="research_snapshot",
        observed_at=observed_at,
        payload=payload,
    )


def _slow_research_payload(*, source: Literal["dune", "thegraph"], observed_at: datetime) -> dict[str, Any]:
    return {
        "source": source,
        "observed_at": observed_at.isoformat(),
        "execution_role": "research_only",
        "latency_dependency": "low",
        "rpc_dependency": "none",
        "uses_real_capital": False,
        "live_order_routing": False,
        "blocked_reasons": [],
    }


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _thegraph_fetched_count(data: dict[str, Any]) -> int:
    list_lengths = [len(value) for value in data.values() if isinstance(value, list)]
    if list_lengths:
        return sum(list_lengths)
    return len(data)


def _safe_url_host(url: str) -> str:
    return urlsplit(url).hostname or ""


def _non_blank(value: str | None) -> bool:
    return value is not None and bool(value.strip())
