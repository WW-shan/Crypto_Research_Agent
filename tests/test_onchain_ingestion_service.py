from __future__ import annotations

from datetime import UTC, datetime
import json

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.onchain_ingestion import (
    SlowEvidenceIngestionSummary,
    ingest_dune_query_result,
    ingest_thegraph_query_result,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.tools.dune import DuneQueryResult
from crypto_alpha_agent.tools.thegraph import TheGraphQueryResult


OBSERVED_AT = datetime(2026, 5, 17, 8, 30, tzinfo=UTC)


class FakeDuneClient:
    def __init__(self) -> None:
        self.calls: list[tuple[int, dict | None]] = []

    def execute_query(self, query_id, *, params=None):
        self.calls.append((query_id, params))
        return DuneQueryResult(
            query_id=query_id,
            rows=[{"asset": "ETH", "metric": "stablecoin_inflow", "value": float(query_id)}],
            raw={"result": {"rows": [{"asset": "ETH", "query_id": query_id}]}},
        )


class FakeGraphClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []

    def query(self, subgraph_url, query, *, variables=None):
        self.calls.append((subgraph_url, query, variables))
        return TheGraphQueryResult(
            subgraph_url=subgraph_url,
            data={"pools": [{"id": "pool-1", "liquidityUSD": "100000"}]},
            raw={"data": {"pools": [{"id": "pool-1"}]}},
        )


class EmptyDuneClient:
    def execute_query(self, query_id, *, params=None):
        return DuneQueryResult(
            query_id=query_id,
            rows=[],
            raw={"result": {"rows": []}},
        )


def test_dune_query_result_is_persisted_as_slow_research_snapshot(tmp_path):
    db_path = tmp_path / "research.sqlite"

    summary = ingest_dune_query_result(
        db_path,
        query_id=123,
        allow_network=True,
        client=FakeDuneClient(),
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="dune")
    assert summary.source == "dune"
    assert summary.feed == "dune_query_result"
    assert summary.records_written == 1
    assert summary.network_allowed is True
    assert summary.uses_real_capital is False
    assert summary.live_order_routing is False
    assert records[0].record_type == "research_snapshot"
    assert records[0].record_id.startswith("dune:")
    assert records[0].record_id.endswith(OBSERVED_AT.isoformat())
    assert records[0].payload["query_ref"]
    assert records[0].payload["rows"][0]["metric"] == "stablecoin_inflow"
    assert records[0].payload["execution_role"] == "research_only"
    assert records[0].payload["latency_dependency"] == "low"
    assert records[0].payload["rpc_dependency"] == "none"
    assert records[0].payload["uses_real_capital"] is False
    assert records[0].payload["live_order_routing"] is False
    assert records[0].payload["blocked_reasons"] == []


def test_dune_query_result_keeps_distinct_records_for_different_query_ids(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeDuneClient()

    ingest_dune_query_result(
        db_path,
        query_id=123,
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )
    ingest_dune_query_result(
        db_path,
        query_id=456,
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="dune")
    assert len(records) == 2
    assert len({record.record_id for record in records}) == 2
    assert client.calls == [(123, None), (456, None)]


def test_dune_query_ref_distinguishes_different_params_for_same_query_id(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeDuneClient()

    ingest_dune_query_result(
        db_path,
        query_id=123,
        params={"chain": "ethereum"},
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )
    ingest_dune_query_result(
        db_path,
        query_id=123,
        params={"chain": "arbitrum"},
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="dune")
    assert len(records) == 2
    assert len({record.payload["query_ref"] for record in records}) == 2


def test_empty_dune_query_result_writes_snapshot_with_zero_fetched_rows(tmp_path):
    db_path = tmp_path / "research.sqlite"

    summary = ingest_dune_query_result(
        db_path,
        query_id=123,
        allow_network=True,
        client=EmptyDuneClient(),
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="dune")
    assert summary.records_fetched == 0
    assert summary.records_written == 1
    assert records[0].payload["rows"] == []


def test_thegraph_query_result_is_persisted_as_slow_research_snapshot(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeGraphClient()

    summary = ingest_thegraph_query_result(
        db_path,
        subgraph_url="https://example.test/subgraph",
        query="{ pools { id } }",
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="thegraph")
    assert summary.source == "thegraph"
    assert summary.feed == "thegraph_query_result"
    assert summary.records_written == 1
    assert summary.network_allowed is True
    assert summary.uses_real_capital is False
    assert summary.live_order_routing is False
    assert records[0].record_type == "research_snapshot"
    assert records[0].record_id.startswith("thegraph:")
    assert records[0].record_id.endswith(OBSERVED_AT.isoformat())
    assert records[0].payload["query_ref"]
    assert records[0].payload["subgraph_ref"]
    assert records[0].payload["data"]["pools"][0]["id"] == "pool-1"
    assert records[0].payload["execution_role"] == "research_only"
    assert records[0].payload["latency_dependency"] == "low"
    assert records[0].payload["rpc_dependency"] == "none"
    assert records[0].payload["uses_real_capital"] is False
    assert records[0].payload["live_order_routing"] is False
    assert records[0].payload["blocked_reasons"] == []
    assert client.calls == [("https://example.test/subgraph", "{ pools { id } }", None)]


def test_thegraph_query_result_keeps_distinct_records_for_different_queries(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeGraphClient()

    ingest_thegraph_query_result(
        db_path,
        subgraph_url="https://example.test/subgraph",
        query="{ pools { id } }",
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )
    ingest_thegraph_query_result(
        db_path,
        subgraph_url="https://example.test/subgraph",
        query="{ pools { id liquidityUSD } }",
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="thegraph")
    assert len(records) == 2
    assert len({record.record_id for record in records}) == 2


def test_thegraph_payload_does_not_persist_secret_subgraph_url(tmp_path):
    db_path = tmp_path / "research.sqlite"
    secret_url = "https://gateway.thegraph.com/api/SECRET_KEY/subgraphs/id/abc"

    ingest_thegraph_query_result(
        db_path,
        subgraph_url=secret_url,
        query="{ pools { id } }",
        allow_network=True,
        client=FakeGraphClient(),
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="thegraph")
    payload_json = json.dumps(records[0].payload, sort_keys=True)
    assert "SECRET_KEY" not in payload_json
    assert secret_url not in payload_json
    assert "subgraph_url" not in records[0].payload
    assert records[0].payload["subgraph_ref"]


def test_thegraph_query_ref_distinguishes_different_variables(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeGraphClient()

    ingest_thegraph_query_result(
        db_path,
        subgraph_url="https://example.test/subgraph",
        query="{ pools(first: $first) { id } }",
        variables={"first": "10"},
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )
    ingest_thegraph_query_result(
        db_path,
        subgraph_url="https://example.test/subgraph",
        query="{ pools(first: $first) { id } }",
        variables={"first": "20"},
        allow_network=True,
        client=client,
        observed_at=OBSERVED_AT,
    )

    records = ResearchDataStore(db_path).load_records(record_type="research_snapshot", source="thegraph")
    assert len(records) == 2
    assert len({record.payload["query_ref"] for record in records}) == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["ingest", "--db", "research.sqlite", "--source", "dune"],
        [
            "ingest",
            "--db",
            "research.sqlite",
            "--source",
            "dune",
            "--allow-network",
        ],
        [
            "ingest",
            "--db",
            "research.sqlite",
            "--source",
            "dune",
            "--allow-network",
            "--dune-query-id",
            "123",
        ],
    ],
)
def test_ingest_cli_requires_dune_network_gate_and_query_arguments(tmp_path, argv):
    argv = [str(tmp_path / "research.sqlite") if item == "research.sqlite" else item for item in argv]
    with pytest.raises(SystemExit):
        main(argv)


def test_ingest_cli_requires_dune_api_key(tmp_path):
    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--source",
                "dune",
                "--allow-network",
                "--dune-query-id",
                "123",
            ]
        )


def test_ingest_cli_requires_thegraph_arguments(tmp_path):
    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--source",
                "thegraph",
                "--allow-network",
            ]
        )


