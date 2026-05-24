from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore


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


def _approved_validation_payload() -> dict[str, object]:
    return {
        "strategy_family": "funding_extremity_price_confirmation",
        "validator_name": "fake_registry_validator",
        "approved": True,
        "blocked_reasons": [],
        "metrics": {"trade_count": 1},
    }


def _paper_trade_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "funding_symbol": "BTC/USDT:USDT",
        "funding_timestamp": "2026-05-17T01:00:00+00:00",
        "entry_timestamp": "2026-05-17T02:00:00+00:00",
        "exit_timestamp": "2026-05-17T03:00:00+00:00",
        "entry_price": 100.0,
        "exit_price": 101.0,
        "raw_return": 0.01,
        "direction": "long",
    }
    payload.update(overrides)
    return payload


def _patch_paper_registry(monkeypatch: pytest.MonkeyPatch, report) -> None:
    class FakeRegistry:
        def run_paper(self, request):
            return report

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.paper_sim_loop.default_strategy_registry",
        lambda **_: FakeRegistry(),
    )


def _simulated_paper_report(*trades: dict[str, object]):
    from crypto_alpha_agent.strategy.models import StrategyPaperReport

    return StrategyPaperReport(
        strategy_family="funding_extremity_price_confirmation",
        status="simulated",
        supports_paper_simulation=True,
        blocked_reasons=[],
        metrics={
            "validation": _approved_validation_payload(),
            "paper_trades": list(trades),
            "observed_at": "2026-05-17T03:00:00+00:00",
        },
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
    assert report.validation.metrics["trade_count"] == 3
    assert report.outcome_count == 3
    assert len(report.outcomes) == report.outcome_count
    assert len(loaded) == report.outcome_count
    assert [item.outcome_id for item in loaded] == [item.outcome_id for item in report.outcomes]
    assert {item.status for item in loaded} == {"closed"}
    assert all(item.touched_real_capital is False for item in loaded)
    assert all(item.live_order_routing is False for item in loaded)
    assert all(0 < item.notional_usd <= 25.0 for item in loaded)
    assert all(item.cost_model_mode == "pessimistic" for item in loaded)
    assert all(item.venue == "binance" for item in loaded)
    assert all(item.fee_model_id.startswith("binance:") for item in loaded)
    assert all(item.stale_signal_status == "fresh" for item in loaded)
    assert all(item.fill_status == "full" for item in loaded)

    first = loaded[0]
    assert first.signal_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert first.entry_price == 103.0
    assert first.exit_price == 99.0
    assert first.quantity == pytest.approx(first.notional_usd / 103.0)
    assert first.gross_pnl_usd == pytest.approx(first.notional_usd * (4.0 / 103.0))
    assert first.fees_usd == pytest.approx(first.entry_fee_usd + first.exit_fee_usd)
    assert first.fees_usd == pytest.approx(first.notional_usd * 0.001 * 2.0)
    assert first.slippage_usd == pytest.approx(first.notional_usd * 0.0005 * 2.0)
    assert first.net_pnl_usd == pytest.approx(first.gross_pnl_usd - first.fees_usd - first.slippage_usd)

    assert len(report.paper_evidence_packages) == 1
    evidence = report.paper_evidence_packages[0]
    assert evidence.strategy_family == "funding_extremity_price_confirmation"
    assert evidence.sample_size == report.outcome_count
    assert evidence.closed_count == report.outcome_count
    assert evidence.failed_count == 0
    assert evidence.net_pnl_usd == pytest.approx(sum(item.net_pnl_usd for item in loaded))
    assert evidence.total_fees_usd == pytest.approx(sum(item.fees_usd for item in loaded))
    assert evidence.total_slippage_usd == pytest.approx(sum(item.slippage_usd for item in loaded))


def test_paper_sim_loop_filters_records_by_observed_window(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)
    start = datetime(2026, 5, 17, 0, tzinfo=UTC)
    end = datetime(2026, 5, 17, 4, tzinfo=UTC)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-window",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=1,
        min_trades=1,
        require_walk_forward=False,
        observed_at_start=start,
        observed_at_end=end,
    )

    assert report.outcome_count == 1
    assert report.outcomes[0].signal_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert all(outcome.signal_timestamp < end for outcome in report.outcomes)
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_paper_sim_loop_can_return_report_without_persisting_outcomes(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-not-persisted",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=1,
        min_trades=1,
        require_walk_forward=False,
        persist_outcomes=False,
    )

    assert report.outcome_count >= 1
    assert PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-not-persisted") == []


