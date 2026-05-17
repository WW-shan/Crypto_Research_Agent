from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import sqlite3

import pytest

from crypto_alpha_agent.data.models import (
    DefiYieldSnapshot,
    FundingRateRecord,
    MarketCandle,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def _validation_evidence(**overrides: object) -> ValidationEvidence:
    data = {
        "run_id": "validation-run-001",
        "strategy_family": "funding_extremity_price_confirmation",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "validator_name": "funding_price",
        "trade_count": 4,
        "net_return": 0.03,
        "gross_expectancy": 0.005,
        "fee_adjusted_expectancy": 0.004,
        "slippage_adjusted_expectancy": 0.003,
        "max_drawdown": 0.02,
        "walk_forward_split_count": 1,
        "walk_forward_pass_rate": 1.0,
        "approved": True,
        "blocked_reasons": [],
    }
    data.update(overrides)
    return ValidationEvidence(**data)


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
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


def _write_funding_price_fixture(db_path, *, include_funding: bool = True) -> None:
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])
    ]
    store.upsert_records([item.to_source_record() for item in candles])
    if include_funding:
        store.upsert_records(
            [
                _funding_record(item)
                for item in [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
            ]
        )


def _defi_yield_record(snapshot: DefiYieldSnapshot) -> SourceRecord:
    safe_symbol = snapshot.symbol.replace("/", "")
    return SourceRecord(
        record_id=(
            f"{snapshot.source}:{snapshot.chain}:{snapshot.project}:{safe_symbol}:"
            f"{snapshot.observed_at.isoformat()}"
        ),
        source=snapshot.source,
        record_type="defi_yield",
        observed_at=snapshot.observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def test_validation_ledger_upsert_load_round_trip(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    approved = _validation_evidence()
    blocked = _validation_evidence(
        run_id="validation-run-002",
        approved=False,
        walk_forward_split_count=0,
        walk_forward_pass_rate=0.0,
        blocked_reasons=["insufficient_walk_forward_splits"],
    )

    assert ledger.upsert_evidence([approved, blocked]) == 2
    assert ledger.upsert_evidence([approved, blocked]) == 2

    loaded = ledger.load_evidence(strategy_family="funding_extremity_price_confirmation")
    assert loaded == [approved, blocked]
    assert ledger.load_evidence(run_id="validation-run-001") == [approved]
    assert ledger.load_evidence(symbol="BTC/USDT") == [approved, blocked]


def test_validation_ledger_stores_canonical_evidence_id(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ledger = ValidationEvidenceLedger(db_path)
    evidence = _validation_evidence()

    ledger.upsert_evidence([evidence])

    with sqlite3.connect(db_path) as connection:
        [(stored_evidence_id,)] = connection.execute(
            "SELECT evidence_id FROM validation_evidence"
        ).fetchall()
    assert stored_evidence_id == evidence.evidence_id


def test_validation_ledger_allows_same_canonical_evidence_across_runs(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    first = _validation_evidence(run_id="run-a")
    second = _validation_evidence(run_id="run-b")
    assert first.evidence_id == second.evidence_id

    assert ledger.upsert_evidence([first, second]) == 2

    assert ledger.load_evidence(run_id="run-a") == [first]
    assert ledger.load_evidence(run_id="run-b") == [second]


def test_replace_run_evidence_replaces_entire_target_run_only(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    target_old = _validation_evidence(run_id="run-a", symbol="BTC/USDT")
    other_run_same_family = _validation_evidence(run_id="run-b", symbol="ETH/USDT")
    target_other_family = _validation_evidence(
        run_id="run-a",
        strategy_family="mean_reversion",
        symbol="SOL/USDT",
        validator_name="mean_reversion_validator",
    )
    replacement = _validation_evidence(
        run_id="run-a",
        symbol="XRP/USDT",
        trade_count=5,
        net_return=0.04,
    )
    ledger.upsert_evidence([target_old, other_run_same_family, target_other_family])

    assert ledger.replace_run_evidence("run-a", [replacement]) == 1

    assert ledger.load_evidence(run_id="run-a") == [replacement]
    assert ledger.load_evidence(run_id="run-b") == [other_run_same_family]


def test_replace_run_evidence_removes_stale_families_for_same_run(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    target_old = _validation_evidence(run_id="run-a", symbol="BTC/USDT")
    target_other_family = _validation_evidence(
        run_id="run-a",
        strategy_family="mean_reversion",
        symbol="SOL/USDT",
        validator_name="mean_reversion_validator",
    )
    replacement = _validation_evidence(
        run_id="run-a",
        symbol="XRP/USDT",
        trade_count=5,
        net_return=0.04,
    )
    ledger.upsert_evidence([target_old, target_other_family])

    assert ledger.replace_run_evidence("run-a", [replacement]) == 1

    loaded = ledger.load_evidence(run_id="run-a")
    assert loaded == [replacement]
    assert {item.strategy_family for item in loaded} == {
        "funding_extremity_price_confirmation"
    }


def test_replace_run_evidence_with_empty_items_clears_target_run_only(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    target = _validation_evidence(run_id="run-a", symbol="BTC/USDT")
    other_run = _validation_evidence(run_id="run-b", symbol="ETH/USDT")
    ledger.upsert_evidence([target, other_run])

    assert ledger.replace_run_evidence("run-a", []) == 0

    assert ledger.load_evidence(run_id="run-a") == []
    assert ledger.load_evidence(run_id="run-b") == [other_run]


def test_load_evidence_normalizes_whitespace_filters(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    evidence = _validation_evidence()
    ledger.upsert_evidence([evidence])

    assert ledger.load_evidence(run_id=" validation-run-001 ") == [evidence]
    assert ledger.load_evidence(strategy_family="   ") == []


def test_validation_ledger_reports_incompatible_schema_without_run_id(tmp_path):
    db_path = tmp_path / "research.sqlite"
    evidence = _validation_evidence()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE validation_evidence (
                evidence_id TEXT PRIMARY KEY,
                strategy_family TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                approved INTEGER NOT NULL,
                blocked_reasons_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                inserted_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO validation_evidence (
                evidence_id,
                strategy_family,
                symbol,
                timeframe,
                approved,
                blocked_reasons_json,
                payload_json,
                inserted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.strategy_family,
                evidence.symbol,
                evidence.timeframe,
                int(evidence.approved),
                "[]",
                evidence.model_dump_json(),
                datetime.now(tz=UTC).isoformat(),
            ),
        )

    try:
        ValidationEvidenceLedger(db_path)
    except ValueError as exc:
        assert "validation_evidence schema is incompatible" in str(exc)
    else:
        raise AssertionError("expected incompatible validation_evidence schema error")


def test_validation_ledger_reports_incompatible_legacy_schema_with_missing_columns(tmp_path):
    db_path = tmp_path / "research.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE validation_evidence (
                evidence_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                PRIMARY KEY (evidence_id)
            )
            """
        )

    with pytest.raises(ValueError, match="validation_evidence schema is incompatible"):
        ValidationEvidenceLedger(db_path)


def test_validation_ledger_persists_blocked_reasons(tmp_path):
    ledger = ValidationEvidenceLedger(tmp_path / "research.sqlite")
    blocked = _validation_evidence(
        approved=False,
        walk_forward_split_count=0,
        walk_forward_pass_rate=0.0,
        blocked_reasons=["insufficient_trades", "insufficient_walk_forward_splits"],
    )

    ledger.upsert_evidence([blocked])

    loaded = ledger.load_evidence(run_id="validation-run-001")
    assert loaded[0].approved is False
    assert loaded[0].blocked_reasons == (
        "insufficient_trades",
        "insufficient_walk_forward_splits",
    )


def test_research_loop_writes_registered_strategy_validation_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        run_id="research-validation-run",
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
    )

    loaded = ValidationEvidenceLedger(db_path).load_evidence(run_id="research-validation-run")
    assert len(loaded) == 1
    assert loaded[0].run_id == "research-validation-run"
    assert loaded[0].strategy_family == "funding_extremity_price_confirmation"
    assert loaded[0].symbol == "BTC/USDT"
    assert loaded[0].timeframe == "1h"
    assert loaded[0].approved is (report.validation_summaries[0].status == "passed")
    assert loaded[0].blocked_reasons == tuple(report.validation_summaries[0].blocked_reasons)


def test_research_loop_does_not_persist_approved_watchlist_validation_without_walk_forward(
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    store.upsert_records(
        [
            _defi_yield_record(
                DefiYieldSnapshot(
                    source="defillama",
                    chain="Ethereum",
                    project="aave-v3",
                    symbol="USDC",
                    tvl_usd=1_000_000.0,
                    apy=3.0,
                    observed_at=now - timedelta(hours=1),
                    raw={"pool": "Ethereum Aave/V3:USDC"},
                )
            ),
            _defi_yield_record(
                DefiYieldSnapshot(
                    source="defillama",
                    chain="Ethereum",
                    project="aave-v3",
                    symbol="USDC",
                    tvl_usd=1_000_000.0,
                    apy=5.0,
                    observed_at=now,
                    raw={"pool": "Ethereum Aave/V3:USDC"},
                )
            ),
        ]
    )

    report = run_stored_research_loop(
        db_path,
        run_id="defi-watchlist-validation-run",
        include_validation=True,
        strategy_family="defi_yield_regime_watchlist",
    )

    loaded = ValidationEvidenceLedger(db_path).load_evidence(
        run_id="defi-watchlist-validation-run"
    )
    assert len(report.validation_summaries) == 1
    assert report.validation_summaries[0].strategy_family == "defi_yield_regime_watchlist"
    assert loaded == []


def test_research_loop_does_not_write_unknown_strategy_validation_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        run_id="unknown-strategy-validation-run",
        include_validation=True,
        strategy_family="unknown",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
    )

    assert len(report.validation_summaries) == 1
    assert report.validation_summaries[0].validator_name == "unknown"
    assert report.validation_summaries[0].blocked_reasons == ["unknown_strategy_family"]
    assert (
        ValidationEvidenceLedger(db_path).load_evidence(
            run_id="unknown-strategy-validation-run"
        )
        == []
    )


def test_research_loop_does_not_write_unknown_strategy_with_missing_params(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        run_id="unknown-strategy-missing-params-run",
        include_validation=True,
        strategy_family="unknown",
    )

    assert len(report.validation_summaries) == 1
    assert report.validation_summaries[0].validator_name == "unknown"
    assert report.validation_summaries[0].blocked_reasons == ["unknown_strategy_family"]
    assert (
        ValidationEvidenceLedger(db_path).load_evidence(
            run_id="unknown-strategy-missing-params-run"
        )
        == []
    )


def test_research_loop_unknown_strategy_clears_stale_validation_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)
    run_id = "reused-validation-run"

    run_stored_research_loop(
        db_path,
        run_id=run_id,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
    )
    assert ValidationEvidenceLedger(db_path).load_evidence(run_id=run_id)

    run_stored_research_loop(
        db_path,
        run_id=run_id,
        include_validation=True,
        strategy_family="unknown",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
    )

    assert ValidationEvidenceLedger(db_path).load_evidence(run_id=run_id) == []


def test_research_loop_unknown_strategy_with_missing_params_clears_stale_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)
    run_id = "reused-validation-run"

    run_stored_research_loop(
        db_path,
        run_id=run_id,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
    )
    assert ValidationEvidenceLedger(db_path).load_evidence(run_id=run_id)

    run_stored_research_loop(
        db_path,
        run_id=run_id,
        include_validation=True,
        strategy_family="unknown",
    )

    assert ValidationEvidenceLedger(db_path).load_evidence(run_id=run_id) == []


def test_baseline_validation_does_not_write_validation_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle(0, 100.0).to_source_record(),
            _candle(1, 101.0).to_source_record(),
            _candle(2, 102.0).to_source_record(),
        ]
    )

    report = run_stored_research_loop(db_path, include_validation=True)

    assert report.validation_summaries
    assert all(summary.baseline_only for summary in report.validation_summaries)
    assert ValidationEvidenceLedger(db_path).load_evidence() == []


def test_baseline_validation_clears_stale_validation_evidence_for_reused_run(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)
    run_id = "reused-baseline-validation-run"

    run_stored_research_loop(
        db_path,
        run_id=run_id,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
    )
    assert ValidationEvidenceLedger(db_path).load_evidence(run_id=run_id)

    report = run_stored_research_loop(
        db_path,
        run_id=run_id,
        include_validation=True,
    )

    assert report.validation_summaries
    assert all(summary.baseline_only for summary in report.validation_summaries)
    assert ValidationEvidenceLedger(db_path).load_evidence(run_id=run_id) == []


def test_validation_ledger_migrates_legacy_payload_without_run_id_from_table_column(
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    evidence = _validation_evidence()
    payload = evidence.model_dump(mode="json", exclude={"run_id"})
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE validation_evidence (
                evidence_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                strategy_family TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                approved INTEGER NOT NULL,
                blocked_reasons_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                inserted_at TEXT NOT NULL,
                PRIMARY KEY (evidence_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO validation_evidence (
                evidence_id,
                run_id,
                strategy_family,
                symbol,
                timeframe,
                approved,
                blocked_reasons_json,
                payload_json,
                inserted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.run_id,
                evidence.strategy_family,
                evidence.symbol,
                evidence.timeframe,
                int(evidence.approved),
                "[]",
                json.dumps(payload, sort_keys=True),
                datetime.now(tz=UTC).isoformat(),
            ),
        )

    ledger = ValidationEvidenceLedger(db_path)

    assert ledger.load_evidence(run_id=evidence.run_id) == [evidence]


def test_validation_ledger_rejects_legacy_payload_with_mismatched_run_id(
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    evidence = _validation_evidence()
    payload = evidence.model_dump(mode="json")
    payload["run_id"] = "different-run-id"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE validation_evidence (
                evidence_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                strategy_family TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                approved INTEGER NOT NULL,
                blocked_reasons_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                inserted_at TEXT NOT NULL,
                PRIMARY KEY (evidence_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO validation_evidence (
                evidence_id,
                run_id,
                strategy_family,
                symbol,
                timeframe,
                approved,
                blocked_reasons_json,
                payload_json,
                inserted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.run_id,
                evidence.strategy_family,
                evidence.symbol,
                evidence.timeframe,
                int(evidence.approved),
                "[]",
                json.dumps(payload, sort_keys=True),
                datetime.now(tz=UTC).isoformat(),
            ),
        )

    with pytest.raises(ValueError, match="payload run_id does not match table run_id"):
        ValidationEvidenceLedger(db_path)


def test_research_loop_normalizes_strategy_family_before_validation(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        run_id="whitespace-strategy-validation-run",
        include_validation=True,
        strategy_family=" funding_extremity_price_confirmation ",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
    )

    loaded = ValidationEvidenceLedger(db_path).load_evidence(
        run_id="whitespace-strategy-validation-run"
    )
    assert len(report.validation_summaries) == 1
    assert report.validation_summaries[0].strategy_family == (
        "funding_extremity_price_confirmation"
    )
    assert len(loaded) == 1
    assert loaded[0].strategy_family == "funding_extremity_price_confirmation"
