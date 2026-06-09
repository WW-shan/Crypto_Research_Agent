from __future__ import annotations

from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.memory.store import MemoryRecord
from crypto_alpha_agent.pipeline.evidence_universe import (
    EvidenceUniverseReport,
    UniverseAsset,
    UniverseSourceCoverage,
)
from crypto_alpha_agent.pipeline.multi_hypothesis_feasibility import (
    CandidateFeasibilityMetric,
    CostSensitivityMetric,
    FeasibilityValidationPolicy,
    MultiHypothesisFeasibilityReport,
    MultipleTestingSummary,
)


START = datetime(2026, 6, 8, tzinfo=UTC)
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
LEGACY_DERIVATIVES_CANDIDATES = {
    "long_short_crowding_contrarian",
    "taker_imbalance_reversal",
    "premium_basis_risk_filter",
    "momentum_derivatives_confirmation",
}


def test_persist_candidate_state_memory_records_candidate_transitions(tmp_path):
    memory_path = tmp_path / "candidate-memory.jsonl"

    from crypto_alpha_agent.pipeline.candidate_state_memory import (
        persist_candidate_state_memory,
    )

    records = persist_candidate_state_memory(
        _report(
            [
                _metric(
                    "derivatives_crowding_price_action",
                    reason_codes=["insufficient_universe_coverage"],
                    sample_count=0,
                ),
                _metric(
                    "perp_spot_basis_funding_deviation",
                    reason_codes=["insufficient_samples"],
                    sample_count=0,
                ),
                _metric("short_horizon_momentum_volatility_filter"),
                _metric(
                    "cross_asset_ranking_turnover_cap",
                    reason_codes=["cost_sensitivity_fragile"],
                ),
            ]
        ),
        memory_path,
        include_current_derivatives_rejections=False,
    )

    by_candidate = {
        record.opportunity["candidate_id"]: record for record in records
    }
    assert by_candidate["derivatives_crowding_price_action"].opportunity["state"] == "candidate"
    assert (
        by_candidate["perp_spot_basis_funding_deviation"].opportunity["state"]
        == "source_qualified"
    )
    assert (
        by_candidate["short_horizon_momentum_volatility_filter"].opportunity["state"]
        == "feasibility_passed"
    )
    assert by_candidate["cross_asset_ranking_turnover_cap"].opportunity["state"] == "redesign_required"

    feasible = by_candidate["short_horizon_momentum_volatility_filter"]
    assert feasible.record_id == "candidate-state:short_horizon_momentum_volatility_filter"
    assert feasible.opportunity["uses_real_capital"] is False
    assert feasible.opportunity["live_order_routing"] is False
    assert feasible.hypothesis["candidate_id"] == "short_horizon_momentum_volatility_filter"
    assert feasible.hypothesis["evidence_refs"] == [
        "strategy-feasibility:multi-hypothesis-lab",
        "timeframe:1h",
    ]
    assert feasible.hypothesis["reason_codes"] == []
    assert feasible.score["source_coverage"]["binance_public:market_candle:1h"][
        "records"
    ] == 360
    assert feasible.score["feasibility_summary"]["sample_count"] > 0
    assert feasible.score["last_seen_at"] == START.isoformat()
    assert set(feasible.tags) >= {
        "candidate-state",
        "short_horizon_momentum_volatility_filter",
        "feasibility_passed",
    }


def test_persist_candidate_state_memory_records_current_derivatives_rejections(tmp_path):
    memory_path = tmp_path / "candidate-memory.jsonl"

    from crypto_alpha_agent.pipeline.candidate_state_memory import (
        persist_candidate_state_memory,
    )

    records = persist_candidate_state_memory(_report([]), memory_path)
    by_candidate = {
        record.opportunity["candidate_id"]: record for record in records
    }

    assert set(by_candidate) == LEGACY_DERIVATIVES_CANDIDATES
    for candidate_id in LEGACY_DERIVATIVES_CANDIDATES:
        record = by_candidate[candidate_id]
        assert record.record_id == f"candidate-state:{candidate_id}"
        assert record.opportunity["state"] == "redesign_required"
        assert record.rejected_reasons == ["non_positive_cost_adjusted_expectancy"]
        assert record.hypothesis["reason_codes"] == [
            "non_positive_cost_adjusted_expectancy"
        ]
        assert record.opportunity["uses_real_capital"] is False
        assert record.opportunity["live_order_routing"] is False


