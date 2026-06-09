from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.data.models import (
    DataSuitability,
    DefiYieldSnapshot,
    DexPairSnapshot,
    MarketCandle,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


START = datetime(2026, 5, 1, tzinfo=UTC)
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
SCREEN_IDS = [
    "short_horizon_momentum_volatility_filter",
    "short_horizon_reversal_volatility_filter",
    "perp_spot_basis_funding_deviation",
    "derivatives_crowding_price_action",
    "defi_dex_regime_discovery",
    "cross_asset_ranking_turnover_cap",
    "regime_gated_cross_asset_momentum",
    "regime_gated_cross_asset_reversal",
    "funding_basis_convergence_liquidity_filter",
    "derivatives_crowding_recent_window_price_action",
    "defi_dex_liquidity_regime_watchlist",
]
REQUIRED_BLOCKED_REASONS = {
    "insufficient_universe_coverage",
    "insufficient_samples",
    "insufficient_walk_forward_splits",
    "non_positive_cost_adjusted_expectancy",
    "unstable_walk_forward_performance",
    "cost_sensitivity_fragile",
    "excessive_turnover",
    "single_asset_or_time_window_dependency",
    "lookahead_risk",
    "watchlist_only_source",
}


def test_multi_hypothesis_lab_reports_all_candidate_gates_read_only(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_directional_market_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        MULTI_HYPOTHESIS_BLOCKED_REASONS,
        build_multi_hypothesis_feasibility_report,
    )

    before = _record_snapshot(db_path)
    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0, 20.0, 50.0],
        min_split_count=3,
    )

    assert set(MULTI_HYPOTHESIS_BLOCKED_REASONS) >= REQUIRED_BLOCKED_REASONS
    assert report.command == "strategy-feasibility"
    assert report.mode == "multi-hypothesis-lab"
    assert report.symbols == SYMBOLS
    assert report.current_capital_usd == 300.0
    assert report.cost_bps_grid == [5.0, 10.0, 20.0, 50.0]
    assert report.universe.symbols == SYMBOLS
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert [metric.candidate for metric in report.candidate_metrics] == SCREEN_IDS

    by_candidate = {metric.candidate: metric for metric in report.candidate_metrics}
    momentum = by_candidate["short_horizon_momentum_volatility_filter"]
    assert momentum.sample_count > 0
    assert set(momentum.asset_coverage) == set(SYMBOLS)
    assert all(count > 0 for count in momentum.asset_coverage.values())
    assert momentum.split_coverage >= 3
    assert momentum.gross_mean > momentum.net_mean > 0
    assert 0 <= momentum.win_rate <= 1
    assert momentum.turnover >= 0
    assert set(momentum.selected_symbol_counts) == {"BTC/USDT", "ETH/USDT"}
    assert sum(momentum.selected_symbol_counts.values()) == momentum.sample_count
    assert [metric.cost_bps for metric in momentum.cost_sensitivity] == [
        5.0,
        10.0,
        20.0,
        50.0,
    ]
    assert all(split.net_mean > 0 for split in momentum.split_metrics)
    assert momentum.reason_codes == []
    assert momentum.candidate_state_target == "feasibility_passed"

    derivatives = by_candidate["derivatives_crowding_price_action"]
    assert derivatives.readiness == "blocked"
    assert "insufficient_universe_coverage" in derivatives.reason_codes
    assert derivatives.sample_count == 0
    assert derivatives.cost_sensitivity == []
    assert derivatives.candidate_state_target == "candidate"

    assert _record_snapshot(db_path) == before
    assert not memory_path.exists()


def test_multi_hypothesis_lab_blocks_single_asset_dependency(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_single_asset_momentum_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0, 20.0, 50.0],
        min_split_count=3,
        candidates=["short_horizon_momentum_volatility_filter"],
    )

    metric = report.candidate_metrics[0]
    assert set(metric.asset_coverage) == set(SYMBOLS)
    assert metric.selected_symbol_counts == {"BTC/USDT": metric.sample_count}
    assert metric.readiness == "blocked"
    assert "single_asset_or_time_window_dependency" in metric.reason_codes
    assert metric.candidate_state_target == "redesign_required"


