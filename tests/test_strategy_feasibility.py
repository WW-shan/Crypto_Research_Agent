from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import (
    BasisRecord,
    LongShortRatioRecord,
    MarketCandle,
    PremiumIndexKlineRecord,
    SourceRecord,
    TakerBuySellVolumeRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
START = datetime(2026, 1, 1, tzinfo=UTC)


def test_large_liquid_momentum_feasibility_produces_walk_forward_metrics(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=430)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    before = _record_snapshot(db_path)
    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.command == "strategy-feasibility"
    assert report.mode == "large-liquid-momentum-regime"
    assert report.readiness == "feasible"
    assert len(report.split_metrics) >= 3
    assert all(metric.test_observations > 0 for metric in report.split_metrics)
    assert all(metric.cost_adjusted_return_mean > 0 for metric in report.split_metrics)
    assert report.derivatives_record_counts == {
        "basis": 0,
        "long_short_account_ratio": 0,
        "premium_index_kline": 0,
        "taker_buy_sell_volume": 0,
    }
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert _record_snapshot(db_path) == before


def test_large_liquid_momentum_feasibility_blocks_insufficient_aligned_history(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=60)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.readiness == "blocked"
    assert "insufficient_aligned_history" in report.reason_codes
    assert report.split_metrics == []


def test_large_liquid_momentum_feasibility_keeps_metrics_when_expectancy_blocks(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_flat_market_candles(db_path, count=430)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in report.reason_codes
    assert len(report.split_metrics) >= 3
    assert all(metric.cost_adjusted_return_mean <= 0 for metric in report.split_metrics)


def test_large_liquid_momentum_feasibility_rejects_invalid_min_split_count(tmp_path):
    db_path = tmp_path / "research.sqlite"

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    with pytest.raises(ValueError, match="min_split_count"):
        build_large_liquid_momentum_feasibility_report(
            db_path,
            symbols=SYMBOLS,
            timeframe="1h",
            current_capital_usd=300,
            min_split_count=0,
        )


def test_derivatives_conditioned_lab_blocks_missing_derivatives_history(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=120)

    before = _record_snapshot(db_path)
    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.command == "strategy-feasibility"
    assert report.mode == "derivatives-conditioned-lab"
    assert report.readiness == "blocked"
    assert "insufficient_derivatives_history" in report.reason_codes
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert len(report.candidate_metrics) == 1
    metric = report.candidate_metrics[0]
    assert metric.candidate == "long_short_crowding_contrarian"
    assert metric.readiness == "blocked"
    assert "insufficient_derivatives_history" in metric.reason_codes
    assert metric.gross_return_mean is None
    assert metric.cost_adjusted_return_mean is None
    assert metric.win_rate is None
    assert metric.split_metrics == []
    assert _record_snapshot(db_path) == before


def test_derivatives_conditioned_lab_rejects_invalid_min_split_count(tmp_path):
    db_path = tmp_path / "research.sqlite"

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    with pytest.raises(ValueError, match="min_split_count"):
        build_derivatives_conditioned_lab_report(
            db_path,
            symbols=SYMBOLS,
            timeframe="1h",
            current_capital_usd=300,
            derivatives_period="1h",
            candidates=["long_short_crowding_contrarian"],
            min_split_count=0,
        )


def test_derivatives_conditioned_lab_keeps_metrics_when_expectancy_blocks(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_flat_market_candles(db_path, count=160)
    _seed_derivatives_context(
        db_path,
        count=160,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in report.reason_codes
    assert len(report.candidate_metrics) == 1
    metric = report.candidate_metrics[0]
    assert metric.candidate == "long_short_crowding_contrarian"
    assert metric.readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in metric.reason_codes
    assert len(metric.split_metrics) >= 3
    assert all(split.cost_adjusted_return_mean <= 0 for split in metric.split_metrics)


def test_derivatives_conditioned_lab_blocks_insufficient_split_observations(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_directional_market_candles(db_path, count=30)
    _seed_derivatives_context(
        db_path,
        count=30,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "blocked"
    assert "insufficient_walk_forward_splits" in report.reason_codes
    metric = report.candidate_metrics[0]
    assert metric.readiness == "blocked"
    assert "insufficient_walk_forward_splits" in metric.reason_codes
    assert 0 < metric.observations < 6
    assert len(metric.split_metrics) == 3
    assert all(split.test_observations > 0 for split in metric.split_metrics)


def test_derivatives_conditioned_lab_reports_passing_and_rejected_candidates(tmp_path):
    db_path = tmp_path / "research.sqlite"
    requested_candidates = [
        "long_short_crowding_contrarian",
        "taker_imbalance_reversal",
    ]
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
        taker_ratios={
            "BTCUSDT": 1.35,
            "ETHUSDT": 1.30,
            "SOLUSDT": 1.25,
        },
    )

    before = _record_snapshot(db_path)
    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=requested_candidates,
        min_split_count=3,
    )

    actual_candidates = [metric.candidate for metric in report.candidate_metrics]
    assert actual_candidates == requested_candidates
    by_candidate = {metric.candidate: metric for metric in report.candidate_metrics}
    long_short_metric = by_candidate["long_short_crowding_contrarian"]
    taker_metric = by_candidate["taker_imbalance_reversal"]
    assert report.readiness == "feasible"
    assert report.reason_codes == []
    assert long_short_metric.readiness == "feasible"
    assert len(long_short_metric.split_metrics) >= 3
    assert all(
        split.test_observations > 0 for split in long_short_metric.split_metrics
    )
    assert all(
        split.cost_adjusted_return_mean > 0
        for split in long_short_metric.split_metrics
    )
    assert long_short_metric.observations > 0
    assert long_short_metric.selected_symbol_counts
    assert "BTC/USDT" in long_short_metric.selected_symbol_counts
    assert taker_metric.readiness == "blocked"
    assert "non_positive_cost_adjusted_expectancy" in taker_metric.reason_codes
    assert len(taker_metric.split_metrics) >= 3
    assert all(split.test_observations > 0 for split in taker_metric.split_metrics)
    assert all(
        split.cost_adjusted_return_mean <= 0 for split in taker_metric.split_metrics
    )
    assert taker_metric.observations > 0
    assert taker_metric.selected_symbol_counts
    assert _record_snapshot(db_path) == before


def test_derivatives_conditioned_lab_expands_default_candidates_and_coverage(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
        taker_ratios={
            "BTCUSDT": 1.35,
            "ETHUSDT": 1.30,
            "SOLUSDT": 1.25,
        },
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        min_split_count=3,
    )

    assert [metric.candidate for metric in report.candidate_metrics] == [
        "long_short_crowding_contrarian",
        "taker_imbalance_reversal",
        "premium_basis_risk_filter",
        "momentum_derivatives_confirmation",
    ]
    assert [item.symbol for item in report.coverage] == SYMBOLS
    for item in report.coverage:
        assert item.derivatives_symbol == item.symbol.replace("/", "")
        assert item.premium_index_kline_records > 0
        assert item.basis_records > 0
        assert item.long_short_account_ratio_records > 0
        assert item.taker_buy_sell_volume_records > 0
        assert item.aligned_records > 0
    assert report.derivatives_record_counts["premium_index_kline"] > 0
    assert report.derivatives_record_counts["basis"] > 0
    assert report.derivatives_record_counts["long_short_account_ratio"] > 0
    assert report.derivatives_record_counts["taker_buy_sell_volume"] > 0


def test_derivatives_conditioned_lab_honors_derivatives_period_filter(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=180)
    _seed_derivatives_context(db_path, count=180)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="4h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.derivatives_period == "4h"
    assert report.derivatives_symbols == {
        symbol: symbol.replace("/", "") for symbol in SYMBOLS
    }
    assert report.readiness == "blocked"
    assert "insufficient_derivatives_history" in report.reason_codes
    assert [metric.candidate for metric in report.candidate_metrics] == [
        "long_short_crowding_contrarian"
    ]
    metric = report.candidate_metrics[0]
    assert metric.readiness == "blocked"
    assert "insufficient_derivatives_history" in metric.reason_codes
    assert metric.split_metrics == []
    assert [item.symbol for item in report.coverage] == SYMBOLS
    for item in report.coverage:
        assert item.derivatives_symbol == item.symbol.replace("/", "")
        assert item.market_records > 0
        assert item.premium_index_kline_records == 0
        assert item.basis_records == 0
        assert item.long_short_account_ratio_records == 0
        assert item.taker_buy_sell_volume_records == 0
        assert item.aligned_records == 0
        assert "insufficient_derivatives_history" in item.blocked_reasons


def test_derivatives_conditioned_lab_preserves_requested_symbol_subset_order(tmp_path):
    db_path = tmp_path / "research.sqlite"
    requested_symbols = ["SOL/USDT", "BTC/USDT"]
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
        taker_ratios={
            "BTCUSDT": 1.35,
            "ETHUSDT": 1.30,
            "SOLUSDT": 1.25,
        },
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=requested_symbols,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.symbols == requested_symbols
    assert report.derivatives_symbols == {
        "SOL/USDT": "SOLUSDT",
        "BTC/USDT": "BTCUSDT",
    }
    assert [item.symbol for item in report.coverage] == requested_symbols
    assert report.readiness == "feasible"
    assert report.reason_codes == []
    assert [metric.candidate for metric in report.candidate_metrics] == [
        "long_short_crowding_contrarian"
    ]
    metric = report.candidate_metrics[0]
    assert metric.readiness == "feasible"
    assert metric.reason_codes == []
    assert metric.observations > 0
    assert metric.selected_symbol_counts
    assert set(metric.selected_symbol_counts) <= set(requested_symbols)
    assert "ETH/USDT" not in metric.selected_symbol_counts
    assert len(metric.split_metrics) >= 3
    assert all(split.test_observations > 0 for split in metric.split_metrics)


def test_large_liquid_momentum_feasibility_blocks_duplicate_timestamps(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=430)
    duplicate = _candle("BTC/USDT", 10, close=110.0).to_source_record()
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"{duplicate.record_id}:duplicate",
                source=duplicate.source,
                record_type=duplicate.record_type,
                observed_at=duplicate.observed_at,
                payload=duplicate.payload,
            )
        ]
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.readiness == "blocked"
    assert "duplicate_timestamps" in report.reason_codes
    assert any("duplicate_timestamps" in item.blocked_reasons for item in report.symbol_reports)


def test_derivatives_conditioned_lab_blocks_duplicate_timestamps(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )
    duplicate = _candle("BTC/USDT", 10, close=110.0).to_source_record()
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"{duplicate.record_id}:duplicate",
                source=duplicate.source,
                record_type=duplicate.record_type,
                observed_at=duplicate.observed_at,
                payload=duplicate.payload,
            )
        ]
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "blocked"
    assert "duplicate_timestamps" in report.reason_codes
    actual_candidates = [metric.candidate for metric in report.candidate_metrics]
    assert actual_candidates == ["long_short_crowding_contrarian"]
    metric = report.candidate_metrics[0]
    assert metric.readiness == "blocked"
    assert "duplicate_timestamps" in metric.reason_codes
    assert metric.split_metrics == []
    coverage_by_symbol = {item.symbol: item for item in report.coverage}
    btc_coverage = coverage_by_symbol["BTC/USDT"]
    assert btc_coverage.duplicate_timestamps == 1
    assert "duplicate_timestamps" in btc_coverage.blocked_reasons