@pytest.mark.parametrize(
    "argv",
    [
        [
            "ingest",
            "--db",
            "research.sqlite",
            "--source",
            "ccxt",
            "--source",
            "dune",
            "--allow-network",
            "--dune-query-id",
            "123",
            "--dune-api-key",
            "test-key",
        ],
        [
            "ingest",
            "--db",
            "research.sqlite",
            "--source",
            "ccxt",
            "--source",
            "thegraph",
            "--allow-network",
            "--subgraph-url",
            "https://example.test/subgraph",
            "--graph-query",
            "{ pools { id } }",
        ],
    ],
)
def test_ingest_cli_rejects_mixing_dune_thegraph_with_ccxt_flags(tmp_path, argv):
    argv = [str(tmp_path / "research.sqlite") if item == "research.sqlite" else item for item in argv]
    with pytest.raises(SystemExit):
        main(argv)


@pytest.mark.parametrize(
    ("source_args", "duplicate_args"),
    [
        (
            [
                "--source",
                "dune",
                "--dune-query-id",
                "123",
                "--dune-api-key",
                "test-key",
            ],
            ["--dune-param", "chain=ethereum", "--dune-param", "chain=arbitrum"],
        ),
        (
            [
                "--source",
                "thegraph",
                "--subgraph-url",
                "https://example.test/subgraph",
                "--graph-query",
                "{ pools { id } }",
            ],
            ["--graph-variable", "first=10", "--graph-variable", "first=20"],
        ),
    ],
)
def test_ingest_cli_rejects_duplicate_onchain_key_value_flags(tmp_path, source_args, duplicate_args):
    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--allow-network",
                *source_args,
                *duplicate_args,
            ]
        )