def test_persist_candidate_state_memory_upserts_repeated_runs(tmp_path):
    memory_path = tmp_path / "candidate-memory.jsonl"

    from crypto_alpha_agent.pipeline.candidate_state_memory import (
        persist_candidate_state_memory,
    )

    first = persist_candidate_state_memory(
        _report(
            [
                _metric(
                    "short_horizon_momentum_volatility_filter",
                    reason_codes=["insufficient_samples"],
                    sample_count=0,
                )
            ],
            generated_at=START,
        ),
        memory_path,
        include_current_derivatives_rejections=False,
    )
    second = persist_candidate_state_memory(
        _report(
            [_metric("short_horizon_momentum_volatility_filter", sample_count=25)],
            generated_at=START + timedelta(hours=1),
        ),
        memory_path,
        include_current_derivatives_rejections=False,
    )
    stored = MemoryStore(memory_path).list_records()

    assert [record.record_id for record in first] == [record.record_id for record in second]
    assert [record.record_id for record in stored] == [record.record_id for record in second]
    assert stored[0].opportunity["state"] == "feasibility_passed"
    assert stored[0].score["last_seen_at"] == (START + timedelta(hours=1)).isoformat()
    assert stored[0].score["feasibility_summary"]["sample_count"] == 25


def test_persist_candidate_state_memory_replaces_existing_duplicate_records(tmp_path):
    memory_path = tmp_path / "candidate-memory.jsonl"
    duplicate_id = "candidate-state:short_horizon_momentum_volatility_filter"
    MemoryStore(memory_path).append(
        MemoryRecord(
            record_id=duplicate_id,
            opportunity={"candidate_id": "short_horizon_momentum_volatility_filter", "state": "candidate"},
            hypothesis={"reason_codes": ["stale_candidate_state"]},
            score={"last_seen_at": (START - timedelta(days=2)).isoformat()},
            rejected_reasons=["stale_candidate_state"],
            tags=["candidate-state", "stale"],
        )
    )
    with memory_path.open("a", encoding="utf-8") as handle:
        handle.write(
            MemoryRecord(
                record_id=duplicate_id,
                opportunity={
                    "candidate_id": "short_horizon_momentum_volatility_filter",
                    "state": "redesign_required",
                },
                hypothesis={"reason_codes": ["stale_fail"]},
                score={"last_seen_at": (START - timedelta(days=1)).isoformat()},
                rejected_reasons=["stale_fail"],
                tags=["candidate-state", "stale"],
            ).model_dump_json()
        )
        handle.write("\n")

    from crypto_alpha_agent.pipeline.candidate_state_memory import (
        persist_candidate_state_memory,
    )

    persist_candidate_state_memory(
        _report([_metric("short_horizon_momentum_volatility_filter")]),
        memory_path,
        include_current_derivatives_rejections=False,
    )
    stored = MemoryStore(memory_path).list_records()

    assert [record.record_id for record in stored] == [duplicate_id]
    assert stored[0].opportunity["state"] == "feasibility_passed"
    assert stored[0].rejected_reasons == []


def test_persist_candidate_state_memory_uses_candidate_state_target_without_capital_leak(tmp_path):
    memory_path = tmp_path / "candidate-memory.jsonl"

    from crypto_alpha_agent.pipeline.candidate_state_memory import (
        persist_candidate_state_memory,
    )

    records = persist_candidate_state_memory(
        _report(
            [
                _metric(
                    "short_horizon_momentum_volatility_filter",
                    reason_codes=["insufficient_samples"],
                    sample_count=0,
                )
            ],
        ),
        memory_path,
        include_current_derivatives_rejections=False,
    )

    record = records[0]
    assert record.opportunity["state"] == "source_qualified"
    assert record.score["feasibility_summary"]["candidate_state_target"] == "source_qualified"
    assert "current_capital_usd" not in record.score["feasibility_summary"]
    assert "300.0" not in memory_path.read_text(encoding="utf-8")


def test_persist_candidate_state_memory_records_feasibility_v2_fields(tmp_path):
    memory_path = tmp_path / "candidate-memory.jsonl"

    from crypto_alpha_agent.pipeline.candidate_state_memory import (
        persist_candidate_state_memory,
    )

    records = persist_candidate_state_memory(
        _report(
            [
                _metric(
                    "short_horizon_momentum_volatility_filter",
                    reason_codes=["insufficient_month_coverage"],
                    sample_count=20,
                    unique_months=1,
                    single_month_dependency=True,
                    multiple_testing_adjusted=True,
                )
            ],
            feasibility_version="v2",
        ),
        memory_path,
        include_current_derivatives_rejections=False,
    )

    record = records[0]
    summary = record.score["feasibility_summary"]
    assert record.opportunity["state"] != "paper_collecting"
    assert summary["feasibility_version"] == "v2"
    assert summary["validation_policy"]["purge_gap_bars"] == 24
    assert summary["validation_policy"]["min_unique_months"] == 3
    assert summary["validation_policy"]["min_asset_count"] == 3
    assert summary["unique_months"] == 1
    assert summary["single_month_dependency"] is True
    assert summary["multiple_testing_adjusted"] is True
    assert summary["multiple_testing_summary"]["evaluated_candidate_count"] == 1
    assert summary["multiple_testing_summary"]["blocked_reason_counts"] == {
        "insufficient_month_coverage": 1
    }


