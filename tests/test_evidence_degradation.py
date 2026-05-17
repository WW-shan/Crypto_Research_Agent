from __future__ import annotations

from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline import evidence_reports
from crypto_alpha_agent.pipeline.experiment_planner import plan_next_experiments


STRATEGY_FAMILY = "funding_extremity_price_confirmation"


def test_negative_latest_window_paper_expectancy_triggers_degraded_expectancy():
    positive_history = [
        _paper_outcome(f"old-{index}", net_pnl_usd=2.0, hours=index)
        for index in range(3)
    ]
    recent_losses = [
        _paper_outcome(f"recent-{index}", net_pnl_usd=-0.25, hours=10 + index)
        for index in range(10)
    ]

    result = evidence_reports.detect_strategy_degradation(
        [*positive_history, *recent_losses],
        [],
        window=10,
    )

    assert result.degraded is True
    assert result.strategy_families == [STRATEGY_FAMILY]
    assert result.family_decisions[0].strategy_family == STRATEGY_FAMILY
    assert result.family_decisions[0].rolling_paper_expectancy == -0.25
    assert result.family_decisions[0].paper_outcome_count == 10
    assert result.family_decisions[0].reason_codes == ["degraded_expectancy"]
    assert result.reason_codes == ["degraded_expectancy"]


def test_paper_expectancy_window_uses_latest_closed_and_failed_outcomes():
    positive_history = [
        _paper_outcome(f"old-{index}", net_pnl_usd=2.0, hours=index)
        for index in range(3)
    ]
    recent_losses = [
        _paper_outcome(f"recent-{index}", net_pnl_usd=-0.25, hours=10 + index)
        for index in range(10)
    ]
    later_blocked = [
        _paper_outcome(
            f"blocked-later-{index}",
            status="blocked",
            net_pnl_usd=0.0,
            failure_reasons=("no_valid_public_signal",),
            hours=30 + index,
        )
        for index in range(2)
    ]

    result = evidence_reports.detect_strategy_degradation(
        [*positive_history, *recent_losses, *later_blocked],
        [],
        window=10,
    )

    assert result.family_decisions[0].paper_outcome_count == 10
    assert result.family_decisions[0].rolling_paper_expectancy == -0.25
    assert result.family_decisions[0].reason_codes == ["degraded_expectancy"]


def test_blocked_paper_outcomes_trigger_insufficient_progress_reason():
    outcomes = [
        _paper_outcome(
            f"blocked-{index}",
            status="blocked",
            net_pnl_usd=0.0,
            failure_reasons=("no_valid_public_signal",),
            hours=index,
        )
        for index in range(3)
    ]

    result = evidence_reports.detect_strategy_degradation(outcomes, [], window=10)

    assert result.degraded is True
    assert result.family_decisions[0].blocked_outcome_count == 3
    assert "insufficient_evidence_progress" in result.reason_codes
    assert "too_many_blocked_runs" in result.reason_codes


def test_fee_and_slippage_killed_validation_edge_are_reported_per_family():
    result = evidence_reports.detect_strategy_degradation(
        [],
        [
            _validation_evidence(
                strategy_family=STRATEGY_FAMILY,
                gross_expectancy=0.003,
                fee_adjusted_expectancy=0.0,
                slippage_adjusted_expectancy=-0.001,
            ),
            _validation_evidence(
                strategy_family="funding_mean_reversion_after_extreme",
                gross_expectancy=0.004,
                fee_adjusted_expectancy=0.002,
                slippage_adjusted_expectancy=0.0,
            ),
        ],
    )

    decisions = {
        decision.strategy_family: decision
        for decision in result.family_decisions
    }
    assert result.degraded is True
    assert result.strategy_families == [
        "funding_extremity_price_confirmation",
        "funding_mean_reversion_after_extreme",
    ]
    assert decisions[STRATEGY_FAMILY].reason_codes == [
        "fee_killed_edge",
        "slippage_killed_edge",
    ]
    assert decisions["funding_mean_reversion_after_extreme"].reason_codes == [
        "slippage_killed_edge"
    ]


def test_non_degraded_families_return_empty_reasons():
    result = evidence_reports.detect_strategy_degradation(
        [
            _paper_outcome("closed-1", net_pnl_usd=0.25, hours=1),
            _paper_outcome("closed-2", net_pnl_usd=0.15, hours=2),
        ],
        [
            _validation_evidence(
                gross_expectancy=0.003,
                fee_adjusted_expectancy=0.002,
                slippage_adjusted_expectancy=0.001,
                approved=True,
                blocked_reasons=(),
            )
        ],
    )

    assert result.degraded is False
    assert result.strategy_families == []
    assert result.reason_codes == []
    assert result.family_decisions[0].reason_codes == []


def test_mark_family_degraded_persists_memory_record_planner_can_read(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    record = evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy", "fee_killed_edge", "degraded_expectancy"],
        memory_path=memory_path,
    )
    stopped = evidence_reports.load_stopped_strategy_families(memory_path)
    planner_result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family=STRATEGY_FAMILY,
        max_proposals=1,
    )
    persisted = MemoryStore(memory_path).get(f"degraded:{STRATEGY_FAMILY}")

    assert record.record_id == f"degraded:{STRATEGY_FAMILY}"
    assert persisted is not None
    assert persisted.rejected_reasons == ["degraded_expectancy", "fee_killed_edge"]
    assert set(persisted.tags) >= {
        STRATEGY_FAMILY,
        "degraded",
        "degraded_expectancy",
        "fee_killed_edge",
    }
    assert persisted.opportunity["strategy_family"] == STRATEGY_FAMILY
    assert stopped == [STRATEGY_FAMILY]
    assert planner_result.proposals == []
    assert planner_result.degraded_strategy_families == [STRATEGY_FAMILY]


def _paper_outcome(
    outcome_id: str,
    *,
    strategy_family: str = STRATEGY_FAMILY,
    status: str = "closed",
    net_pnl_usd: float,
    gross_pnl_usd: float = 0.05,
    fees_usd: float = 0.01,
    slippage_usd: float = 0.01,
    failure_reasons: tuple[str, ...] = (),
    hours: int = 0,
) -> PaperSimulationOutcome:
    observed_at = datetime(2026, 5, 17, tzinfo=UTC) + timedelta(hours=hours)
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="paper-degradation-run",
        candidate_id=f"candidate-{outcome_id}",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status=status,
        signal_timestamp=observed_at,
        entry_price=100.0,
        exit_price=99.0,
        quantity=0.1,
        notional_usd=10.0,
        gross_pnl_usd=gross_pnl_usd,
        fees_usd=fees_usd,
        slippage_usd=slippage_usd,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=abs(net_pnl_usd),
        failure_reasons=failure_reasons,
    )


def _validation_evidence(
    *,
    strategy_family: str = STRATEGY_FAMILY,
    gross_expectancy: float,
    fee_adjusted_expectancy: float,
    slippage_adjusted_expectancy: float,
    approved: bool = False,
    blocked_reasons: tuple[str, ...] = ("non_positive_expectancy",),
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id="validation-degradation-run",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price_confirmation",
        trade_count=8,
        net_return=slippage_adjusted_expectancy,
        gross_expectancy=gross_expectancy,
        fee_adjusted_expectancy=fee_adjusted_expectancy,
        slippage_adjusted_expectancy=slippage_adjusted_expectancy,
        max_drawdown=0.02,
        walk_forward_split_count=3,
        walk_forward_pass_rate=1.0 if approved else 0.0,
        approved=approved,
        blocked_reasons=blocked_reasons,
    )