def test_ingest_cli_runs_dune_with_fake_ingestion(capsys, tmp_path, monkeypatch):
    calls = []

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        return SlowEvidenceIngestionSummary(
            source="dune",
            db_path=str(kwargs["db_path"]),
            feed="dune_query_result",
            records_fetched=1,
            records_written=1,
            network_allowed=True,
            uses_real_capital=False,
            live_order_routing=False,
        )

    monkeypatch.setattr("crypto_alpha_agent.cli.ingest_dune_query_result", fake_ingest)

    exit_code = main(
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "dune",
            "--allow-network",
            "--dune-query-id",
            "123",
            "--dune-api-key",
            "test-key",
            "--dune-param",
            "chain=ethereum",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["source"] == "dune"
    assert payload["ingestion"]["records_written"] == 1
    assert calls[0]["params"] == {"chain": "ethereum"}


def test_ingest_cli_runs_thegraph_with_fake_ingestion(capsys, tmp_path, monkeypatch):
    calls = []

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        return SlowEvidenceIngestionSummary(
            source="thegraph",
            db_path=str(kwargs["db_path"]),
            feed="thegraph_query_result",
            records_fetched=1,
            records_written=1,
            network_allowed=True,
            uses_real_capital=False,
            live_order_routing=False,
        )

    monkeypatch.setattr("crypto_alpha_agent.cli.ingest_thegraph_query_result", fake_ingest)

    exit_code = main(
        [
            "ingest",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--source",
            "thegraph",
            "--allow-network",
            "--subgraph-url",
            "https://example.test/subgraph",
            "--graph-query",
            "{ pools(first: $first) { id } }",
            "--graph-variable",
            "first=10",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["source"] == "thegraph"
    assert payload["ingestion"]["records_written"] == 1
    assert calls[0]["variables"] == {"first": "10"}
