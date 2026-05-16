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
