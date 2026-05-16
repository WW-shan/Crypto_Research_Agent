from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger


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


def _write_happy_path_fixture(tmp_path):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])
    ]
    fundings = [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([_funding_record(item) for item in fundings])
    return db_path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "crypto_alpha_agent.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_run_paper_sim_loop_writes_outcomes_without_live_capital(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-test",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=1_000.0,
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=2,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-test")

    assert report.run_id == "paper-test"
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.notional_usd == 25.0
    assert report.validation.trade_count == 3
    assert report.outcome_count == 3
    assert len(report.outcomes) == report.outcome_count
    assert len(loaded) == report.outcome_count
    assert [item.outcome_id for item in loaded] == [item.outcome_id for item in report.outcomes]
    assert {item.status for item in loaded} == {"closed"}
    assert all(item.touched_real_capital is False for item in loaded)
    assert all(item.live_order_routing is False for item in loaded)
    assert all(item.notional_usd == 25.0 for item in loaded)

    first = loaded[0]
    assert first.signal_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert first.entry_price == 103.0
    assert first.exit_price == 99.0
    assert first.quantity == pytest.approx(25.0 / 103.0)
    assert first.gross_pnl_usd == pytest.approx(25.0 * (4.0 / 103.0))
    assert first.fees_usd == pytest.approx(25.0 * 0.001 * 2.0)
    assert first.slippage_usd == pytest.approx(25.0 * 0.0005 * 2.0)
    assert first.net_pnl_usd == pytest.approx(first.gross_pnl_usd - first.fees_usd - first.slippage_usd)

    assert len(report.paper_evidence_packages) == 1
    evidence = report.paper_evidence_packages[0]
    assert evidence.strategy_family == "funding_extremity_price_confirmation"
    assert evidence.sample_size == report.outcome_count
    assert evidence.closed_count == report.outcome_count
    assert evidence.failed_count == 0
    assert evidence.net_pnl_usd == pytest.approx(sum(item.net_pnl_usd for item in loaded))


def test_paper_sim_loop_keeps_existing_outcome_ids_stable_after_backfill(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100])
    ]
    initial_fundings = [_funding(3, -0.0009), _funding(5, 0.0008)]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([_funding_record(item) for item in initial_fundings])

    first_report = run_paper_sim_loop(
        db_path,
        run_id="paper-backfill",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=1,
        min_trades=2,
        require_walk_forward=False,
    )
    first_ids_by_signal = {
        outcome.signal_timestamp: outcome.outcome_id for outcome in first_report.outcomes
    }

    store.upsert_records([_funding_record(_funding(1, 0.0007))])
    second_report = run_paper_sim_loop(
        db_path,
        run_id="paper-backfill",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=1,
        min_trades=2,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-backfill")
    second_ids_by_signal = {
        outcome.signal_timestamp: outcome.outcome_id for outcome in second_report.outcomes
    }

    assert second_report.outcome_count == 3
    assert len(loaded) == 3
    assert set(first_ids_by_signal).issubset(second_ids_by_signal)
    for signal_timestamp, outcome_id in first_ids_by_signal.items():
        assert second_ids_by_signal[signal_timestamp] == outcome_id
    assert {outcome.outcome_id for outcome in loaded} == {
        outcome.outcome_id for outcome in second_report.outcomes
    }
    assert second_report.paper_evidence_packages[0].sample_size == 3
    assert second_report.paper_evidence_packages[0].closed_count == 3


def test_empty_store_records_one_blocked_no_signal_outcome(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-empty",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=100.0,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-empty")

    assert report.outcome_count == 1
    assert len(loaded) == 1
    outcome = loaded[0]
    assert outcome.status == "blocked"
    assert outcome.failure_reasons[0] == "no_signal"
    assert "insufficient_price_bars" in outcome.failure_reasons
    assert "insufficient_funding_samples" in outcome.failure_reasons
    assert outcome.entry_price == 0.0
    assert outcome.exit_price == 0.0
    assert outcome.quantity == 0.0
    assert outcome.notional_usd == 0.0
    assert outcome.gross_pnl_usd == 0.0
    assert outcome.fees_usd == 0.0
    assert outcome.slippage_usd == 0.0
    assert outcome.net_pnl_usd == 0.0
    assert outcome.touched_real_capital is False
    assert outcome.live_order_routing is False
    assert report.paper_evidence_packages[0].failed_count == 1
    assert "no_signal" in report.paper_evidence_packages[0].failure_reasons


def test_run_paper_sim_loop_rejects_unsupported_strategy_family(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    with pytest.raises(ValueError, match="unsupported strategy_family"):
        run_paper_sim_loop(
            db_path,
            strategy_family="latency_arbitrage",
            price_symbol="BTC/USDT",
            funding_symbol="BTC/USDT:USDT",
            timeframe="1h",
        )


def test_cli_paper_sim_loop_outputs_json_and_persists_ledger(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)
    report_path = tmp_path / "paper-report.json"

    result = _run_cli(
        "paper-sim-loop",
        "--db",
        str(db_path),
        "--strategy-family",
        "funding_extremity_price_confirmation",
        "--price-symbol",
        "BTC/USDT",
        "--funding-symbol",
        "BTC/USDT:USDT",
        "--timeframe",
        "1h",
        "--run-id",
        "cli-paper",
        "--current-capital-usd",
        "30",
        "--notional-usd",
        "100",
        "--threshold-abs",
        "0.0005",
        "--hold-bars",
        "2",
        "--fee-rate",
        "0.001",
        "--slippage-rate",
        "0.0005",
        "--min-trades",
        "2",
        "--no-require-walk-forward",
        "--report-out",
        str(report_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="cli-paper")
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["command"] == "paper-sim-loop"
    assert payload["mode"] == "paper_simulation_only"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["report"]["run_id"] == "cli-paper"
    assert payload["report"]["outcome_count"] == 3
    assert payload["report"]["notional_usd"] == 25.0
    assert len(loaded) == payload["report"]["outcome_count"]
    assert report_payload == payload


def test_cli_paper_sim_loop_accepts_zero_capital_and_notional(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)

    result = _run_cli(
        "paper-sim-loop",
        "--db",
        str(db_path),
        "--strategy-family",
        "funding_extremity_price_confirmation",
        "--price-symbol",
        "BTC/USDT",
        "--funding-symbol",
        "BTC/USDT:USDT",
        "--timeframe",
        "1h",
        "--run-id",
        "cli-paper-zero",
        "--current-capital-usd",
        "0",
        "--notional-usd",
        "0",
        "--threshold-abs",
        "0.0005",
        "--hold-bars",
        "2",
        "--min-trades",
        "2",
        "--no-require-walk-forward",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["report"]["run_id"] == "cli-paper-zero"
    assert payload["report"]["notional_usd"] == 0.0
    assert payload["report"]["outcome_count"] == 3
    assert {
        outcome["status"] for outcome in payload["report"]["outcomes"]
    } == {"closed"}
    assert all(
        outcome["quantity"] == 0.0
        and outcome["notional_usd"] == 0.0
        and outcome["gross_pnl_usd"] == 0.0
        and outcome["fees_usd"] == 0.0
        and outcome["slippage_usd"] == 0.0
        and outcome["net_pnl_usd"] == 0.0
        for outcome in payload["report"]["outcomes"]
    )