def test_multi_hypothesis_lab_fails_closed_for_future_watchlist_data(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    evaluation_end = START + timedelta(hours=90)
    future = evaluation_end + timedelta(days=2)
    _seed_directional_market_candles(db_path, count=100)
    ResearchDataStore(db_path).upsert_records(
        [
            _dex_pair("BTC", "USDT", future),
            _defi_yield("USDT", future),
            _source_health("dexscreener", "pairs", future),
            _source_health("defillama", "yield_pools", future),
            _source_health("binance_public", "um_futures_ohlcv", future),
        ]
    )

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0, 20.0, 50.0],
        min_split_count=3,
        candidates=["defi_dex_regime_discovery"],
        evaluation_start=START,
        evaluation_end=evaluation_end,
    )

    assert report.readiness == "blocked"
    assert "lookahead_risk" in report.reason_codes
    assert "watchlist_only_source" in report.reason_codes
    assert report.universe.point_in_time_universe is False
    metric = report.candidate_metrics[0]
    assert metric.candidate == "defi_dex_regime_discovery"
    assert metric.readiness == "blocked"
    assert "lookahead_risk" in metric.reason_codes
    assert "watchlist_only_source" in metric.reason_codes
    assert metric.candidate_state_target == "redesign_required"
    assert metric.sample_count == 0


def test_multi_hypothesis_lab_blocks_cost_sensitive_candidates(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_weak_market_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0, 20.0, 50.0],
        min_split_count=3,
        candidates=["short_horizon_momentum_volatility_filter"],
    )

    metric = report.candidate_metrics[0]
    assert metric.sample_count > 0
    assert metric.cost_sensitivity[0].cost_bps == 5.0
    assert metric.cost_sensitivity[0].net_mean > 0
    assert metric.cost_sensitivity[-1].cost_bps == 50.0
    assert metric.cost_sensitivity[-1].net_mean <= 0
    assert metric.readiness == "blocked"
    assert "cost_sensitivity_fragile" in metric.reason_codes
    assert metric.candidate_state_target == "redesign_required"


def test_multi_hypothesis_lab_cost_aware_filter_reduces_low_edge_turnover(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_mixed_edge_market_candles(db_path, count=160)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=159))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    unfiltered_report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[10.0],
        min_split_count=1,
        candidates=["short_horizon_momentum_volatility_filter"],
        feasibility_version="v2",
    )
    filtered_report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[10.0],
        min_split_count=1,
        candidates=["short_horizon_momentum_volatility_filter"],
        feasibility_version="v2",
        cost_aware_execution=True,
        min_edge_over_cost_multiplier=2.0,
    )

    unfiltered = unfiltered_report.candidate_metrics[0]
    filtered = filtered_report.candidate_metrics[0]
    assert filtered_report.validation_policy.cost_aware_execution is True
    assert filtered_report.validation_policy.min_edge_over_cost_multiplier == 2.0
    assert filtered.raw_sample_count == unfiltered.sample_count
    assert 0 < filtered.sample_count < filtered.raw_sample_count
    assert filtered.cost_aware_sample_count == filtered.sample_count
    assert filtered.cost_threshold == pytest.approx(0.002)
    assert filtered.cost_sensitivity[0].cost_bps == 10.0
    assert filtered.cost_sensitivity[0].cost_threshold == pytest.approx(0.002)


def test_multi_hypothesis_lab_blocks_when_cost_aware_filter_removes_samples(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_low_edge_market_candles(db_path, count=100)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=99))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[10.0],
        min_split_count=3,
        candidates=["short_horizon_momentum_volatility_filter"],
        feasibility_version="v2",
        cost_aware_execution=True,
        min_edge_over_cost_multiplier=2.0,
    )

    metric = report.candidate_metrics[0]
    assert metric.raw_sample_count > 0
    assert metric.sample_count == 0
    assert metric.cost_aware_sample_count == 0
    assert metric.readiness == "blocked"
    assert "insufficient_samples" in metric.reason_codes


def test_multi_hypothesis_lab_blocks_excessive_turnover(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_alternating_ranking_market_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0],
        min_split_count=1,
        candidates=["cross_asset_ranking_turnover_cap"],
        feasibility_version="v2",
        max_turnover=0.05,
    )

    metric = report.candidate_metrics[0]
    assert report.validation_policy.max_turnover == 0.05
    assert metric.turnover > 0.05
    assert metric.readiness == "blocked"
    assert "excessive_turnover" in metric.reason_codes
    assert metric.candidate_state_target == "redesign_required"


