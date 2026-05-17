from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.risk.rollout import (
    compute_max_observed_loss_usd,
    validation_evidence_to_walk_forward_splits,
)

STRATEGY_FAMILY = "funding_extremity_price_confirmation"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "crypto_alpha_agent.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _paper_outcome(
    index: int,
    *,
    status: str = "closed",
    gross_pnl_usd: float = 2.0,
    fees_usd: float = 0.25,
    slippage_usd: float = 0.25,
    net_pnl_usd: float = 1.5,
    max_drawdown_usd: float = 0.5,
    failure_reasons: tuple[str, ...] = (),
) -> PaperSimulationOutcome:
    observed_at = datetime(2026, 5, 17, tzinfo=UTC) + timedelta(minutes=index)
    return PaperSimulationOutcome(
        outcome_id=f"paper-{index:03d}",
        run_id="rollout-fixture",
        candidate_id=f"candidate-{index:03d}",
        strategy_family=STRATEGY_FAMILY,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status=status,
        signal_timestamp=observed_at - timedelta(minutes=5),
        entry_price=100.0,
        exit_price=101.0,
        quantity=0.25,
        notional_usd=25.0 if status == "closed" else 0.0,
        gross_pnl_usd=gross_pnl_usd,
        fees_usd=fees_usd,
        slippage_usd=slippage_usd,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=max_drawdown_usd,
        failure_reasons=failure_reasons,
        touched_real_capital=False,
        live_order_routing=False,
    )


def _validation_evidence(
    index: int,
    *,
    approved: bool = True,
    blocked_reasons: tuple[str, ...] = (),
    slippage_adjusted_expectancy: float = 1.25,
    walk_forward_split_count: int = 3,
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id=f"validation-run-{index}",
        strategy_family=STRATEGY_FAMILY,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_extremity_walk_forward",
        trade_count=30,
        net_return=0.08,
        gross_expectancy=1.75,
        fee_adjusted_expectancy=1.45,
        slippage_adjusted_expectancy=slippage_adjusted_expectancy,
        max_drawdown=2.0,
        walk_forward_split_count=walk_forward_split_count,
        walk_forward_pass_rate=1.0 if approved else 0.0,
        approved=approved,
        blocked_reasons=blocked_reasons,
    )


def _write_fixture(
    db_path: Path,
    *,
    outcomes: list[PaperSimulationOutcome],
    evidence: list[ValidationEvidence] | None = None,
) -> None:
    PaperOutcomeLedger(db_path).upsert_outcomes(outcomes)
    ValidationEvidenceLedger(db_path).upsert_evidence(
        evidence if evidence is not None else [_validation_evidence(1)]
    )


