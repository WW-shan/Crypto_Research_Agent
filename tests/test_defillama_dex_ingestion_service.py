from __future__ import annotations

from datetime import UTC, datetime
import json

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.ingestion import (
    ingest_defillama_yield_pools,
    ingest_dexscreener_pairs,
)
from crypto_alpha_agent.data.models import DataSuitability, DefiYieldSnapshot, DexPairSnapshot
from crypto_alpha_agent.data.store import ResearchDataStore


OBSERVED_AT = datetime(2026, 5, 17, 8, 30, tzinfo=UTC)


class FakeDexScreenerClient:
    def __init__(self) -> None:
        self.search_calls: list[str] = []
        self.token_calls: list[tuple[str, list[str]]] = []

    def search_pairs(self, query: str) -> list[DexPairSnapshot]:
        self.search_calls.append(query)
        return [
            DexPairSnapshot(
                source="dexscreener",
                chain="base",
                dex="uniswap",
                pair_address="0xpair",
                base_token="ABC",
                quote_token="USDC",
                price_usd=1.25,
                liquidity_usd=25000.0,
                volume_24h_usd=5000.0,
                observed_at=OBSERVED_AT,
            )
        ]

    def pairs_by_token_addresses(self, chain_id: str, token_addresses: list[str]) -> list[DexPairSnapshot]:
        self.token_calls.append((chain_id, token_addresses))
        return self.search_pairs("token-lookup")


class LowLiquidityDexClient:
    def search_pairs(self, query: str) -> list[DexPairSnapshot]:
        return [
            DexPairSnapshot(
                source="dexscreener",
                chain="base",
                dex="uniswap",
                pair_address="0xlow",
                base_token="LOW",
                quote_token="USDC",
                price_usd=0.04,
                liquidity_usd=999.0,
                volume_24h_usd=125.0,
                observed_at=OBSERVED_AT,
                suitability=DataSuitability(
                    latency_dependency="medium",
                    execution_role="research_only",
                    unsuitable_reasons=["liquidity_too_low"],
                ),
            )
        ]


class FakeDefiLlamaClient:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def yield_pools(self, min_tvl_usd: float = 10000.0) -> list[DefiYieldSnapshot]:
        self.calls.append(min_tvl_usd)
        return [
            DefiYieldSnapshot(
                source="defillama",
                chain="Ethereum",
                project="aave",
                symbol="USDC",
                tvl_usd=500000.0,
                apy=4.1,
                observed_at=OBSERVED_AT,
            )
        ]


class CollidingDefiLlamaClient:
    def yield_pools(self, min_tvl_usd: float = 10000.0) -> list[DefiYieldSnapshot]:
        return [
            DefiYieldSnapshot(
                source="defillama",
                chain="Ethereum",
                project="aave",
                symbol="USDC",
                tvl_usd=500000.0,
                apy=4.1,
                observed_at=OBSERVED_AT,
                raw={"pool": "aave-v3-usdc", "url": "https://example.invalid/aave-v3-usdc"},
            ),
            DefiYieldSnapshot(
                source="defillama",
                chain="Ethereum",
                project="aave",
                symbol="USDC",
                tvl_usd=750000.0,
                apy=4.3,
                observed_at=OBSERVED_AT,
                raw={"pool": "aave-v2-usdc", "url": "https://example.invalid/aave-v2-usdc"},
            ),
        ]


def test_ingest_dexscreener_pairs_writes_dex_pair_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeDexScreenerClient()

    summary = ingest_dexscreener_pairs(db_path, query="USDC", allow_network=True, client=client)

    records = ResearchDataStore(db_path).load_records(record_type="dex_pair", source="dexscreener")
    assert summary.source == "dexscreener"
    assert summary.feed == "pairs"
    assert summary.records_fetched == 1
    assert summary.records_written == 1
    assert summary.uses_real_capital is False
    assert records[0].record_type == "dex_pair"
    assert records[0].payload["pair_address"] == "0xpair"
    assert client.search_calls == ["USDC"]


def test_low_liquidity_dex_pairs_persist_research_only_suitability(tmp_path):
    db_path = tmp_path / "research.sqlite"

    ingest_dexscreener_pairs(db_path, query="LOW", allow_network=True, client=LowLiquidityDexClient())

    records = ResearchDataStore(db_path).load_records(record_type="dex_pair", source="dexscreener")
    assert records[0].payload["suitability"]["execution_role"] == "research_only"
    assert records[0].payload["suitability"]["unsuitable_reasons"] == ["liquidity_too_low"]


def test_ingest_defillama_yield_pools_writes_defi_yield_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    client = FakeDefiLlamaClient()

    summary = ingest_defillama_yield_pools(
        db_path,
        min_tvl_usd=10000,
        allow_network=True,
        client=client,
    )

    records = ResearchDataStore(db_path).load_records(record_type="defi_yield", source="defillama")
    assert summary.source == "defillama"
    assert summary.feed == "yield_pools"
    assert summary.records_fetched == 1
    assert summary.records_written == 1
    assert summary.live_order_routing is False
    assert records[0].record_type == "defi_yield"
    assert records[0].payload["project"] == "aave"
    assert client.calls == [10000]