def test_multi_hypothesis_lab_does_not_count_same_timestamp_symbol_fanout_as_turnover(
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_directional_market_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0],
        min_split_count=1,
        candidates=["short_horizon_momentum_volatility_filter"],
        feasibility_version="v2",
        max_turnover=0.5,
    )

    metric = report.candidate_metrics[0]
    assert set(metric.selected_symbol_counts) == {"BTC/USDT", "ETH/USDT"}
    assert metric.turnover == pytest.approx(0.0)
    assert "excessive_turnover" not in metric.reason_codes


def test_multi_hypothesis_lab_evaluates_regime_gated_market_screens(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_directional_market_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0],
        min_split_count=3,
        candidates=["regime_gated_cross_asset_momentum"],
        feasibility_version="v2",
        purge_gap_bars=2,
        min_unique_months=1,
        min_asset_count=1,
    )

    metric = report.candidate_metrics[0]
    assert metric.candidate == "regime_gated_cross_asset_momentum"
    assert metric.sample_count > 0
    assert "insufficient_samples" not in metric.reason_codes
    assert metric.multiple_testing_adjusted is True


def test_multi_hypothesis_lab_v2_reports_policy_month_gates_and_multiple_testing(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    _seed_directional_market_candles(db_path, count=140)
    _seed_source_health(db_path, observed_at=START + timedelta(hours=139))

    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        build_multi_hypothesis_feasibility_report,
    )

    report = build_multi_hypothesis_feasibility_report(
        db_path,
        memory_path=memory_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0],
        min_split_count=3,
        candidates=["short_horizon_momentum_volatility_filter"],
        feasibility_version="v2",
        purge_gap_bars=2,
        requested_months=[(2026, 5), (2026, 6)],
        min_unique_months=2,
        min_asset_count=2,
    )

    assert report.validation_policy.version == "v2"
    assert report.validation_policy.purge_gap_bars == 2
    assert report.validation_policy.min_unique_months == 2
    assert report.validation_policy.min_asset_count == 2
    assert report.multiple_testing_summary.evaluated_candidate_count == 1
    assert report.multiple_testing_summary.feasible_candidate_count == 0
    assert report.multiple_testing_summary.blocked_candidate_count == 1
    assert report.readiness == "blocked"
    assert "insufficient_month_coverage" in report.reason_codes
    assert "insufficient_asset_coverage" in report.reason_codes

    metric = report.candidate_metrics[0]
    assert metric.unique_months == 1
    assert metric.single_month_dependency is True
    assert metric.multiple_testing_adjusted is True
    assert "insufficient_month_coverage" in metric.reason_codes
    assert "insufficient_asset_coverage" in metric.reason_codes
    assert all(split.purge_gap_bars == 2 for split in metric.split_metrics)
    assert all(split.train_observations >= 0 for split in metric.split_metrics)


def test_multi_hypothesis_models_are_strict():
    from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
        CandidateFeasibilityMetric,
        CostSensitivityMetric,
        MultiHypothesisFeasibilityReport,
    )

    with pytest.raises(ValidationError):
        CostSensitivityMetric(cost_bps="5", gross_mean=0.01, net_mean=0.009)

    with pytest.raises(ValidationError):
        CandidateFeasibilityMetric(
            candidate="short_horizon_momentum_volatility_filter",
            readiness="blocked",
            sample_count=0,
            asset_coverage={},
            split_coverage=0,
            gross_mean=None,
            net_mean=None,
            win_rate=None,
            turnover=0.0,
            selected_symbol_counts={},
            cost_sensitivity=[],
            split_metrics=[],
            reason_codes=["insufficient_samples"],
            candidate_state_target="candidate",
            unexpected="not allowed",
        )

    with pytest.raises(ValidationError):
        MultiHypothesisFeasibilityReport(
            command="strategy-feasibility",
            mode="multi-hypothesis-lab",
            generated_at=START,
            timeframe="1h",
            symbols=["BTC/USDT"],
            current_capital_usd=300.0,
            cost_bps_grid=[5.0, 10.0, 20.0, 50.0],
            readiness="blocked",
            reason_codes=[],
            universe={},
            candidate_metrics=[],
            uses_real_capital=False,
            live_order_routing=False,
            extra_field="not allowed",
        )


