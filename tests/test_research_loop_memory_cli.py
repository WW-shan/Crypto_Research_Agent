from __future__ import annotations

import json
from datetime import UTC, datetime

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import (
    DexPairSnapshot,
    FundingRateRecord,
    MarketCandle,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryStore


def _candle(hour: int, close: float, *, symbol: str = "BTC/USDT") -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol=symbol,
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        funding_rate=rate,
    )


def _funding_record(funding: FundingRateRecord) -> SourceRecord:
    safe_symbol = funding.symbol.replace("/", "").replace(":", "-")
    return SourceRecord(
        record_id=f"{funding.source}:{safe_symbol}:funding:{funding.timestamp.isoformat()}",
        source=funding.source,
        record_type="funding_rate",
        observed_at=funding.timestamp,
        payload=funding.model_dump(mode="json"),
    )


def _dex_pair(
    *,
    base_token: str,
    liquidity_usd: float,
    volume_24h_usd: float = 25_000.0,
) -> DexPairSnapshot:
    return DexPairSnapshot(
        source="dexscreener",
        chain="Ethereum",
        dex="uniswap",
        pair_address=f"0x{base_token.lower()}",
        base_token=base_token,
        quote_token="USDC",
        price_usd=1.0,
        liquidity_usd=liquidity_usd,
        volume_24h_usd=volume_24h_usd,
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
    )


def _dex_pair_record(snapshot: DexPairSnapshot) -> SourceRecord:
    return SourceRecord(
        record_id=(
            f"{snapshot.source}:{snapshot.chain}:{snapshot.dex}:"
            f"{snapshot.pair_address}:{snapshot.observed_at.isoformat()}"
        ),
        source=snapshot.source,
        record_type="dex_pair",
        observed_at=snapshot.observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _seed_hypothesis_fixture(db_path) -> None:
    ResearchDataStore(db_path).upsert_records(
        [
            _dex_pair_record(_dex_pair(base_token="WETH", liquidity_usd=100_000.0)),
            _dex_pair_record(_dex_pair(base_token="MICRO", liquidity_usd=100.0)),
        ]
    )


def _seed_registered_validation_fixture(db_path) -> None:
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])
    ]
    store.upsert_records([candle.to_source_record() for candle in candles])
    store.upsert_records(
        [
            _funding_record(funding)
            for funding in [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
        ]
    )


def test_research_loop_memory_cli_persists_generated_and_blocked_hypotheses(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "var" / "memory.jsonl"
    _seed_hypothesis_fixture(db_path)

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--current-capital-usd",
            "300",
            "--run-id",
            "cli-memory-run",
            "--memory",
            str(memory_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    records = MemoryStore(memory_path).list_records()
    research_records = [record for record in records if "research-loop" in record.tags]
    llm_records = [record for record in records if "llm" in record.tags]

    assert exit_code == 0
    assert payload["memory_records_written"] == 2
    assert payload["memory_path"] == str(memory_path)
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert {record.opportunity["asset"] for record in research_records} == {"WETH", "MICRO"}
    assert all("research-loop" in record.tags for record in research_records)
    assert any("blocked" in record.tags for record in research_records)
    assert len(llm_records) == 1
    assert llm_records[0].record_id == payload["llm_memory_record_id"]


def test_research_loop_memory_cli_persists_validation_evidence_lessons(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "var" / "memory.jsonl"
    _seed_registered_validation_fixture(db_path)

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-validation",
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--validation-timeframe",
            "1h",
            "--hold-bars",
            "2",
            "--min-trades",
            "2",
            "--run-id",
            "cli-validation-memory-run",
            "--memory",
            str(memory_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    validation_records = [
        record
        for record in MemoryStore(memory_path).list_records()
        if "validation-evidence" in record.tags
    ]

    assert exit_code == 0
    assert payload["memory_records_written"] >= 1
    assert payload["validation_memory_records_written"] == 1
    assert payload["memory_path"] == str(memory_path)
    assert len(validation_records) == 1
    assert validation_records[0].hypothesis["lesson"] == "validation_blocked"
    assert validation_records[0].opportunity["run_id"] == "cli-validation-memory-run"
    assert validation_records[0].opportunity["uses_real_capital"] is False
    assert validation_records[0].opportunity["live_order_routing"] is False


def test_research_loop_memory_cli_is_idempotent_by_record_id(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "var" / "memory.jsonl"
    _seed_hypothesis_fixture(db_path)
    args = [
        "research-loop",
        "--db",
        str(db_path),
        "--run-id",
        "cli-memory-idempotent-run",
        "--memory",
        str(memory_path),
    ]

    main(args)
    first_payload = json.loads(capsys.readouterr().out)
    first_record_ids = [record.record_id for record in MemoryStore(memory_path).list_records()]
    main(args)
    second_payload = json.loads(capsys.readouterr().out)
    second_record_ids = [record.record_id for record in MemoryStore(memory_path).list_records()]

    assert first_payload["memory_records_written"] == 2
    assert second_payload["memory_records_written"] == 2
    assert second_record_ids == first_record_ids


def test_research_loop_memory_cli_empty_report_does_not_create_memory_file(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "var" / "memory.jsonl"
    ResearchDataStore(db_path)

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-validation",
            "--memory",
            str(memory_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["memory_records_written"] == 0
    assert payload["memory_path"] == str(memory_path)
    assert payload["validation_memory_records_written"] == 0
    records = MemoryStore(memory_path).list_records()
    assert len(records) == 1
    assert records[0].record_id == payload["llm_memory_record_id"]
    assert records[0].tags == ["llm", "research_loop", "rejected"]


def test_research_loop_memory_cli_ignores_stale_validation_ledger_without_validation(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "var" / "memory.jsonl"
    ResearchDataStore(db_path)
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            ValidationEvidence(
                run_id="stale-validation-run",
                strategy_family="funding_extremity_price_confirmation",
                symbol="BTC/USDT",
                timeframe="1h",
                validator_name="strategy_registry",
                trade_count=2,
                net_return=-0.01,
                gross_expectancy=-0.005,
                fee_adjusted_expectancy=-0.006,
                slippage_adjusted_expectancy=-0.007,
                max_drawdown=0.01,
                walk_forward_split_count=0,
                walk_forward_pass_rate=0.0,
                approved=False,
                blocked_reasons=("insufficient_trades",),
            )
        ]
    )

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--run-id",
            "stale-validation-run",
            "--memory",
            str(memory_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["memory_records_written"] == 0
    assert payload["validation_memory_records_written"] == 0
    records = MemoryStore(memory_path).list_records()
    assert len(records) == 1
    assert records[0].record_id == payload["llm_memory_record_id"]
    assert records[0].tags == ["llm", "research_loop", "rejected"]
