from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.evidence.models import (
    ExperimentRun,
    PaperSimulationOutcome,
    StrategyCandidate,
    ValidationEvidence,
)


def _strategy_candidate_kwargs(**overrides):
    data = {
        "candidate_id": "cand-funding-btc-001",
        "strategy_family": "funding_extremity_price_confirmation",
        "symbol": "BTC/USDT",
        "venue": "binance",
        "timeframe": "1h",
        "parameters": {"funding_threshold_abs": 0.0005, "hold_bars": 3},
        "current_capital_usd": 300.0,
        "min_capital_usd": 25.0,
        "data_sources": ["ccxt", "binance_public"],
        "created_at": datetime(2026, 5, 17, tzinfo=UTC),
    }
    data.update(overrides)
    return data


def _validation_evidence_kwargs(**overrides):
    data = {
        "strategy_family": "funding_extremity_price_confirmation",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "validator_name": "funding_price",
        "trade_count": 12,
        "net_return": 0.04,
        "gross_expectancy": 0.004,
        "fee_adjusted_expectancy": 0.003,
        "slippage_adjusted_expectancy": 0.002,
        "max_drawdown": 0.03,
        "walk_forward_split_count": 0,
        "walk_forward_pass_rate": 0.0,
        "approved": False,
        "blocked_reasons": ["insufficient_walk_forward_splits"],
    }
    data.update(overrides)
    return data


def _paper_simulation_outcome_kwargs(**overrides):
    data = {
        "outcome_id": "paper-001",
        "run_id": "run-001",
        "candidate_id": "cand-001",
        "strategy_family": "funding_extremity_price_confirmation",
        "symbol": "BTC/USDT",
        "observed_at": datetime(2026, 5, 17, tzinfo=UTC),
        "status": "closed",
        "signal_timestamp": datetime(2026, 5, 17, tzinfo=UTC),
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 0.1,
        "notional_usd": 10.0,
        "gross_pnl_usd": 0.1,
        "fees_usd": 0.02,
        "slippage_usd": 0.01,
        "net_pnl_usd": 0.07,
        "max_drawdown_usd": 0.02,
    }
    data.update(overrides)
    return data


def _experiment_run_kwargs(**overrides):
    data = {
        "run_id": "exp-001",
        "candidate_id": "cand-001",
        "strategy_family": "funding_extremity_price_confirmation",
        "started_at": datetime(2026, 5, 17, tzinfo=UTC),
        "data_sources": ["ccxt", "binance_public"],
        "status": "paper_simulated",
        "validation_evidence_ids": ["validation-001"],
        "paper_outcome_ids": ["paper-001", "paper-002"],
        "notes": ["research_only"],
    }
    data.update(overrides)
    return data


def test_strategy_candidate_preserves_low_capital_constraints():
    candidate = StrategyCandidate(**_strategy_candidate_kwargs())

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
    evidence = ValidationEvidence(**_validation_evidence_kwargs())

    assert evidence.approved is False
    assert "insufficient_walk_forward_splits" in evidence.blocked_reasons


def test_paper_simulation_outcome_cannot_touch_live_capital():
    with pytest.raises(ValidationError):
        PaperSimulationOutcome(**_paper_simulation_outcome_kwargs(touched_real_capital=True))


def test_experiment_run_links_candidate_validation_and_paper_outcomes():
    run = ExperimentRun(**_experiment_run_kwargs())

    assert run.live_order_routing is False
    assert run.status == "paper_simulated"


def test_required_data_sources_cannot_normalize_to_empty():
    with pytest.raises(ValidationError):
        StrategyCandidate(**_strategy_candidate_kwargs(data_sources=["  "]))

    with pytest.raises(ValidationError):
        ExperimentRun(**_experiment_run_kwargs(data_sources=["  "]))


def test_validation_evidence_id_uses_canonical_blocked_reasons():
    repeated = ValidationEvidence(**_validation_evidence_kwargs(blocked_reasons=["x", "x", " "]))
    canonical = ValidationEvidence(**_validation_evidence_kwargs(blocked_reasons=["x"]))

    assert repeated.blocked_reasons == ["x"]
    assert repeated.evidence_id == canonical.evidence_id


def test_validation_evidence_id_treats_omitted_and_empty_blocked_reasons_equally():
    omitted_kwargs = _validation_evidence_kwargs()
    omitted_kwargs.pop("blocked_reasons")

    omitted = ValidationEvidence(**omitted_kwargs)
    explicit_empty = ValidationEvidence(**_validation_evidence_kwargs(blocked_reasons=[]))

    assert omitted.blocked_reasons == []
    assert explicit_empty.blocked_reasons == []
    assert omitted.evidence_id == explicit_empty.evidence_id


def test_strategy_candidate_rejects_unsafe_assignment():
    candidate = StrategyCandidate(**_strategy_candidate_kwargs())

    with pytest.raises(ValidationError):
        candidate.live_order_routing = True
    assert candidate.live_order_routing is False


def test_paper_simulation_outcome_rejects_unsafe_assignment():
    capital_outcome = PaperSimulationOutcome(**_paper_simulation_outcome_kwargs())
    routing_outcome = PaperSimulationOutcome(**_paper_simulation_outcome_kwargs(outcome_id="paper-002"))

    with pytest.raises(ValidationError):
        capital_outcome.touched_real_capital = True
    assert capital_outcome.touched_real_capital is False

    with pytest.raises(ValidationError):
        routing_outcome.live_order_routing = True
    assert routing_outcome.live_order_routing is False


@pytest.mark.parametrize("source_name", ["private_rpc", "premium_rpc", "eth_mempool", "mev_stream"])
def test_strategy_candidate_rejects_unsafe_data_sources(source_name):
    with pytest.raises(ValidationError):
        StrategyCandidate(**_strategy_candidate_kwargs(data_sources=[source_name]))


def test_strategy_candidate_rejects_blank_scalar_identifier():
    with pytest.raises(ValidationError):
        StrategyCandidate(**_strategy_candidate_kwargs(candidate_id="   "))