def _seed_directional_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 2.0
            elif symbol == "ETH/USDT":
                close = 200.0 + index * 5.0
            else:
                close = 80.0 - index * 0.03
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _seed_single_asset_momentum_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 1.0
            elif symbol == "ETH/USDT":
                close = 200.0 - index * 0.05
            else:
                close = 80.0 - index * 0.03
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _seed_weak_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 0.08
            elif symbol == "ETH/USDT":
                close = 200.0 - index * 0.02
            else:
                close = 80.0 - index * 0.01
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _seed_mixed_edge_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                if index < count // 2:
                    close = 100.0 + index * 0.004
                else:
                    close = 100.0 + (count // 2) * 0.004 + (index - count // 2) * 0.6
            elif symbol == "ETH/USDT":
                if index < count // 2:
                    close = 200.0 + index * 0.003
                else:
                    close = 200.0 + (count // 2) * 0.003 + (index - count // 2) * 0.4
            else:
                close = 80.0 - index * 0.01
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _seed_low_edge_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 0.004
            elif symbol == "ETH/USDT":
                close = 200.0 + index * 0.003
            else:
                close = 80.0 - index * 0.01
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _seed_alternating_ranking_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if index < 72:
                close = 100.0 if symbol != "SOL/USDT" else 90.0
            elif symbol == "BTC/USDT":
                close = 110.0 if index % 2 == 0 else 101.0
            elif symbol == "ETH/USDT":
                close = 101.0 if index % 2 == 0 else 110.0
            else:
                close = 90.0
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _seed_source_health(db_path, *, observed_at: datetime) -> None:
    ResearchDataStore(db_path).upsert_records(
        [_source_health("binance_public", "um_futures_ohlcv", observed_at)]
    )


def _market_candle(symbol: str, index: int, *, close: float) -> SourceRecord:
    return MarketCandle(
        source="binance_public",
        venue="binance_usdm",
        symbol=symbol,
        timestamp=START + timedelta(hours=index),
        timeframe="1h",
        open=close,
        high=close * 1.001,
        low=close * 0.999,
        close=close,
        volume=10_000.0 + index,
        suitability=DataSuitability(),
    ).to_source_record()


def _dex_pair(base_token: str, quote_token: str, observed_at: datetime) -> SourceRecord:
    snapshot = DexPairSnapshot(
        source="dexscreener",
        chain="ethereum",
        dex="uniswap",
        pair_address=f"0x{base_token.lower()}",
        base_token=base_token,
        quote_token=quote_token,
        price_usd=100.0,
        liquidity_usd=50_000.0,
        volume_24h_usd=20_000.0,
        observed_at=observed_at,
    )
    return SourceRecord(
        record_id=f"dexscreener:{base_token}:{quote_token}:{observed_at.isoformat()}",
        source="dexscreener",
        record_type="dex_pair",
        observed_at=observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _defi_yield(symbol: str, observed_at: datetime) -> SourceRecord:
    snapshot = DefiYieldSnapshot(
        source="defillama",
        chain="ethereum",
        project="example",
        symbol=symbol,
        tvl_usd=1_000_000.0,
        apy=5.0,
        observed_at=observed_at,
    )
    return SourceRecord(
        record_id=f"defillama:{symbol}:{observed_at.isoformat()}",
        source="defillama",
        record_type="defi_yield",
        observed_at=observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _source_health(
    source: str,
    feed: str,
    observed_at: datetime,
    *,
    success: bool = True,
) -> SourceRecord:
    return SourceRecord(
        record_id=f"{source}:{feed}:source_health:{observed_at.isoformat()}",
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "success": success,
            "attempts": 1,
            "failure": None if success else "probe failed",
            "observed_at": observed_at.isoformat(),
            "records_fetched": 1,
            "records_written": 1,
            "network_route": "direct",
        },
    )


def _record_snapshot(db_path) -> dict[str, dict[str, object]]:
    return {
        record.record_id: record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records()
    }
