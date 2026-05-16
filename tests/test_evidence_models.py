from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.evidence.models import (
    ExperimentRun,
    PaperSimulationOutcome,
    StrategyCandidate,
    ValidationEvidence,
)


def test_strategy_candidate_preserves_low_capital_constraints():
    candidate = StrategyCandidate(
        candidate_id="cand-funding-btc-001",
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        venue="binance",
        timeframe="1h",
        parameters={"funding_threshold_abs": 0.0005, "hold_bars": 3},
        current_capital_usd=300.0,
        min_capital_usd=25.0,
        data_sources=["ccxt", "binance_public"],
        created_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert candidate.execution_mode == "research_and_paper_only"
    assert candidate.requires_speed_edge is False
    assert candidate.requires_premium_rpc is False
    assert candidate.live_order_routing is False


def test_strategy_candidate_rejects_unsuitable_execution_requirements():
    with pytest.raises(ValidationError):
        StrategyCandidate(
            candidate_id="cand-bad",
            strategy_family="subsecond_arbitrage",
            symbol="ETH/USDT",
            venue="binance",
            timeframe="1m",
            parameters={},
            current_capital_usd=300.0,
            min_capital_usd=5000.0,
            data_sources=["private_rpc"],
            created_at=datetime(2026, 5, 17, tzinfo=UTC),
            requires_speed_edge=True,
        )


def test_validation_evidence_blocks_when_walk_forward_is_missing():
    evidence = ValidationEvidence(
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price",
        trade_count=12,
        net_return=0.04,
        gross_expectancy=0.004,
        fee_adjusted_expectancy=0.003,
        slippage_adjusted_expectancy=0.002,
        max_drawdown=0.03,
        walk_forward_split_count=0,
        walk_forward_pass_rate=0.0,
        approved=False,
        blocked_reasons=["insufficient_walk_forward_splits"],
    )

    assert evidence.approved is False
    assert "insufficient_walk_forward_splits" in evidence.blocked_reasons


def test_paper_simulation_outcome_cannot_touch_live_capital():
    with pytest.raises(ValidationError):
        PaperSimulationOutcome(
            outcome_id="paper-001",
            run_id="run-001",
            candidate_id="cand-001",
            strategy_family="funding_extremity_price_confirmation",
            symbol="BTC/USDT",
            observed_at=datetime(2026, 5, 17, tzinfo=UTC),
            status="closed",
            signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
            entry_price=100.0,
            exit_price=101.0,
            quantity=0.1,
            notional_usd=10.0,
            gross_pnl_usd=0.1,
            fees_usd=0.02,
            slippage_usd=0.01,
            net_pnl_usd=0.07,
            max_drawdown_usd=0.02,
            touched_real_capital=True,
        )


def test_experiment_run_links_candidate_validation_and_paper_outcomes():
    run = ExperimentRun(
        run_id="exp-001",
        candidate_id="cand-001",
        strategy_family="funding_extremity_price_confirmation",
        started_at=datetime(2026, 5, 17, tzinfo=UTC),
        data_sources=["ccxt", "binance_public"],
        status="paper_simulated",
        validation_evidence_ids=["validation-001"],
        paper_outcome_ids=["paper-001", "paper-002"],
        notes=["research_only"],
    )

    assert run.live_order_routing is False
    assert run.status == "paper_simulated"