def _payload_from_cli(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_rollout_review_cli_blocks_with_insufficient_closed_sample_and_skips_no_signal_outcomes(tmp_path):
    db_path = tmp_path / "research.sqlite"
    outcomes = [_paper_outcome(index) for index in range(29)]
    outcomes.extend(
        [
            _paper_outcome(
                29,
                status="no_signal",
                gross_pnl_usd=0.0,
                fees_usd=0.0,
                slippage_usd=0.0,
                net_pnl_usd=0.0,
                max_drawdown_usd=0.0,
            ),
            _paper_outcome(
                30,
                status="no_signal",
                gross_pnl_usd=0.0,
                fees_usd=0.0,
                slippage_usd=0.0,
                net_pnl_usd=0.0,
                max_drawdown_usd=0.0,
            ),
        ]
    )
    _write_fixture(db_path, outcomes=outcomes)

    result = _run_cli(
        "rollout-review",
        "--db",
        str(db_path),
        "--strategy-family",
        STRATEGY_FAMILY,
    )

    payload = _payload_from_cli(result)
    rollout = payload["rollout_evaluation"]
    evidence_package = payload["evidence_package"]

    assert payload["command"] == "rollout-review"
    assert payload["decision"] == "blocked"
    assert "insufficient_sample_size" in payload["blocked_reasons"]
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert rollout["observation_count"] == 29
    assert "insufficient_sample_size" in rollout["reason_codes"]
    assert evidence_package["sample_size"] == 31
    assert evidence_package["closed_count"] == 29
    assert evidence_package["rollout_observation_count"] == 29
    assert payload["max_observed_loss_usd"] == pytest.approx(0.5)
    assert payload["readiness_artifact"]["ready_for_human_review"] is False
    assert payload["readiness_artifact"]["live_execution_enabled"] is False


def test_rollout_review_cli_builds_review_ready_artifact_and_writes_evidence_package(tmp_path):
    db_path = tmp_path / "research.sqlite"
    artifact_out = tmp_path / "artifacts" / "readiness.json"
    evidence_package_out = tmp_path / "artifacts" / "evidence-package.json"
    _write_fixture(db_path, outcomes=[_paper_outcome(index) for index in range(30)])

    result = _run_cli(
        "rollout-review",
        "--db",
        str(db_path),
        "--strategy-family",
        STRATEGY_FAMILY,
        "--human-approved",
        "--human-approval-reference",
        "approval-ticket-16",
        "--artifact-out",
        str(artifact_out),
        "--evidence-package-out",
        str(evidence_package_out),
    )

    payload = _payload_from_cli(result)

    assert payload["readiness_artifact"]["ready_for_human_review"] is True
    assert payload["decision"] == "ready_for_human_review"
    assert payload["blocked_reasons"] == []
    assert payload["readiness_artifact"]["live_execution_enabled"] is False
    assert payload["rollout_evaluation"]["eligible_for_tiny_live"] is True
    assert payload["rollout_evaluation"]["walk_forward_split_count"] == 3
    assert payload["evidence_package_out"] == str(evidence_package_out)
    assert payload["evidence_package"]["evidence_package_path"] == str(evidence_package_out)
    assert payload["max_observed_loss_usd"] == pytest.approx(0.5)

    readiness_artifact = json.loads(artifact_out.read_text(encoding="utf-8"))
    persisted_package = json.loads(evidence_package_out.read_text(encoding="utf-8"))
    assert readiness_artifact["ready_for_human_review"] is True
    assert readiness_artifact["live_execution_enabled"] is False
    assert persisted_package["paper_outcome_ids"] == [f"paper-{index:03d}" for index in range(30)]
    assert persisted_package["validation_evidence_ids"]
    assert persisted_package["evidence_package_path"] == str(evidence_package_out)


def test_compute_max_observed_loss_uses_worst_negative_net_pnl_or_drawdown():
    outcomes = [
        _paper_outcome(0, net_pnl_usd=-7.0, max_drawdown_usd=3.0),
        _paper_outcome(
            1,
            status="blocked",
            gross_pnl_usd=0.0,
            fees_usd=0.0,
            slippage_usd=0.0,
            net_pnl_usd=0.0,
            max_drawdown_usd=12.0,
            failure_reasons=("risk_block",),
        ),
        _paper_outcome(
            2,
            status="failed",
            gross_pnl_usd=0.0,
            fees_usd=0.0,
            slippage_usd=0.0,
            net_pnl_usd=-9.0,
            max_drawdown_usd=4.0,
            failure_reasons=("paper_error",),
        ),
        _paper_outcome(
            3,
            gross_pnl_usd=-20.0,
            fees_usd=1.0,
            slippage_usd=1.0,
            net_pnl_usd=0.0,
            max_drawdown_usd=1.0,
        ),
    ]

    assert compute_max_observed_loss_usd(outcomes) == pytest.approx(22.0)


def test_rollout_module_public_api_imports_without_evidence_cycle():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from crypto_alpha_agent.risk.rollout import RolloutEvaluation",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_validation_evidence_conversion_excludes_blocked_numeric_walk_forward_evidence():
    blocked = _validation_evidence(
        2,
        approved=False,
        blocked_reasons=("negative_expectancy",),
        slippage_adjusted_expectancy=-0.25,
        walk_forward_split_count=2,
    )

    splits = validation_evidence_to_walk_forward_splits([blocked])

    assert splits == []


def test_validation_evidence_conversion_dedupes_canonical_evidence_ids():
    first = _validation_evidence(3, walk_forward_split_count=2)
    second = _validation_evidence(4, walk_forward_split_count=2)
    assert first.evidence_id == second.evidence_id

    splits = validation_evidence_to_walk_forward_splits([first, second])

    assert [split.split_id for split in splits] == [
        f"{first.evidence_id}:split:0",
        f"{first.evidence_id}:split:1",
    ]


def test_rollout_review_cli_blocks_unapproved_positive_walk_forward_evidence(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_fixture(
        db_path,
        outcomes=[_paper_outcome(index) for index in range(30)],
        evidence=[
            _validation_evidence(
                5,
                approved=False,
                blocked_reasons=("validation_not_approved",),
                slippage_adjusted_expectancy=1.25,
                walk_forward_split_count=3,
            )
        ],
    )

    result = _run_cli(
        "rollout-review",
        "--db",
        str(db_path),
        "--strategy-family",
        STRATEGY_FAMILY,
        "--human-approved",
        "--human-approval-reference",
        "approval-ticket-16",
    )

    payload = _payload_from_cli(result)

    assert payload["decision"] == "blocked"
    assert payload["rollout_evaluation"]["walk_forward_split_count"] == 0
    assert "insufficient_walk_forward_splits" in payload["blocked_reasons"]
    assert payload["readiness_artifact"]["ready_for_human_review"] is False
    assert payload["evidence_package"]["validation_blocked_reasons"] == [
        "validation_not_approved"
    ]


def test_rollout_review_cli_counts_failed_outcomes_in_failure_rate_gate(tmp_path):
    db_path = tmp_path / "research.sqlite"
    failed_outcomes = [
        _paper_outcome(
            index,
            status="failed",
            gross_pnl_usd=0.0,
            fees_usd=0.0,
            slippage_usd=0.0,
            net_pnl_usd=0.0,
            max_drawdown_usd=0.0,
            failure_reasons=("paper_error",),
        )
        for index in range(30, 34)
    ]
    _write_fixture(
        db_path,
        outcomes=[*_paper_outcome_list(30), *failed_outcomes],
    )

    result = _run_cli(
        "rollout-review",
        "--db",
        str(db_path),
        "--strategy-family",
        STRATEGY_FAMILY,
        "--human-approved",
        "--human-approval-reference",
        "approval-ticket-16",
    )

    payload = _payload_from_cli(result)

    assert payload["decision"] == "blocked"
    assert payload["rollout_evaluation"]["observation_count"] == 34
    assert payload["rollout_evaluation"]["failure_rate"] == pytest.approx(4 / 34)
    assert "failure_rate_above_limit" in payload["blocked_reasons"]
    assert payload["evidence_package"]["failed_count"] == 4


def _paper_outcome_list(count: int) -> list[PaperSimulationOutcome]:
    return [_paper_outcome(index) for index in range(count)]