def test_defillama_yield_pools_keep_distinct_pool_records_with_same_symbol_and_timestamp(tmp_path):
    db_path = tmp_path / "research.sqlite"

    summary = ingest_defillama_yield_pools(
        db_path,
        min_tvl_usd=10000,
        allow_network=True,
        client=CollidingDefiLlamaClient(),
    )

    records = ResearchDataStore(db_path).load_records(record_type="defi_yield", source="defillama")
    assert summary.records_fetched == 2
    assert summary.records_written == 2
    assert len(records) == 2
    assert {record.payload["raw"]["pool"] for record in records} == {"aave-v2-usdc", "aave-v3-usdc"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": ""},
        {"query": "   "},
        {"chain": "", "token_addresses": ["0xabc"]},
        {"chain": "   ", "token_addresses": ["0xabc"]},
        {"chain": "base", "token_addresses": [""]},
        {"chain": "base", "token_addresses": ["   "]},
    ],
)
def test_ingest_dexscreener_pairs_rejects_blank_lookup_inputs(tmp_path, kwargs):
    with pytest.raises(ValueError):
        ingest_dexscreener_pairs(
            tmp_path / "research.sqlite",
            allow_network=True,
            client=FakeDexScreenerClient(),
            **kwargs,
        )


@pytest.mark.parametrize("source", ["dexscreener", "defillama"])
def test_ingest_cli_rejects_dex_and_defi_sources_without_allow_network(tmp_path, source):
    with pytest.raises(SystemExit):
        main(["ingest", "--db", str(tmp_path / "research.sqlite"), "--source", source])


@pytest.mark.parametrize(
    "source_args",
    [
        [
            "--source",
            "ccxt",
            "--ccxt-feed",
            "ohlcv",
            "--symbol",
            "ETH/USDT",
            "--timeframe",
            "1h",
        ],
        ["--source", "dexscreener", "--query", "USDC"],
    ],
)
def test_ingest_cli_rejects_min_tvl_usd_for_non_defillama_sources(tmp_path, monkeypatch, source_args):
    class EmptyCcxtCollector:
        def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
            return []

    monkeypatch.setattr(
        "crypto_alpha_agent.data.ingestion.DexScreenerClient",
        lambda: FakeDexScreenerClient(),
    )
    monkeypatch.setattr(
        "crypto_alpha_agent.data.ingestion.CcxtResearchCollector",
        lambda exchange_id="binance": EmptyCcxtCollector(),
    )

    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--allow-network",
                *source_args,
                "--min-tvl-usd",
                "10000",
            ]
        )


@pytest.mark.parametrize(
    "lookup_args",
    [
        ["--query", ""],
        ["--query", "   "],
        ["--chain", "", "--token-address", "0xabc"],
        ["--chain", "   ", "--token-address", "0xabc"],
        ["--chain", "base", "--token-address", ""],
        ["--chain", "base", "--token-address", "   "],
    ],
)
def test_ingest_cli_rejects_blank_dexscreener_lookup_inputs(tmp_path, monkeypatch, lookup_args):
    monkeypatch.setattr(
        "crypto_alpha_agent.data.ingestion.DexScreenerClient",
        lambda: FakeDexScreenerClient(),
    )

    with pytest.raises(SystemExit):
        main(
            [
                "ingest",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--source",
                "dexscreener",
                "--allow-network",
                *lookup_args,
            ]
        )


def test_ingest_cli_runs_dexscreener_query_with_network_gate(capsys, tmp_path, monkeypatch):
    db_path = tmp_path / "research.sqlite"

    monkeypatch.setattr(
        "crypto_alpha_agent.data.ingestion.DexScreenerClient",
        lambda: FakeDexScreenerClient(),
    )

    exit_code = main(
        [
            "ingest",
            "--db",
            str(db_path),
            "--source",
            "dexscreener",
            "--query",
            "USDC",
            "--allow-network",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["feed"] == "pairs"
    assert ResearchDataStore(db_path).load_records(record_type="dex_pair", source="dexscreener")


def test_ingest_cli_runs_defillama_with_network_gate(capsys, tmp_path, monkeypatch):
    db_path = tmp_path / "research.sqlite"

    monkeypatch.setattr(
        "crypto_alpha_agent.data.ingestion.DefiLlamaResearchClient",
        lambda: FakeDefiLlamaClient(),
    )

    exit_code = main(
        [
            "ingest",
            "--db",
            str(db_path),
            "--source",
            "defillama",
            "--min-tvl-usd",
            "10000",
            "--allow-network",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ingestion"]["feed"] == "yield_pools"
    assert ResearchDataStore(db_path).load_records(record_type="defi_yield", source="defillama")