def test_run_paper_sim_loop_blocks_when_min_notional_exceeds_owner_profile(tmp_path, monkeypatch):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)
    _patch_paper_registry(monkeypatch, _simulated_paper_report(_paper_trade_payload()))

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-min-notional-block",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        min_notional_usd=30.0,
        require_walk_forward=False,
    )

    assert report.outcome_count == 1
    outcome = report.outcomes[0]
    assert outcome.status == "blocked"
    assert outcome.cost_model_mode == "pessimistic"
    assert outcome.fill_status == "blocked"
    assert "min_notional_exceeds_max_notional" in outcome.failure_reasons


def test_run_paper_sim_loop_blocks_stale_signal_even_when_validation_approved(tmp_path, monkeypatch):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)
    stale_trade = _paper_trade_payload(
        funding_timestamp="2026-05-17T01:00:00+00:00",
        entry_timestamp="2026-05-17T03:00:00+00:00",
        exit_timestamp="2026-05-17T04:00:00+00:00",
    )
    _patch_paper_registry(monkeypatch, _simulated_paper_report(stale_trade))

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-stale-signal-block",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        max_signal_age_seconds=60.0,
        require_walk_forward=False,
    )

    outcome = report.outcomes[0]
    assert outcome.status == "blocked"
    assert outcome.stale_signal_status == "stale"
    assert outcome.signal_age_seconds == pytest.approx(7200.0)
    assert "stale_signal" in outcome.failure_reasons


def test_run_paper_sim_loop_records_partial_fill_when_enabled(tmp_path, monkeypatch):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)
    partial_trade = _paper_trade_payload(entry_volume=1.0, exit_volume=1.0)
    _patch_paper_registry(monkeypatch, _simulated_paper_report(partial_trade))

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-partial-fill",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        max_volume_participation_rate=0.10,
        allow_partial_fills=True,
        require_walk_forward=False,
    )

    outcome = report.outcomes[0]
    assert outcome.status == "closed"
    assert outcome.fill_status == "partial"
    assert 0 < outcome.fill_ratio < 1
    assert outcome.notional_usd == pytest.approx(10.0)
    assert outcome.quantity == pytest.approx(0.1)


def test_run_paper_sim_loop_blocks_missed_fill_when_liquidity_is_too_low(tmp_path, monkeypatch):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)
    low_liquidity_trade = _paper_trade_payload(entry_volume=0.01, exit_volume=0.01)
    _patch_paper_registry(monkeypatch, _simulated_paper_report(low_liquidity_trade))

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-missed-fill",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        max_volume_participation_rate=0.10,
        require_walk_forward=False,
    )

    outcome = report.outcomes[0]
    assert outcome.status == "blocked"
    assert outcome.fill_status == "missed"
    assert "missed_fill_assumed" in outcome.failure_reasons
    assert report.paper_evidence_packages[0].missed_fill_count == 1


def test_run_paper_sim_loop_blocks_positive_gross_pnl_erased_by_costs(tmp_path, monkeypatch):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)
    pre_cost_only_trade = _paper_trade_payload(raw_return=0.001)
    _patch_paper_registry(monkeypatch, _simulated_paper_report(pre_cost_only_trade))

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-pre-cost-only-block",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        require_walk_forward=False,
    )

    outcome = report.outcomes[0]
    assert outcome.status == "blocked"
    assert outcome.cost_model_mode == "pessimistic"
    assert outcome.gross_pnl_usd > 0
    assert outcome.net_pnl_usd <= 0
    assert not any(item.status == "closed" for item in report.outcomes)
    assert "pre_cost_only_profitable" in outcome.failure_reasons