def test_derivatives_conditioned_lab_blocks_duplicate_derivatives_timestamps(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )
    duplicate = LongShortRatioRecord(
        source="binance_usdm",
        venue="binance",
        symbol="BTCUSDT",
        period="1h",
        timestamp=START + timedelta(hours=10),
        long_short_ratio=0.55,
        long_account=0.55 / 1.55,
        short_account=1.0 - 0.55 / 1.55,
        raw={"fixture": "duplicate_long_short"},
    ).to_source_record()
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"{duplicate.record_id}:duplicate",
                source=duplicate.source,
                record_type=duplicate.record_type,
                observed_at=duplicate.observed_at,
                payload=duplicate.payload,
            )
        ]
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "blocked"
    assert "duplicate_timestamps" in report.reason_codes
    metric = report.candidate_metrics[0]
    assert metric.readiness == "blocked"
    assert "duplicate_timestamps" in metric.reason_codes
    assert metric.observations == 0
    assert metric.split_metrics == []
    coverage_by_symbol = {item.symbol: item for item in report.coverage}
    btc_coverage = coverage_by_symbol["BTC/USDT"]
    assert btc_coverage.duplicate_timestamps == 1
    assert "duplicate_timestamps" in btc_coverage.blocked_reasons


def test_derivatives_conditioned_lab_ignores_non_perpetual_basis_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )
    delivery_basis = BasisRecord(
        source="binance_usdm",
        venue="binance",
        pair="BTCUSDT",
        contract_type="CURRENT_QUARTER",
        period="1h",
        timestamp=START + timedelta(hours=10),
        index_price=100.0,
        futures_price=100.1,
        basis=0.1,
        basis_rate=0.001,
        annualized_basis_rate=None,
        raw={"fixture": "delivery_basis"},
    ).to_source_record()
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"{delivery_basis.record_id}:delivery",
                source=delivery_basis.source,
                record_type=delivery_basis.record_type,
                observed_at=delivery_basis.observed_at,
                payload=delivery_basis.payload,
            )
        ]
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "feasible"
    assert "duplicate_timestamps" not in report.reason_codes
    coverage_by_symbol = {item.symbol: item for item in report.coverage}
    btc_coverage = coverage_by_symbol["BTC/USDT"]
    assert btc_coverage.basis_records == 180
    assert btc_coverage.duplicate_timestamps == 0
    assert "duplicate_timestamps" not in btc_coverage.blocked_reasons
    assert report.derivatives_record_counts["basis"] == 541


