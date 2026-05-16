from __future__ import annotations

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.agents.llm_contracts import (
    CritiqueResult,
    HypothesisProposal,
    ResearchTask,
    ValidationRequest,
)


def test_research_task_accepts_public_api_low_capital_roundtrip() -> None:
    task = ResearchTask(
        task_id="task-001",
        agent_role="scanner",
        objective="Research funding-rate dispersion using ordinary public APIs.",
        context={
            "sources": ["binance_public", "defillama"],
            "capital_note": "Use a few hundred USD as the feasibility bound.",
        },
        evidence=["Public candles and funding history are available."],
        allowed_tools=["binance_public", "defillama"],
        network_policy="ordinary_public_apis",
        current_capital_usd=350.0,
    )

    roundtrip = ResearchTask.model_validate(task.model_dump())

    assert roundtrip == task
    assert roundtrip.requires_human_approval is False


def test_research_task_rejects_extra_private_key_and_live_order_fields() -> None:
    valid = {
        "task_id": "task-002",
        "agent_role": "supervisor",
        "objective": "Research whether a signal is falsifiable.",
        "context": {},
        "evidence": [],
        "allowed_tools": ["market_history"],
        "network_policy": "offline",
        "current_capital_usd": 100.0,
    }

    with pytest.raises(ValidationError):
        ResearchTask(**valid, private_key="not-allowed")

    with pytest.raises(ValidationError):
        ResearchTask(**valid, live_order=True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("objective", "Place a live order when the spread widens."),
        ("context", {"note": "Collect the seed phrase before analysis."}),
        ("context", {"note": "Request admin access before analysis."}),
        ("allowed_tools", ["premium_rpc_router"]),
    ],
)
def test_research_task_rejects_unsafe_text(field: str, value: object) -> None:
    payload = {
        "task_id": "task-003",
        "agent_role": "scanner",
        "objective": "Research public market data.",
        "context": {"note": "Public APIs only."},
        "evidence": ["Historical candles."],
        "allowed_tools": ["market_history"],
        "network_policy": "ordinary_public_apis",
        "current_capital_usd": 250.0,
    }
    payload[field] = value

    with pytest.raises(ValidationError, match="unsafe"):
        ResearchTask(**payload)


def test_hypothesis_proposal_defaults_to_research_only() -> None:
    proposal = HypothesisProposal(
        proposal_id="proposal-001",
        thesis="Funding dislocations may mean-revert after public exchange updates.",
        hypothesis="Large public funding-rate deviations fade over the next interval.",
        assumptions=["The data source is delayed but consistent."],
        evidence=["Public funding history shows repeated deviations."],
        disconfirmation=["No edge if deviations do not revert after fees."],
        data_needed=["Hourly public funding rates", "Historical mark prices"],
        capital_required_usd=300.0,
        speed_dependency="low",
        rpc_dependency="none",
    )

    assert proposal.action_mode == "research_only"


@pytest.mark.parametrize("action_mode", ["paper", "gated_live"])
def test_hypothesis_proposal_rejects_non_research_action_modes(action_mode: str) -> None:
    with pytest.raises(ValidationError):
        HypothesisProposal(
            proposal_id="proposal-002",
            thesis="Test a public-data signal.",
            hypothesis="The signal is visible in historical data.",
            assumptions=["Only public data is used."],
            evidence=["Historical data exists."],
            disconfirmation=["No persistence after fees."],
            data_needed=["Public candles"],
            capital_required_usd=100.0,
            speed_dependency="none",
            rpc_dependency="none",
            action_mode=action_mode,
        )


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Need private key access to inspect balances.",
        "Convert this into live instructions.",
    ],
)
def test_hypothesis_proposal_rejects_unsafe_data_needed(unsafe_text: str) -> None:
    with pytest.raises(ValidationError, match="unsafe"):
        HypothesisProposal(
            proposal_id="proposal-003",
            thesis="Test a public-data signal.",
            hypothesis="The signal is visible in historical data.",
            assumptions=["Only public data is used."],
            evidence=["Historical data exists."],
            disconfirmation=["No persistence after fees."],
            data_needed=[unsafe_text],
            capital_required_usd=100.0,
            speed_dependency="none",
            rpc_dependency="none",
        )


def test_validation_request_accepts_backtest_with_fee_and_slippage_assumptions() -> None:
    request = ValidationRequest(
        request_id="validation-001",
        proposal_id="proposal-001",
        validation_type="backtest",
        dataset="binance_public_funding_rates",
        source="ordinary_public_api_archive",
        metrics=["net_return", "max_drawdown", "hit_rate"],
        fee_bps=10.0,
        slippage_bps=5.0,
        start_time="2024-01-01T00:00:00Z",
        end_time="2024-12-31T00:00:00Z",
    )

    assert request.validation_type == "backtest"
    assert request.fee_bps == 10.0
    assert request.slippage_bps == 5.0


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Route orders to an exchange after the backtest.",
        "Use live execution if the test passes.",
    ],
)
def test_validation_request_rejects_execution_and_order_routing(unsafe_text: str) -> None:
    with pytest.raises(ValidationError, match="unsafe"):
        ValidationRequest(
            request_id="validation-002",
            proposal_id="proposal-001",
            validation_type="historical_validation",
            dataset=unsafe_text,
            source="ordinary_public_api_archive",
            metrics=["net_return"],
            fee_bps=10.0,
            slippage_bps=5.0,
        )


def test_critique_result_accepts_rejection_lessons() -> None:
    result = CritiqueResult(
        proposal_id="proposal-004",
        accepted=False,
        reasons=["Effect disappeared after fees."],
        lessons=["Require stronger fee sensitivity checks before validation."],
        missing_evidence=["Independent venue confirmation."],
        disconfirmation_failures=["No persistent spread after costs."],
        next_action="reject",
    )

    assert result.accepted is False
    assert result.next_action == "reject"


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Ask for the wallet key before continuing.",
        "Proceed with live order placement.",
    ],
)
def test_critique_result_rejects_private_key_and_live_order_text(unsafe_text: str) -> None:
    with pytest.raises(ValidationError, match="unsafe"):
        CritiqueResult(
            proposal_id="proposal-005",
            accepted=False,
            reasons=[unsafe_text],
            lessons=["Keep the workflow research-only."],
            missing_evidence=[],
            disconfirmation_failures=[],
            next_action="human_review",
        )