def test_run_paper_sim_loop_forwards_stale_source_gate_to_registry(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-stale-source",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
        now=datetime(2026, 5, 24, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert report.validation.approved is False
    assert "stale_source" in report.validation.blocked_reasons
    assert {outcome.status for outcome in report.outcomes} == {"blocked"}


def test_run_paper_sim_loop_stable_ids_include_result_changing_stale_gate(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    first = run_paper_sim_loop(
        _write_happy_path_fixture(tmp_path / "first"),
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
    )
    second = run_paper_sim_loop(
        _write_happy_path_fixture(tmp_path / "second"),
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
        now=datetime(2026, 5, 24, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert first.run_id != second.run_id
    assert first.outcomes[0].candidate_id != second.outcomes[0].candidate_id


def test_run_paper_sim_loop_stable_ids_include_cost_model_assumptions(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    first = run_paper_sim_loop(
        _write_happy_path_fixture(tmp_path / "first-cost"),
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
        cost_model_mode="pessimistic",
    )
    second = run_paper_sim_loop(
        _write_happy_path_fixture(tmp_path / "second-cost"),
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
        cost_model_mode="base",
    )

    assert first.run_id != second.run_id
    assert first.outcomes[0].candidate_id != second.outcomes[0].candidate_id


def test_run_paper_sim_loop_blocks_outcomes_when_validation_not_approved(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="paper-validation-blocked",
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
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-validation-blocked")

    assert report.validation.approved is False
    assert "insufficient_walk_forward_splits" in report.validation.blocked_reasons
    assert report.outcome_count == 1
    assert len(loaded) == 1
    assert {outcome.status for outcome in report.outcomes} == {"blocked"}
    assert {outcome.status for outcome in loaded} == {"blocked"}
    outcome = loaded[0]
    assert outcome.notional_usd == 0.0
    assert outcome.net_pnl_usd == 0.0
    assert outcome.failure_reasons == tuple(report.validation.blocked_reasons)
    assert "insufficient_walk_forward_splits" in outcome.failure_reasons
    assert outcome.cost_model_mode == "pessimistic"
    assert outcome.venue == "binance"
    assert outcome.fee_model_id.startswith("binance:")
    assert outcome.taker_fee_rate > 0
    assert outcome.applied_entry_fee_rate == pytest.approx(0.001)
    assert outcome.applied_exit_fee_rate == pytest.approx(0.001)
    assert outcome.slippage_bps == pytest.approx(5.0)
    assert outcome.stale_signal_status == "not_evaluated"
    assert outcome.fill_status == "blocked"
    assert "insufficient_walk_forward_splits" in report.notes
    assert outcome.touched_real_capital is False
    assert outcome.live_order_routing is False

    evidence = report.paper_evidence_packages[0]
    assert evidence.closed_count == 0
    assert evidence.blocked_count == 1
    assert evidence.failed_count == 1
    assert "insufficient_walk_forward_splits" in evidence.failure_reasons


def test_run_paper_sim_loop_replaces_closed_outcomes_when_rerun_blocks(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    first_report = run_paper_sim_loop(
        db_path,
        run_id="paper-validation-rerun",
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
    other_report = run_paper_sim_loop(
        db_path,
        run_id="paper-other-run",
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
    second_report = run_paper_sim_loop(
        db_path,
        run_id="paper-validation-rerun",
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
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-validation-rerun")
    other_loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-other-run")

    assert {outcome.status for outcome in first_report.outcomes} == {"closed"}
    assert second_report.validation.approved is False
    assert {outcome.status for outcome in second_report.outcomes} == {"blocked"}
    assert [outcome.outcome_id for outcome in loaded] == [
        outcome.outcome_id for outcome in second_report.outcomes
    ]
    assert {outcome.status for outcome in loaded} == {"blocked"}
    assert {outcome.outcome_id for outcome in first_report.outcomes}.isdisjoint(
        {outcome.outcome_id for outcome in loaded}
    )
    assert [outcome.outcome_id for outcome in other_loaded] == [
        outcome.outcome_id for outcome in other_report.outcomes
    ]


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


def test_paper_sim_loop_replaces_same_signal_after_price_correction(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records(
        [
            _candle(0, 100).to_source_record(),
            _candle(1, 103).to_source_record(),
            _candle(2, 101).to_source_record(),
            _candle(3, 99).to_source_record(),
        ]
    )
    store.upsert_records([_funding_record(_funding(1, 0.0008))])

    first_report = run_paper_sim_loop(
        db_path,
        run_id="paper-corrected-price",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=1,
        min_trades=1,
        require_walk_forward=False,
    )

    store.upsert_records([_candle(2, 100).to_source_record()])
    second_report = run_paper_sim_loop(
        db_path,
        run_id="paper-corrected-price",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=1,
        min_trades=1,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-corrected-price")

    assert first_report.outcome_count == 1
    assert second_report.outcome_count == 1
    assert second_report.outcomes[0].exit_price == 100.0
    assert len(loaded) == second_report.outcome_count
    assert loaded[0].outcome_id == second_report.outcomes[0].outcome_id
    assert second_report.outcomes[0].outcome_id == first_report.outcomes[0].outcome_id


def test_auto_run_id_changes_with_notional_to_keep_outcomes_distinct(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    low_notional_report = run_paper_sim_loop(
        db_path,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
    )
    high_notional_report = run_paper_sim_loop(
        db_path,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=20.0,
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes()

    assert low_notional_report.run_id != high_notional_report.run_id
    assert {outcome.outcome_id for outcome in low_notional_report.outcomes}.isdisjoint(
        {outcome.outcome_id for outcome in high_notional_report.outcomes}
    )
    assert len(loaded) == (
        low_notional_report.outcome_count + high_notional_report.outcome_count
    )


def test_manual_run_id_replaces_previous_outcomes_when_parameters_change(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    low_notional_report = run_paper_sim_loop(
        db_path,
        run_id="paper-manual-sizing",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
    )
    high_notional_report = run_paper_sim_loop(
        db_path,
        run_id="paper-manual-sizing",
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=20.0,
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=2,
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id="paper-manual-sizing")

    assert low_notional_report.run_id == high_notional_report.run_id
    assert {outcome.outcome_id for outcome in low_notional_report.outcomes}.isdisjoint(
        {outcome.outcome_id for outcome in high_notional_report.outcomes}
    )
    assert len(loaded) == high_notional_report.outcome_count
    assert {outcome.outcome_id for outcome in loaded} == {
        outcome.outcome_id for outcome in high_notional_report.outcomes
    }
    assert all(0 < outcome.notional_usd <= 20.0 for outcome in loaded)


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
    assert outcome.cost_model_mode == "pessimistic"
    assert outcome.venue == "binance"
    assert outcome.fee_model_id.startswith("binance:")
    assert outcome.applied_entry_fee_rate == pytest.approx(0.001)
    assert outcome.applied_exit_fee_rate == pytest.approx(0.001)
    assert outcome.slippage_bps == pytest.approx(5.0)
    assert outcome.stale_signal_status == "not_evaluated"
    assert outcome.fill_status == "blocked"
    assert outcome.touched_real_capital is False
    assert outcome.live_order_routing is False
    assert report.paper_evidence_packages[0].failed_count == 1
    assert "insufficient_price_bars" in report.paper_evidence_packages[0].failure_reasons


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


def test_run_paper_sim_loop_blocks_mean_reversion_when_registry_paper_gate_blocks(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_happy_path_fixture(tmp_path)

    report = run_paper_sim_loop(
        db_path,
        run_id="mean-reversion-registry-blocked",
        strategy_family="funding_mean_reversion_after_extreme",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=24.99,
        notional_usd=10.0,
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
        require_walk_forward=False,
    )

    assert report.outcome_count == 1
    outcome = report.outcomes[0]
    assert outcome.status == "blocked"
    assert outcome.failure_reasons == ("insufficient_current_capital",)
    assert outcome.notional_usd == 0.0


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
        "--venue",
        "binance",
        "--cost-model-mode",
        "pessimistic",
        "--max-signal-age-seconds",
        "3600",
        "--min-notional-usd",
        "5",
        "--quantity-step",
        "0.001",
        "--tick-size",
        "0.1",
        "--max-volume-participation-rate",
        "0.05",
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
    assert payload["report"]["venue"] == "binance"
    assert payload["report"]["cost_model_mode"] == "pessimistic"
    assert payload["report"]["max_signal_age_seconds"] == 3600.0
    assert len(loaded) == payload["report"]["outcome_count"]
    assert all(outcome.cost_model_mode == "pessimistic" for outcome in loaded)
    assert all(outcome.venue == "binance" for outcome in loaded)
    assert report_payload == payload


def test_cli_paper_sim_loop_memory_writes_records_and_outputs_metadata(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)
    memory_path = tmp_path / "paper-memory.jsonl"

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
        "cli-paper-memory",
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
        "--memory",
        str(memory_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    records = MemoryStore(memory_path).list_records()

    assert "memory_records_written" in payload
    assert "memory_path" in payload
    assert payload["memory_records_written"] == 3
    assert payload["memory_path"] == str(memory_path)
    assert len(records) == payload["memory_records_written"]
    assert {record.paper_trade_outcome["run_id"] for record in records} == {"cli-paper-memory"}
    assert all(0 < record.opportunity["notional"] <= 25.0 for record in records)


def test_cli_paper_sim_loop_memory_replaces_same_run_records_when_rerun_blocks(tmp_path):
    db_path = _write_happy_path_fixture(tmp_path)
    memory_path = tmp_path / "paper-memory.jsonl"
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="research-loop:keep-me",
            hypothesis={"thesis": "unrelated memory must survive paper replacement"},
            tags=["research-loop"],
        )
    )

    common_args = [
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
        "--memory",
        str(memory_path),
    ]

    closed_result = _run_cli(
        *common_args,
        "--run-id",
        "cli-paper-memory-rerun",
        "--no-require-walk-forward",
    )
    assert closed_result.returncode == 0, closed_result.stderr
    closed_payload = json.loads(closed_result.stdout)
    closed_records = [
        record
        for record in MemoryStore(memory_path).list_records()
        if record.paper_trade_outcome is not None
        and record.paper_trade_outcome["run_id"] == "cli-paper-memory-rerun"
    ]
    assert {outcome["status"] for outcome in closed_payload["report"]["outcomes"]} == {"closed"}
    assert len(closed_records) == 3
    assert all(record.rejected_reasons == [] for record in closed_records)

    other_result = _run_cli(
        *common_args,
        "--run-id",
        "cli-paper-memory-other",
        "--no-require-walk-forward",
    )
    assert other_result.returncode == 0, other_result.stderr

    blocked_result = _run_cli(
        *common_args,
        "--run-id",
        "cli-paper-memory-rerun",
    )
    assert blocked_result.returncode == 0, blocked_result.stderr
    blocked_payload = json.loads(blocked_result.stdout)
    records = MemoryStore(memory_path).list_records()
    rerun_records = [
        record
        for record in records
        if record.paper_trade_outcome is not None
        and record.paper_trade_outcome["run_id"] == "cli-paper-memory-rerun"
    ]
    other_records = [
        record
        for record in records
        if record.paper_trade_outcome is not None
        and record.paper_trade_outcome["run_id"] == "cli-paper-memory-other"
    ]

    assert {outcome["status"] for outcome in blocked_payload["report"]["outcomes"]} == {
        "blocked"
    }
    assert len(rerun_records) == 1
    assert rerun_records[0].paper_trade_outcome["status"] == "blocked"
    assert "insufficient_walk_forward_splits" in rerun_records[0].rejected_reasons
    assert "insufficient_walk_forward_splits" in rerun_records[0].paper_trade_outcome[
        "failure_reasons"
    ]
    assert len(other_records) == 3
    assert {record.paper_trade_outcome["status"] for record in other_records} == {"closed"}
    assert MemoryStore(memory_path).get("research-loop:keep-me") is not None


@pytest.mark.parametrize(
    ("price_field", "run_id"),
    [
        ("entry_price", "paper-invalid-zero-entry"),
        ("exit_price", "paper-invalid-zero-exit"),
    ],
)
def test_run_paper_sim_loop_blocks_simulated_report_with_zero_trade_price(
    tmp_path,
    monkeypatch,
    price_field,
    run_id,
):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
    from crypto_alpha_agent.strategy.models import StrategyPaperReport

    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    report = StrategyPaperReport(
        strategy_family="funding_extremity_price_confirmation",
        status="simulated",
        supports_paper_simulation=True,
        blocked_reasons=[],
        metrics={
            "validation": _approved_validation_payload(),
            "paper_trades": [_paper_trade_payload(**{price_field: 0.0})],
            "observed_at": "2026-05-17T03:00:00+00:00",
        },
    )
    _patch_paper_registry(monkeypatch, report)

    loop_report = run_paper_sim_loop(
        db_path,
        run_id=run_id,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id=run_id)

    assert loop_report.validation.approved is False
    assert "paper_report_metrics_invalid" in loop_report.validation.blocked_reasons
    assert "metrics_error" in loop_report.validation.metrics
    assert loop_report.outcome_count == 1
    assert {outcome.status for outcome in loop_report.outcomes} == {"blocked"}
    assert {outcome.status for outcome in loaded} == {"blocked"}
    assert not any(outcome.status == "closed" for outcome in loaded)
    assert "paper_report_metrics_invalid" in loaded[0].failure_reasons


@pytest.mark.parametrize(
    ("metrics_override", "run_id"),
    [
        ({"observed_at": {"not": "a timestamp"}}, "paper-invalid-observed-at"),
        ({"validation": {"approved": True}}, "paper-invalid-validation"),
    ],
)
def test_run_paper_sim_loop_blocks_simulated_report_with_malformed_metrics(
    tmp_path,
    monkeypatch,
    metrics_override,
    run_id,
):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
    from crypto_alpha_agent.strategy.models import StrategyPaperReport

    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    metrics = {
        "validation": _approved_validation_payload(),
        "paper_trades": [_paper_trade_payload()],
        "observed_at": "2026-05-17T03:00:00+00:00",
    }
    metrics.update(metrics_override)
    report = StrategyPaperReport(
        strategy_family="funding_extremity_price_confirmation",
        status="simulated",
        supports_paper_simulation=True,
        blocked_reasons=[],
        metrics=metrics,
    )
    _patch_paper_registry(monkeypatch, report)

    loop_report = run_paper_sim_loop(
        db_path,
        run_id=run_id,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        require_walk_forward=False,
    )

    loaded = PaperOutcomeLedger(db_path).load_outcomes(run_id=run_id)

    assert loop_report.validation.approved is False
    assert "paper_report_metrics_invalid" in loop_report.validation.blocked_reasons
    assert "metrics_error" in loop_report.validation.metrics
    assert loop_report.outcome_count == 1
    assert len(loaded) == 1
    assert loaded[0].status == "blocked"
    assert "paper_report_metrics_invalid" in loaded[0].failure_reasons


def test_cli_paper_sim_loop_blocks_zero_capital_and_notional(tmp_path):
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
    assert payload["report"]["outcome_count"] == 1
    outcome = payload["report"]["outcomes"][0]
    assert outcome["status"] == "blocked"
    assert outcome["failure_reasons"] == ["insufficient_current_capital"]
    assert outcome["quantity"] == 0.0
    assert outcome["notional_usd"] == 0.0
    assert outcome["gross_pnl_usd"] == 0.0
    assert outcome["fees_usd"] == 0.0
    assert outcome["slippage_usd"] == 0.0
    assert outcome["net_pnl_usd"] == 0.0
