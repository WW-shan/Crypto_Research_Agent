import pytest
from pydantic import ValidationError

from crypto_alpha_agent.agents.approvals import ManualApproval
from crypto_alpha_agent.config import RuntimeConfig
from crypto_alpha_agent.risk.guardian import (
    PermissionScope,
    RiskContext,
    RiskGuardian,
    RiskPolicy,
)


def _policy() -> RiskPolicy:
    return RiskPolicy(
        max_capital_per_opportunity_usd=1_000.0,
        max_daily_loss_usd=250.0,
        max_consecutive_failures=3,
        allowed_venues=["binance", "coinbase"],
    )


def _scope() -> PermissionScope:
    return PermissionScope(
        venue="binance",
        api_permissions=["trade"],
        wallet_permissions=["no-withdraw"],
    )


def _context(**overrides) -> RiskContext:
    data = {
        "opportunity_id": "opp-1",
        "execution_mode": "gated_live",
        "venue": "binance",
        "capital_required_usd": 500.0,
        "daily_realized_pnl_usd": -100.0,
        "consecutive_failures": 0,
        "permission_scope": _scope(),
    }
    data.update(overrides)
    if "manual_approval" not in overrides:
        data["manual_approval"] = ManualApproval(
            approval_id="approval-123",
            approved=True,
            approver="risk-lead",
            opportunity_id=data["opportunity_id"],
            action_mode=data["execution_mode"],
            venue=data["venue"],
            max_approved_capital_usd=data["capital_required_usd"],
            reason="within test limits",
            reference_id="ticket-123",
        )
    return RiskContext(**data)


def test_gated_live_requires_manual_approval_before_execution():
    guardian = RiskGuardian(_policy())
    context = _context(manual_approval=None)

    decision = guardian.evaluate(context)

    assert decision.approved is False
    assert decision.live_execution_allowed is False
    assert decision.execution_allowed is False
    assert decision.reason_codes == ["manual_approval_required"]
    with pytest.raises(PermissionError, match="manual_approval_required"):
        decision.assert_can_execute()


def test_forbidden_permissions_block_execution_even_with_manual_approval():
    guardian = RiskGuardian(_policy())
    context = _context(
        permission_scope=PermissionScope(
            venue="binance",
            api_permissions=["trade", "admin"],
            wallet_permissions=["no-withdraw"],
        )
    )

    decision = guardian.evaluate(context)

    assert decision.approved is False
    assert decision.execution_allowed is False
    assert decision.reason_codes == ["forbidden_api_permission"]
    with pytest.raises(PermissionError, match="forbidden_api_permission"):
        decision.assert_can_execute()


def test_policy_guards_emit_stable_reason_codes():
    guardian = RiskGuardian(_policy())
    context = _context(
        venue="unknown-dex",
        capital_required_usd=1_001.0,
        daily_realized_pnl_usd=-250.0,
        consecutive_failures=3,
        permission_scope=PermissionScope(
            venue="unknown-dex",
            api_permissions=["trade"],
            wallet_permissions=["withdraw"],
        ),
    )

    decision = guardian.evaluate(context)

    assert decision.approved is False
    assert decision.execution_allowed is False
    assert decision.reason_codes == [
        "capital_above_opportunity_limit",
        "daily_loss_limit_reached",
        "consecutive_failure_limit_reached",
        "venue_not_allowed",
        "forbidden_wallet_permission",
    ]


def test_gated_live_executes_only_when_all_guards_and_approval_pass():
    guardian = RiskGuardian(_policy())

    decision = guardian.evaluate(_context())

    assert decision.approved is True
    assert decision.execution_allowed is True
    assert decision.live_execution_allowed is True
    assert decision.reason_codes == []
    assert decision.assert_can_execute() is None


def test_gated_live_rejects_approval_scoped_to_different_opportunity():
    guardian = RiskGuardian(_policy())
    context = _context(
        manual_approval=ManualApproval(
            approval_id="approval-stale",
            approved=True,
            approver="risk-lead",
            opportunity_id="opp-previous",
            action_mode="gated_live",
            venue="binance",
            max_approved_capital_usd=500.0,
            reason="approved for a different opportunity",
            reference_id="ticket-previous",
        )
    )

    decision = guardian.evaluate(context)

    assert decision.approved is False
    assert decision.live_execution_allowed is False
    assert decision.reason_codes == ["manual_approval_scope_mismatch"]


def test_gated_live_rejects_approval_that_does_not_cover_requested_capital():
    guardian = RiskGuardian(_policy())
    context = _context(
        capital_required_usd=750.0,
        manual_approval=ManualApproval(
            approval_id="approval-too-small",
            approved=True,
            approver="risk-lead",
            opportunity_id="opp-1",
            action_mode="gated_live",
            venue="binance",
            max_approved_capital_usd=500.0,
            reason="approved a smaller allocation",
            reference_id="ticket-123",
        ),
    )

    decision = guardian.evaluate(context)

    assert decision.approved is False
    assert decision.live_execution_allowed is False
    assert decision.reason_codes == ["manual_approval_scope_mismatch"]


def test_runtime_config_action_mode_is_compatible_with_risk_context():
    guardian = RiskGuardian(_policy())
    context = _context(
        execution_mode=RuntimeConfig().action_mode,
        manual_approval=None,
        permission_scope=PermissionScope(
            venue="binance",
            api_permissions=["read"],
            wallet_permissions=[],
        ),
    )

    decision = guardian.evaluate(context)

    assert decision.approved is True
    assert decision.execution_allowed is False
    assert decision.live_execution_allowed is False
    assert decision.reason_codes == []


def test_duplicate_venue_blocks_emit_one_reason_code():
    guardian = RiskGuardian(_policy())
    context = _context(
        venue="unknown-dex",
        permission_scope=PermissionScope(
            venue="coinbase",
            api_permissions=["trade"],
            wallet_permissions=["no-withdraw"],
        ),
    )

    decision = guardian.evaluate(context)

    assert decision.approved is False
    assert decision.reason_codes == ["venue_not_allowed"]


def test_research_can_be_approved_without_live_execution_or_manual_approval():
    guardian = RiskGuardian(_policy())
    context = _context(
        execution_mode="research_only",
        manual_approval=None,
        permission_scope=PermissionScope(
            venue="binance",
            api_permissions=["read"],
            wallet_permissions=[],
        ),
    )

    decision = guardian.evaluate(context)

    assert decision.approved is True
    assert decision.execution_allowed is False
    assert decision.live_execution_allowed is False
    assert decision.reason_codes == []


@pytest.mark.parametrize(
    "api_permissions,wallet_permissions",
    [
        (["all"], []),
        (["*"], []),
        (["unbounded"], []),
        (["trade"], ["*"]),
        (["*"], ["no-withdraw"]),
    ],
)
def test_permission_scope_rejects_unbounded_permissions(api_permissions, wallet_permissions):
    with pytest.raises(ValidationError):
        PermissionScope(
            venue="binance",
            api_permissions=api_permissions,
            wallet_permissions=wallet_permissions,
        )
