from __future__ import annotations

import math

import pytest
from pydantic import ValidationError


def test_aggregates_closed_paper_outcomes_for_strategy_family():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-1",
                "status": "closed",
                "realized_net_pnl": 12.5,
                "drawdown_usd": 3.0,
            },
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-2",
                "status": "closed",
                "realized_pnl_usd": -2.5,
                "max_drawdown_usd": 7.0,
            },
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-3",
                "status": "filled",
                "realized_net_pnl": 5.0,
            },
        ]
    )

    assert len(packages) == 1
    package = packages[0]
    assert package.strategy_family == "funding_basis"
    assert package.sample_size == 3
    assert package.closed_count == 3
    assert package.failed_count == 0
    assert package.net_pnl_usd == 15.0
    assert package.hit_rate == pytest.approx(2 / 3)
    assert package.max_drawdown_usd == 7.0
    assert package.failure_reasons == []
    assert package.approved_for_review is False
    assert package.total_notional_usd == 0.0
    assert package.total_fees_usd == 0.0
    assert package.total_slippage_usd == 0.0


def test_includes_failed_and_rejected_outcomes_with_deduped_failure_reasons():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "strategy_family": "breakout",
                "trade_id": "trade-1",
                "status": "closed",
                "realized_net_pnl": 4.0,
            },
            {
                "strategy_family": "breakout",
                "trade_id": "trade-2",
                "status": "failed",
                "realized_net_pnl": -1.5,
                "reason_codes": ["insufficient_paper_cash", "exchange_unavailable"],
            },
            {
                "strategy_family": "breakout",
                "trade_id": "trade-3",
                "status": "rejected",
                "realized_pnl_usd": 0.0,
                "failure_reasons": ["exchange_unavailable", "guard_rejected"],
            },
            {
                "strategy_family": "breakout",
                "trade_id": "trade-4",
                "status": "blocked",
                "error_reason": "capital_above_budget",
            },
        ]
    )

    assert packages[0].sample_size == 4
    assert packages[0].closed_count == 1
    assert packages[0].failed_count == 3
    assert packages[0].net_pnl_usd == 2.5
    assert packages[0].hit_rate == 1.0
    assert packages[0].max_drawdown_usd == 1.5
    assert packages[0].failure_reasons == [
        "insufficient_paper_cash",
        "exchange_unavailable",
        "guard_rejected",
        "capital_above_budget",
    ]


def test_aggregates_phase_10_execution_realism_fields():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-1",
                "symbol": "ETH/USDT:USDT",
                "status": "closed",
                "notional_usd": 25.0,
                "gross_pnl_usd": 1.0,
                "fees_usd": 0.05,
                "slippage_usd": 0.025,
                "realized_net_pnl": 0.925,
                "cost_model_mode": "pessimistic",
                "stale_signal_status": "fresh",
                "fill_status": "full",
            },
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-2",
                "symbol": "ETH/USDT:USDT",
                "status": "blocked",
                "notional_usd": 0.0,
                "gross_pnl_usd": 0.0,
                "fees_usd": 0.0,
                "slippage_usd": 0.0,
                "realized_net_pnl": 0.0,
                "cost_model_mode": "pessimistic",
                "stale_signal_status": "stale",
                "fill_status": "missed",
                "failure_reasons": ["stale_signal", "missed_fill_assumed"],
            },
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-3",
                "symbol": "ETH/USDT:USDT",
                "status": "closed",
                "notional_usd": 10.0,
                "gross_pnl_usd": 0.4,
                "fees_usd": 0.02,
                "slippage_usd": 0.01,
                "realized_net_pnl": 0.37,
                "cost_model_mode": "pessimistic",
                "stale_signal_status": "fresh",
                "fill_status": "partial",
            },
        ]
    )

    package = packages[0]
    assert package.total_notional_usd == pytest.approx(35.0)
    assert package.gross_pnl_usd == pytest.approx(1.4)
    assert package.total_fees_usd == pytest.approx(0.07)
    assert package.total_slippage_usd == pytest.approx(0.035)
    assert package.stale_signal_count == 1
    assert package.missed_fill_count == 1
    assert package.partial_fill_count == 1
    assert package.cost_model_modes == ["pessimistic"]
    assert package.failure_reasons == ["stale_signal", "missed_fill_assumed"]


def test_groups_multiple_strategy_families_in_deterministic_order():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "strategy_family": "momentum",
                "trade_id": "trade-1",
                "status": "closed",
                "realized_net_pnl": 3.0,
            },
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-2",
                "status": "closed",
                "realized_net_pnl": 2.0,
            },
            {
                "strategy_family": "momentum",
                "trade_id": "trade-3",
                "status": "closed",
                "realized_net_pnl": -1.0,
            },
        ]
    )

    assert [package.strategy_family for package in packages] == ["funding_basis", "momentum"]
    assert [package.net_pnl_usd for package in packages] == [2.0, 2.0]