def _report(
    metrics: list[CandidateFeasibilityMetric],
    *,
    generated_at: datetime = START,
    feasibility_version: str = "v1",
) -> MultiHypothesisFeasibilityReport:
    validation_policy = FeasibilityValidationPolicy(
        version=feasibility_version,
        purge_gap_bars=24 if feasibility_version == "v2" else 0,
        min_unique_months=3 if feasibility_version == "v2" else 0,
        min_asset_count=3 if feasibility_version == "v2" else 0,
    )
    return MultiHypothesisFeasibilityReport(
        generated_at=generated_at,
        timeframe="1h",
        symbols=SYMBOLS,
        current_capital_usd=300.0,
        cost_bps_grid=[5.0, 10.0, 20.0, 50.0],
        validation_policy=validation_policy,
        multiple_testing_summary=MultipleTestingSummary(
            evaluated_candidate_count=len(metrics),
            feasible_candidate_count=sum(1 for metric in metrics if metric.readiness == "feasible"),
            blocked_candidate_count=sum(1 for metric in metrics if metric.readiness == "blocked"),
            feasible_candidates=[
                metric.candidate for metric in metrics if metric.readiness == "feasible"
            ],
            blocked_reason_counts={
                reason: sum(1 for metric in metrics if reason in metric.reason_codes)
                for reason in sorted({reason for metric in metrics for reason in metric.reason_codes})
            },
        ),
        readiness="feasible" if any(metric.readiness == "feasible" for metric in metrics) else "blocked",
        reason_codes=[],
        universe=EvidenceUniverseReport(
            generated_at=generated_at,
            symbols=SYMBOLS,
            timeframe="1h",
            point_in_time_universe=True,
            reason_codes=[],
            assets=[
                UniverseAsset(
                    symbol=symbol,
                    exchange_symbol=symbol.replace("/", ""),
                    market_records=120,
                    first_market_timestamp=START - timedelta(days=5),
                    latest_market_timestamp=START,
                    blocked_reasons=[],
                )
                for symbol in SYMBOLS
            ],
            source_coverage=[
                UniverseSourceCoverage(
                    source="binance_public",
                    record_type="market_candle",
                    feed="1h",
                    role="execution_history",
                    records=360,
                    latest_observed_at=generated_at,
                    source_health_present=True,
                    network_routes=["direct"],
                    blocked_reasons=[],
                )
            ],
            quality_issues=[],
            uses_real_capital=False,
            live_order_routing=False,
        ),
        candidate_metrics=metrics,
        uses_real_capital=False,
        live_order_routing=False,
    )


def _metric(
    candidate: str,
    *,
    reason_codes: list[str] | None = None,
    sample_count: int = 20,
    unique_months: int = 2,
    single_month_dependency: bool = False,
    multiple_testing_adjusted: bool = False,
) -> CandidateFeasibilityMetric:
    reason_codes = reason_codes or []
    readiness = "blocked" if reason_codes else "feasible"
    if not reason_codes:
        candidate_state_target = "feasibility_passed"
    elif set(reason_codes) <= {"insufficient_universe_coverage"}:
        candidate_state_target = "candidate"
    elif set(reason_codes) <= {"insufficient_samples", "insufficient_walk_forward_splits"}:
        candidate_state_target = "source_qualified"
    elif set(reason_codes) <= {"insufficient_month_coverage", "insufficient_asset_coverage"}:
        candidate_state_target = "candidate"
    else:
        candidate_state_target = "redesign_required"
    return CandidateFeasibilityMetric(
        candidate=candidate,
        readiness=readiness,
        sample_count=sample_count,
        asset_coverage={"BTC/USDT": 20, "ETH/USDT": 20},
        split_coverage=3 if sample_count else 0,
        gross_mean=0.02 if sample_count else None,
        net_mean=0.019 if sample_count else None,
        win_rate=1.0 if sample_count else None,
        turnover=0.1 if sample_count else 0.0,
        unique_months=unique_months if sample_count else 0,
        single_month_dependency=single_month_dependency,
        multiple_testing_adjusted=multiple_testing_adjusted,
        selected_symbol_counts={"BTC/USDT": sample_count} if sample_count else {},
        cost_sensitivity=[
            CostSensitivityMetric(
                cost_bps=5.0,
                gross_mean=0.02,
                net_mean=0.0195,
                win_rate=1.0,
            )
        ]
        if sample_count
        else [],
        split_metrics=[],
        reason_codes=reason_codes,
        candidate_state_target=candidate_state_target,
    )