def test_derivatives_conditioned_lab_blocks_ambiguous_derivatives_symbol_mapping(
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    requested_symbols = ["BTC/USDT", "ETH/USDT"]
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_derivatives_conditioned_lab_report,
    )

    report = build_derivatives_conditioned_lab_report(
        db_path,
        symbols=requested_symbols,
        timeframe="1h",
        current_capital_usd=300,
        derivatives_symbols={
            "BTC/USDT": "BTCUSDT",
            "ETH/USDT": "BTCUSDT",
        },
        derivatives_period="1h",
        candidates=["long_short_crowding_contrarian"],
        min_split_count=3,
    )

    assert report.readiness == "blocked"
    assert "ambiguous_derivatives_symbol_mapping" in report.reason_codes
    metric = report.candidate_metrics[0]
    assert metric.readiness == "blocked"
    assert "ambiguous_derivatives_symbol_mapping" in metric.reason_codes
    assert metric.observations == 0
    assert metric.split_metrics == []
    assert [item.symbol for item in report.coverage] == requested_symbols
    assert all(
        "ambiguous_derivatives_symbol_mapping" in item.blocked_reasons
        for item in report.coverage
    )


def test_strategy_feasibility_cli_writes_markdown_and_json(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "feasibility.md"
    json_out = tmp_path / "feasibility.json"
    _seed_market_candles(db_path, count=430)

    exit_code = main(
        [
            "strategy-feasibility",
            "--db",
            str(db_path),
            "--mode",
            "large-liquid-momentum-regime",
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["command"] == "strategy-feasibility"
    assert payload["report"]["readiness"] == "feasible"
    assert json_payload["report"]["uses_real_capital"] is False
    assert json_payload["report"]["live_order_routing"] is False
    assert "Large Liquid Momentum" in out_path.read_text(encoding="utf-8")


def test_strategy_feasibility_cli_writes_derivatives_lab_markdown_and_json(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "derivatives-lab.md"
    json_out = tmp_path / "derivatives-lab.json"
    _seed_directional_market_candles(db_path, count=180)
    _seed_derivatives_context(
        db_path,
        count=180,
        long_short_ratios={
            "BTCUSDT": 0.55,
            "ETHUSDT": 1.10,
            "SOLUSDT": 1.08,
        },
    )

    before = _record_snapshot(db_path)
    exit_code = main(
        [
            "strategy-feasibility",
            "--db",
            str(db_path),
            "--mode",
            "derivatives-conditioned-lab",
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--derivatives-period",
            "1h",
            "--candidate",
            "long_short_crowding_contrarian",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = out_path.read_text(encoding="utf-8")
    expected_candidates = ["long_short_crowding_contrarian"]
    assert exit_code == 0
    assert payload["command"] == "strategy-feasibility"
    assert payload["report"] == json_payload["report"]
    assert payload["report"]["mode"] == "derivatives-conditioned-lab"
    assert payload["report"]["readiness"] == "feasible"
    assert payload["report"]["uses_real_capital"] is False
    assert payload["report"]["live_order_routing"] is False
    assert (
        [metric["candidate"] for metric in payload["report"]["candidate_metrics"]]
        == expected_candidates
    )
    assert (
        [metric["candidate"] for metric in json_payload["report"]["candidate_metrics"]]
        == expected_candidates
    )
    metric = payload["report"]["candidate_metrics"][0]
    assert metric["readiness"] == "feasible"
    assert metric["reason_codes"] == []
    assert metric["observations"] > 0
    assert len(metric["split_metrics"]) >= 3
    assert all(split["test_observations"] > 0 for split in metric["split_metrics"])
    assert "Derivatives-Conditioned Feasibility Lab" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown
    assert "long_short_crowding_contrarian" in markdown
    assert _record_snapshot(db_path) == before


def _seed_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol_index, symbol in enumerate(SYMBOLS):
        base = 100.0 + symbol_index * 50.0
        drift = 0.35 - symbol_index * 0.08
        for index in range(count):
            close = base + index * drift
            records.append(_candle(symbol, index, close=close).to_source_record())
    ResearchDataStore(db_path).upsert_records(records)


def _seed_flat_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol_index, symbol in enumerate(SYMBOLS):
        close = 100.0 + symbol_index * 50.0
        for index in range(count):
            records.append(_candle(symbol, index, close=close).to_source_record())
    ResearchDataStore(db_path).upsert_records(records)


def _candle(symbol: str, index: int, *, close: float) -> MarketCandle:
    return MarketCandle(
        source="unit_test",
        venue="binance",
        symbol=symbol,
        timestamp=START + timedelta(hours=index),
        timeframe="1h",
        open=close * 0.999,
        high=close * 1.001,
        low=close * 0.998,
        close=close,
        volume=10_000.0 + index,
    )


def _seed_directional_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 0.5
            elif symbol == "ETH/USDT":
                close = 200.0 - index * 0.1
            else:
                close = 50.0 - index * 0.05
            records.append(_candle(symbol, index, close=close).to_source_record())
    ResearchDataStore(db_path).upsert_records(records)


def _seed_derivatives_context(
    db_path,
    *,
    count: int,
    long_short_ratios: dict[str, float] | None = None,
    taker_ratios: dict[str, float] | None = None,
    premium_values: dict[str, float] | None = None,
    basis_rates: dict[str, float] | None = None,
) -> None:
    derivative_symbols = [symbol.replace("/", "") for symbol in SYMBOLS]
    long_short_ratios = long_short_ratios or {
        symbol: 1.0 for symbol in derivative_symbols
    }
    taker_ratios = taker_ratios or {symbol: 1.0 for symbol in derivative_symbols}
    premium_values = premium_values or {symbol: 0.0 for symbol in derivative_symbols}
    basis_rates = basis_rates or {symbol: 0.0 for symbol in derivative_symbols}
    records = []
    for symbol in derivative_symbols:
        for index in range(count):
            timestamp = START + timedelta(hours=index)
            long_short_ratio = long_short_ratios[symbol]
            long_account = long_short_ratio / (1.0 + long_short_ratio)
            short_account = 1.0 - long_account
            taker_ratio = taker_ratios[symbol]
            records.extend(
                [
                    LongShortRatioRecord(
                        source="binance_usdm",
                        venue="binance",
                        symbol=symbol,
                        period="1h",
                        timestamp=timestamp,
                        long_short_ratio=long_short_ratio,
                        long_account=long_account,
                        short_account=short_account,
                        raw={"fixture": "long_short"},
                    ).to_source_record(),
                    TakerBuySellVolumeRecord(
                        source="binance_usdm",
                        venue="binance",
                        symbol=symbol,
                        period="1h",
                        timestamp=timestamp,
                        buy_sell_ratio=taker_ratio,
                        buy_volume=100.0 * taker_ratio,
                        sell_volume=100.0,
                        raw={"fixture": "taker"},
                    ).to_source_record(),
                    PremiumIndexKlineRecord(
                        source="binance_usdm",
                        venue="binance",
                        symbol=symbol,
                        timestamp=timestamp,
                        interval="1h",
                        open=premium_values[symbol],
                        high=premium_values[symbol],
                        low=premium_values[symbol],
                        close=premium_values[symbol],
                        raw={"fixture": "premium"},
                    ).to_source_record(),
                    BasisRecord(
                        source="binance_usdm",
                        venue="binance",
                        pair=symbol,
                        contract_type="PERPETUAL",
                        period="1h",
                        timestamp=timestamp,
                        index_price=100.0,
                        futures_price=100.0 * (1.0 + basis_rates[symbol]),
                        basis=100.0 * basis_rates[symbol],
                        basis_rate=basis_rates[symbol],
                        annualized_basis_rate=None,
                        raw={"fixture": "basis"},
                    ).to_source_record(),
                ]
            )
    ResearchDataStore(db_path).upsert_records(records)


def _record_snapshot(db_path) -> dict[str, dict[str, object]]:
    return {
        record.record_id: record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records()
    }