def test_filters_to_requested_strategy_family():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "strategy_family": "momentum",
                "trade_id": "trade-1",
                "status": "closed",
                "realized_net_pnl": 3.0,
            },
            {
                "strategy_family": "funding_basis",
                "trade_id": "trade-2",
                "status": "closed",
                "realized_net_pnl": 2.0,
            },
        ],
        strategy_family="momentum",
    )

    assert [package.strategy_family for package in packages] == ["momentum"]
    assert packages[0].sample_size == 1


def test_accepts_paper_trade_result_inputs():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence
    from crypto_alpha_agent.execution.paper import PaperFill, PaperTradeResult

    fill = PaperFill(
        symbol="ETH-USD",
        side="sell",
        quantity=1.0,
        reference_price=100.0,
        fill_price=110.0,
        gross_value=110.0,
        fee=1.0,
        slippage_rate=0.0,
        latency_ms=2.0,
    )
    result = PaperTradeResult(
        fill=fill,
        cash=1_010.0,
        inventory={"ETH-USD": 0.0},
        capital_used=100.0,
        realized_gross_pnl=10.0,
        realized_net_pnl=9.0,
    )

    packages = aggregate_paper_evidence([result], strategy_family="paper_execution")

    assert packages[0].strategy_family == "paper_execution"
    assert packages[0].sample_size == 1
    assert packages[0].closed_count == 1
    assert packages[0].net_pnl_usd == 9.0
    assert packages[0].hit_rate == 1.0


def test_aggregates_nested_closed_paper_outcome_with_strategy_family_default():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "status": "closed",
                "buy": {
                    "fill": {
                        "symbol": "ETH-USD",
                    },
                    "capital_used": 100.0,
                },
                "sell": {
                    "fill": {
                        "symbol": "ETH-USD",
                    },
                    "realized_net_pnl": 12.5,
                    "capital_used": 100.0,
                    "drawdown": -4.0,
                },
            }
        ],
        strategy_family="funding_basis",
    )

    assert len(packages) == 1
    package = packages[0]
    assert package.strategy_family == "funding_basis"
    assert package.sample_size == 1
    assert package.closed_count == 1
    assert package.failed_count == 0
    assert package.net_pnl_usd == 12.5
    assert package.hit_rate == 1.0
    assert package.max_drawdown_usd == 4.0


def test_rejects_bool_drawdown_from_mapping_input():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    with pytest.raises(ValidationError):
        aggregate_paper_evidence(
            [
                {
                    "status": "closed",
                    "realized_net_pnl": 1.0,
                    "drawdown": True,
                }
            ],
            strategy_family="funding_basis",
        )


def test_aggregates_failed_paper_outcome_with_reason_codes_and_strategy_family_default():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "status": "failed",
                "stage": "paper_execute",
                "reason_codes": ["insufficient_paper_cash"],
                "error": "paper account cash is insufficient",
            }
        ],
        strategy_family="funding_basis",
    )

    assert packages[0].strategy_family == "funding_basis"
    assert packages[0].sample_size == 1
    assert packages[0].closed_count == 0
    assert packages[0].failed_count == 1
    assert packages[0].net_pnl_usd == 0.0
    assert packages[0].hit_rate == 0.0
    assert packages[0].failure_reasons == [
        "insufficient_paper_cash",
        "paper account cash is insufficient",
    ]


def test_aggregates_failed_paper_outcome_with_error_fallback():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "status": "failed",
                "stage": "paper_execute",
                "error": "paper account cash is insufficient",
            }
        ],
        strategy_family="funding_basis",
    )

    assert packages[0].failure_reasons == ["paper account cash is insufficient"]


def test_aggregates_blocked_paper_outcome_with_reason_codes_and_strategy_family_default():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    packages = aggregate_paper_evidence(
        [
            {
                "status": "blocked",
                "stage": "score_feasibility",
                "reason_codes": ["capital_above_budget"],
            }
        ],
        strategy_family="funding_basis",
    )

    assert packages[0].strategy_family == "funding_basis"
    assert packages[0].sample_size == 1
    assert packages[0].closed_count == 0
    assert packages[0].failed_count == 1
    assert packages[0].failure_reasons == ["capital_above_budget"]


def test_rejects_non_finite_numeric_inputs():
    from crypto_alpha_agent.evidence.paper import PaperEvidenceInput

    with pytest.raises(ValidationError):
        PaperEvidenceInput(
            strategy_family="funding_basis",
            trade_id="trade-1",
            status="closed",
            realized_net_pnl=math.nan,
        )


def test_empty_input_returns_empty_list():
    from crypto_alpha_agent.evidence.paper import aggregate_paper_evidence

    assert aggregate_paper_evidence([]) == []
