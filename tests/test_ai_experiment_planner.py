from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.pipeline.experiment_planner import plan_next_experiments
from crypto_alpha_agent.strategy import default_strategy_registry


class _PlannerRuntime:
    def __init__(self, response: str) -> None:
        self.llm = _PlannerLLM(response)
        self.health_commands: list[str] = []

    def health_check(self, *, command: str):
        self.health_commands.append(command)
        return object()

    def metadata(self) -> dict[str, Any]:
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": "planning",
            "llm_model": "test-real-model",
            "llm_health_schema": "LLMHealthCheckResult",
        }


class _PlannerLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.task = None

    def __call__(self, task):
        self.task = task
        return self.response


class _SequencePlannerLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.tasks: list[Any] = []

    def __call__(self, task):
        self.tasks.append(task)
        index = min(len(self.tasks) - 1, len(self.responses) - 1)
        return self.responses[index]


def _planner_response(*, threshold_abs: float = 0.001, hold_bars: int = 2) -> str:
    return json.dumps(
        {
            "strategy_family": "funding_extremity_price_confirmation",
            "parameter_changes": {
                "threshold_abs": threshold_abs,
                "hold_bars": hold_bars,
            },
            "evidence_refs": ["gap:collect_more_walk_forward_data"],
            "why_it_might_improve_edge": "Higher public funding extremity may survive fees.",
            "expected_edge_mechanism": (
                "More extreme public funding rates should survive fees and slippage."
            ),
            "disconfirmation_tests": [
                "Reject if fee-adjusted expectancy stays non-positive."
            ],
            "stop_conditions": ["Stop after two blocked validation runs."],
            "required_data_fields": ["market_candle", "funding_rate"],
            "selected_validator": "funding_price_confirmation",
        }
    )


def seed_validation_memory(
    memory_path: Path,
    *,
    run_id: str,
    strategy_family: str,
    blocked_reasons: list[str],
    parameters: dict[str, Any],
) -> None:
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id=f"validation:{run_id}",
            created_at=DETERMINISTIC_EVENT_TIME_ISO,
            updated_at=DETERMINISTIC_EVENT_TIME_ISO,
            opportunity={
                "run_id": run_id,
                "strategy_family": strategy_family,
                "parameters": parameters,
            },
            hypothesis={
                "strategy_family": strategy_family,
                "parameter_changes": parameters,
            },
            score={
                "approved": False,
                "blocked_reasons": blocked_reasons,
                "parameters": parameters,
            },
            rejected_reasons=blocked_reasons,
            tags=[strategy_family, "validation", "blocked"],
        )
    )


def _validation_evidence(
    *,
    run_id: str = "validation-run-001",
    strategy_family: str = "funding_extremity_price_confirmation",
    blocked_reasons: list[str] | None = None,
    net_return: float = -0.03,
    fee_adjusted_expectancy: float = -0.001,
    slippage_adjusted_expectancy: float = -0.0015,
    walk_forward_split_count: int = 0,
) -> ValidationEvidence:
    reasons = blocked_reasons or ["insufficient_walk_forward_splits"]
    return ValidationEvidence(
        run_id=run_id,
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price_confirmation",
        trade_count=3,
        net_return=net_return,
        gross_expectancy=0.001,
        fee_adjusted_expectancy=fee_adjusted_expectancy,
        slippage_adjusted_expectancy=slippage_adjusted_expectancy,
        max_drawdown=0.02,
        walk_forward_split_count=walk_forward_split_count,
        walk_forward_pass_rate=0.0,
        approved=False,
        blocked_reasons=reasons,
    )


def _paper_outcome(
    *,
    outcome_id: str = "paper-001",
    strategy_family: str = "funding_extremity_price_confirmation",
    net_pnl_usd: float = -0.25,
    failure_reasons: tuple[str, ...] = ("fee_killed_edge",),
) -> PaperSimulationOutcome:
    observed_at = datetime(2026, 5, 17, tzinfo=UTC)
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="paper-run-001",
        candidate_id="candidate-001",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status="closed",
        signal_timestamp=observed_at,
        entry_price=100.0,
        exit_price=99.5,
        quantity=0.1,
        notional_usd=10.0,
        gross_pnl_usd=0.05,
        fees_usd=0.2,
        slippage_usd=0.1,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=abs(net_pnl_usd),
        failure_reasons=failure_reasons,
    )


def _strict_llm_experiment_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategy_family": "funding_extremity_price_confirmation",
        "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
        "evidence_refs": ["gap:collect_more_walk_forward_data"],
        "why_it_might_improve_edge": "Higher funding threshold may survive fees.",
        "expected_edge_mechanism": "More extreme public funding rates should survive fees and slippage.",
        "disconfirmation_tests": ["Reject if fee-adjusted expectancy remains non-positive."],
        "stop_conditions": ["Stop after two failed validation runs."],
        "required_data_fields": ["market_candle", "funding_rate"],
        "selected_validator": "funding_price_confirmation",
    }
    payload.update(overrides)
    return payload


def _planner_llm(**overrides: Any):
    def llm(_task):
        return json.dumps(_strict_llm_experiment_payload(**overrides))

    return llm


def test_planner_uses_validation_memory_to_avoid_repeating_blocked_parameters(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    seed_validation_memory(
        memory_path,
        run_id="daily-001",
        strategy_family="funding_extremity_price_confirmation",
        blocked_reasons=["non_positive_net_return"],
        parameters={"threshold_abs": 0.0005, "hold_bars": 1},
    )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family="funding_extremity_price_confirmation",
        max_proposals=2,
        current_capital_usd=300.0,
        llm=_planner_llm(),
    )

    assert result.live_order_routing is False
    assert all(proposal.strategy_family == "funding_extremity_price_confirmation" for proposal in result.proposals)
    assert all(proposal.max_capital_usd <= 300.0 for proposal in result.proposals)
    assert all(proposal.parameter_changes != {"threshold_abs": 0.0005, "hold_bars": 1} for proposal in result.proposals)


def test_plan_experiments_requires_llm(tmp_path):
    with pytest.raises(TypeError, match="llm"):
        plan_next_experiments(
            db_path=tmp_path / "research.sqlite",
            memory_path=tmp_path / "memory.jsonl",
            current_capital_usd=300.0,
        )


def test_planner_does_not_emit_evidence_less_open_interest_family_baseline(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    blocked_parameters = {"threshold_abs": 0.0005, "hold_bars": 1}
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation_evidence(
                strategy_family="funding_extremity_price_confirmation",
                blocked_reasons=["insufficient_walk_forward_splits"],
                walk_forward_split_count=0,
            )
        ]
    )
    seed_validation_memory(
        memory_path,
        run_id="daily-blocked-baseline",
        strategy_family="funding_extremity_price_confirmation",
        blocked_reasons=["non_positive_net_return"],
        parameters=blocked_parameters,
    )

    result = plan_next_experiments(
        db_path=db_path,
        memory_path=memory_path,
        max_proposals=3,
        current_capital_usd=300.0,
        llm=_planner_llm(),
    )

    assert result.accepted is True
    assert result.proposals
    assert all(
        proposal.strategy_family != "funding_open_interest_crowding"
        for proposal in result.proposals
    )
    assert all(proposal.parameter_changes != blocked_parameters for proposal in result.proposals)


def test_planner_rejects_open_interest_family_without_family_specific_evidence(tmp_path):
    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_family="funding_open_interest_crowding",
        max_proposals=2,
        current_capital_usd=300.0,
        llm=_planner_llm(
            strategy_family="funding_open_interest_crowding",
            required_data_fields=["market_candle", "funding_rate", "open_interest"],
            selected_validator="funding_oi_crowding",
        ),
    )

    assert result.accepted is False
    assert result.proposals == []
    assert "no_safe_registered_proposals" in result.rejected_reason_codes


def test_planner_rejects_llm_open_interest_family_without_family_specific_evidence(tmp_path):
    def llm(_task):
        return json.dumps(
            {
                "strategy_family": "funding_open_interest_crowding",
                "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                "evidence_refs": ["gap:collect_more_walk_forward_data"],
                "why_it_might_improve_edge": "Open interest can disconfirm crowded funding reversals.",
                "expected_edge_mechanism": "Crowded funding plus open interest may identify stronger public dislocations.",
                "disconfirmation_tests": ["Reject if open-interest confirmation does not improve expectancy."],
                "stop_conditions": ["Stop after two blocked validation runs."],
                "required_data_fields": ["market_candle", "funding_rate", "open_interest"],
                "selected_validator": "funding_oi_crowding",
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert result.proposals == []
    assert "no_safe_registered_proposals" in result.rejected_reason_codes


def test_planner_rejects_unsafe_llm_experiment(tmp_path):
    def unsafe_llm(_task):
        return '{"strategy_family":"mev_sandwich","live_order_routing":true,"parameter_changes":{}}'

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=unsafe_llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "charter_violation" in result.rejected_reason_codes
    assert result.proposals == []


def test_planner_rejects_sparse_llm_proposal_schema(tmp_path):
    def llm(_task):
        return json.dumps(
            {
                "strategy_family": "funding_extremity_price_confirmation",
                "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "invalid_proposal_schema" in result.rejected_reason_codes


def test_planner_retries_structural_proposal_schema_failures(tmp_path):
    llm = _SequencePlannerLLM(
        [
            json.dumps(
                {
                    "proposals": [
                        {
                            "strategy_family": "funding_extremity_price_confirmation",
                            "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                        }
                    ]
                }
            ),
            json.dumps({"proposals": [_strict_llm_experiment_payload()]}),
        ]
    )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is True
    assert len(result.proposals) == 1
    assert len(llm.tasks) == 2


def test_planner_ignores_llm_supplied_computed_proposal_fields(tmp_path):
    def llm(_task):
        return json.dumps(
            {
                "proposals": [
                    _strict_llm_experiment_payload(
                        proposal_id="llm-should-not-win",
                        max_capital_usd=90.0,
                        max_notional_usd=9.0,
                        accepted=True,
                        rejected_reason_codes=[],
                    )
                ]
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=90.0,
    )

    assert result.accepted is True
    assert result.proposals[0].proposal_id != "llm-should-not-win"
    assert result.proposals[0].max_capital_usd == 90.0
    assert result.proposals[0].max_notional_usd == 9.0


def test_planner_coerces_llm_text_list_proposal_fields(tmp_path):
    def llm(_task):
        return json.dumps(
            {
                "proposals": [
                    _strict_llm_experiment_payload(
                        why_it_might_improve_edge=[
                            "Higher funding threshold may reduce noisy entries.",
                            "Price confirmation may preserve after-cost edge.",
                        ],
                        expected_edge_mechanism=[
                            "Public funding extremes capture crowding.",
                            "Market candles confirm direction before validation.",
                        ],
                    )
                ]
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=90.0,
    )

    assert result.accepted is True
    assert "Higher funding threshold" in result.proposals[0].why_it_might_improve_edge
    assert "Public funding extremes" in result.proposals[0].expected_edge_mechanism


def test_planner_rejects_nonexistent_evidence_ref(tmp_path):
    def llm(_task):
        return json.dumps(
            _strict_llm_experiment_payload(evidence_refs=["validation:not-present"])
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "missing_evidence_ref" in result.rejected_reason_codes


def test_planner_persists_rejected_memory_for_mixed_llm_batch(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    def llm(_task):
        invalid = _strict_llm_experiment_payload(
            parameter_changes={"threshold_abs": 0.0015, "hold_bars": 1},
            evidence_refs=["validation:not-present"],
        )
        return json.dumps({"proposals": [_strict_llm_experiment_payload(), invalid]})

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is True
    assert len(result.proposals) == 1
    records = MemoryStore(memory_path).list_records()
    accepted_records = [record for record in records if "accepted" in record.tags]
    rejected_records = [record for record in records if "rejected" in record.tags]
    assert accepted_records
    assert rejected_records
    assert rejected_records[0].record_id == f"experiment-proposal:{result.batch_id}:partial-rejected"
    assert rejected_records[0].rejected_reasons == ["missing_evidence_ref"]


def test_planner_rejects_arbitrary_data_gap_ref(tmp_path):
    def llm(_task):
        return json.dumps(
            _strict_llm_experiment_payload(
                evidence_refs=["data-gap:completely_unregistered_dataset"]
            )
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "missing_evidence_ref" in result.rejected_reason_codes


def test_planner_rejects_unavailable_required_data_field(tmp_path):
    def llm(_task):
        return json.dumps(
            _strict_llm_experiment_payload(
                required_data_fields=["market_candle", "funding_rate", "liquidations"]
            )
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "unsupported_data_fields" in result.rejected_reason_codes


def test_planner_rejects_direct_paper_outcome_payload(tmp_path):
    def llm(_task):
        return json.dumps(
            {
                "paper_outcomes": [{"outcome_id": "fabricated-paper-outcome"}],
                "proposals": [_strict_llm_experiment_payload()],
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "charter_violation" in result.rejected_reason_codes


def test_planner_rejects_duplicate_prior_experiment_signature(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="experiment-proposal:prior",
            opportunity={"strategy_family": "funding_extremity_price_confirmation"},
            hypothesis={
                "proposal": {
                    "strategy_family": "funding_extremity_price_confirmation",
                    "selected_validator": "funding_price_confirmation",
                    "parameter_changes": {"hold_bars": 2, "threshold_abs": 0.001},
                }
            },
            rejected_reasons=["non_positive_net_return"],
            tags=["experiment-proposal", "rejected"],
        )
    )

    def llm(_task):
        return json.dumps(_strict_llm_experiment_payload())

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert "duplicate_experiment" in result.rejected_reason_codes


def test_planner_reads_evidence_and_proposes_bounded_registered_disconfirmation_experiment(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation_evidence(
                blocked_reasons=["insufficient_walk_forward_splits"],
                walk_forward_split_count=0,
            )
        ]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes([_paper_outcome()])

    result = plan_next_experiments(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family="funding_extremity_price_confirmation",
        current_capital_usd=80.0,
        max_proposals=3,
        llm=_planner_llm(
            parameter_changes={
                "experiment_type": "collect_more_walk_forward_data",
                "threshold_abs": 0.0005,
                "hold_bars": 1,
                "min_walk_forward_splits": 3,
            },
        ),
    )

    assert result.accepted is True
    assert result.validation_evidence_count == 1
    assert result.paper_evidence_count == 1
    assert result.proposals
    proposal = result.proposals[0]
    assert proposal.strategy_family == "funding_extremity_price_confirmation"
    assert proposal.max_notional_usd == 8.0
    assert proposal.live_order_routing is False
    assert proposal.uses_real_capital is False
    assert "collect_more_walk_forward_data" in proposal.parameter_changes.values()
    assert proposal.evidence_refs
    assert proposal.disconfirmation_tests
    assert proposal.stop_conditions
    assert proposal.allowed_data_sources == ["market_candle", "funding_rate"]


def test_planner_uses_paper_insufficient_walk_forward_splits_to_collect_more_data(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            _paper_outcome(
                failure_reasons=("insufficient_walk_forward_splits",),
            )
        ]
    )

    result = plan_next_experiments(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family="funding_extremity_price_confirmation",
        current_capital_usd=80.0,
        max_proposals=1,
        llm=_planner_llm(
            parameter_changes={
                "experiment_type": "collect_more_walk_forward_data",
                "threshold_abs": 0.0005,
                "hold_bars": 1,
                "min_walk_forward_splits": 3,
            },
        ),
    )

    assert result.accepted is True
    assert result.proposals
    proposal = result.proposals[0]
    assert proposal.parameter_changes["experiment_type"] == "collect_more_walk_forward_data"
    assert proposal.parameter_changes["min_walk_forward_splits"] == 3


def test_planner_defaults_to_first_registered_funding_baseline_when_no_evidence_exists(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        current_capital_usd=300.0,
        llm=_planner_llm(parameter_changes={"threshold_abs": 0.0005, "hold_bars": 1}),
    )

    assert result.proposals
    assert result.proposals[0].strategy_family == "funding_extremity_price_confirmation"
    assert result.proposals[0].parameter_changes["threshold_abs"] == 0.0005
    assert result.proposals[0].max_notional_usd == 25.0
    assert any("experiment-proposal" in record.tags for record in MemoryStore(memory_path).list_records())


def test_planner_rejects_unknown_strategy_family_without_proposals(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family="unknown_non_funding_family",
        current_capital_usd=300.0,
        llm=_planner_llm(),
    )

    assert result.accepted is False
    assert result.proposals == []
    assert result.rejected_reason_codes
    assert "no_safe_registered_proposals" in result.rejected_reason_codes
    assert any("experiment-proposal" in record.tags for record in MemoryStore(memory_path).list_records())


def test_planner_rejects_when_all_funding_families_are_degraded(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    registry = default_strategy_registry(current_capital_usd=300.0)
    funding_families = [
        family
        for family in registry.list_families()
        if {"market_candle", "funding_rate"}.issubset(set(registry.get(family).required_record_types))
    ]
    for family in funding_families:
        MemoryStore(memory_path).upsert(
            MemoryRecord(
                record_id=f"degraded:{family}",
                opportunity={"strategy_family": family},
                rejected_reasons=["degraded_expectancy"],
                tags=[family, "degraded_expectancy"],
            )
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        current_capital_usd=300.0,
        max_proposals=2,
        llm=_planner_llm(),
    )

    assert result.accepted is False
    assert result.proposals == []
    assert result.rejected_reason_codes
    assert "no_safe_registered_proposals" in result.rejected_reason_codes
    assert result.degraded_strategy_families == sorted(funding_families)
    assert not any("accepted" in record.tags for record in MemoryStore(memory_path).list_records())


def test_planner_omits_unsafe_memory_degraded_family_from_llm_task_and_memory(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    unsafe_family = "private key seed phrase"
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="degraded:unsafe-family",
            opportunity={"strategy_family": unsafe_family},
            hypothesis={
                "strategy_family": unsafe_family,
                "parameter_changes": {"threshold_abs": 0.001},
            },
            rejected_reasons=["degraded_expectancy"],
            tags=["degraded_expectancy"],
        )
    )
    seen: dict[str, Any] = {}

    def llm(task):
        seen["task"] = task
        rendered_task = json.dumps(task.model_dump(mode="python"), sort_keys=True)
        assert unsafe_family not in rendered_task
        return json.dumps(
            {
                "strategy_family": "funding_extremity_price_confirmation",
                "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                "evidence_refs": ["gap:collect_more_walk_forward_data"],
                "why_it_might_improve_edge": "Higher funding threshold may survive fees.",
                "expected_edge_mechanism": "More extreme public funding rates should survive fees and slippage.",
                "disconfirmation_tests": ["Reject if fee-adjusted expectancy remains non-positive."],
                "stop_conditions": ["Stop after two failed validation runs."],
                "required_data_fields": ["market_candle", "funding_rate"],
                "selected_validator": "funding_price_confirmation",
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=llm,
        current_capital_usd=120.0,
    )

    assert result.accepted is True
    assert seen["task"].degraded_strategy_families == []
    persisted = json.dumps(
        [
            record.model_dump(mode="python")
            for record in MemoryStore(memory_path).list_records()
            if "experiment-proposal" in record.tags
        ],
        sort_keys=True,
    )
    assert unsafe_family not in persisted


def test_planner_passes_structured_evidence_context_to_llm(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation_evidence(
                blocked_reasons=["insufficient_walk_forward_splits"],
                walk_forward_split_count=0,
            )
        ]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes([_paper_outcome()])
    seed_validation_memory(
        memory_path,
        run_id="daily-structured-context",
        strategy_family="funding_extremity_price_confirmation",
        blocked_reasons=["non_positive_net_return"],
        parameters={"threshold_abs": 0.0005, "hold_bars": 1},
    )
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="degraded:funding_mean_reversion_after_extreme",
            opportunity={"strategy_family": "funding_mean_reversion_after_extreme"},
            rejected_reasons=["fee_killed_edge"],
            tags=["funding_mean_reversion_after_extreme", "degraded_expectancy"],
        )
    )

    seen: dict[str, Any] = {}

    def llm(task):
        seen["task"] = task
        assert task.planner_input.db_path == str(db_path)
        assert task.validation_evidence_summaries
        assert task.paper_evidence_packages
        assert task.degraded_strategy_families == ["funding_mean_reversion_after_extreme"]
        assert task.blocked_parameter_sets["funding_extremity_price_confirmation"]
        assert task.memory_context.blocked_parameter_sets["funding_extremity_price_confirmation"]
        return json.dumps(
                {
                    "strategy_family": "funding_extremity_price_confirmation",
                    "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                    "evidence_refs": [task.evidence_refs[0]],
                    "why_it_might_improve_edge": "Higher funding threshold may survive fees.",
                    "expected_edge_mechanism": "More extreme public funding rates should survive fees and slippage.",
                    "disconfirmation_tests": ["Reject if fee-adjusted expectancy remains non-positive."],
                    "stop_conditions": ["Stop after two failed validation runs."],
                    "required_data_fields": ["market_candle", "funding_rate"],
                    "selected_validator": "funding_price_confirmation",
                }
            )

    result = plan_next_experiments(
        db_path=db_path,
        memory_path=memory_path,
        strategy_family="funding_extremity_price_confirmation",
        llm=llm,
        current_capital_usd=120.0,
    )

    assert result.accepted is True
    assert seen["task"].planner_input.strategy_family == "funding_extremity_price_confirmation"
    assert seen["task"].memory_context.degraded_strategy_families == [
        "funding_mean_reversion_after_extreme"
    ]


def test_planner_excludes_degraded_families_by_default(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="degraded:funding_extremity_price_confirmation",
            opportunity={"strategy_family": "funding_extremity_price_confirmation"},
            rejected_reasons=["fee_killed_edge"],
            tags=["funding_extremity_price_confirmation", "degraded_expectancy"],
        )
    )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        current_capital_usd=300.0,
        max_proposals=2,
        llm=_planner_llm(),
    )

    assert "funding_extremity_price_confirmation" in result.degraded_strategy_families
    assert all(proposal.strategy_family != "funding_extremity_price_confirmation" for proposal in result.proposals)


def test_planner_rejects_invalid_llm_json_and_persists_safe_rejection_memory(tmp_path):
    unsafe_response = "{not json} private-key seed phrase live order"
    memory_path = tmp_path / "memory.jsonl"

    def invalid_llm(_task):
        return unsafe_response

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=invalid_llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert result.rejected_reason_codes == ["invalid_json"]
    assert result.proposals == []

    records = MemoryStore(memory_path).list_records()
    assert len(records) == 1
    record = records[0]
    assert record.record_id.startswith(f"experiment-proposal:{result.batch_id}:rejected")
    assert "experiment-proposal" in record.tags
    assert record.rejected_reasons == ["invalid_json"]
    persisted = json.dumps(record.model_dump(mode="python"), sort_keys=True)
    assert "private-key seed phrase" not in persisted
    assert "live order" not in persisted
    assert record.hypothesis["llm_response"]["raw_response_length"] == len(unsafe_response)
    assert record.hypothesis["llm_response"]["raw_response_omitted"] is True


def test_planner_rejects_llm_json_with_nan_and_persists_safe_rejection_memory(tmp_path):
    unsafe_response = (
        '{"strategy_family":"funding_extremity_price_confirmation",'
        '"parameter_changes":{"threshold_abs":NaN}}'
    )
    memory_path = tmp_path / "memory.jsonl"

    def nan_llm(_task):
        return unsafe_response

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=nan_llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert result.rejected_reason_codes == ["invalid_json"]
    assert result.proposals == []

    records = MemoryStore(memory_path).list_records()
    assert len(records) == 1
    assert records[0].rejected_reasons == ["invalid_json"]
    assert records[0].hypothesis["llm_response"]["raw_response_omitted"] is True


@pytest.mark.parametrize("malformed_response", [None, {"content": "not json"}, b'{"content":"not json"}'])
def test_planner_rejects_non_string_llm_response_and_persists_safe_rejection_memory(
    tmp_path,
    malformed_response,
):
    memory_path = tmp_path / "memory.jsonl"

    def malformed_llm(_task):
        return malformed_response

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=malformed_llm,
        current_capital_usd=300.0,
    )

    assert result.accepted is False
    assert result.proposals == []
    assert result.rejected_reason_codes

    records = MemoryStore(memory_path).list_records()
    assert len(records) == 1
    record = records[0]
    assert record.record_id.startswith(f"experiment-proposal:{result.batch_id}:rejected")
    assert "experiment-proposal" in record.tags
    assert record.rejected_reasons == result.rejected_reason_codes
    metadata = record.hypothesis["llm_response"]
    assert metadata["raw_response_type"] == type(malformed_response).__name__
    assert metadata["raw_response_omitted"] is True
    assert "raw_response_sha256" not in metadata
    assert "raw_response_length" not in metadata
    persisted = json.dumps(record.model_dump(mode="python"), sort_keys=True)
    assert "not json" not in persisted


def test_planner_accepts_safe_llm_experiment_and_writes_proposal_memory(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    def safe_llm(_task):
        return json.dumps(
            {
                "strategy_family": "funding_extremity_price_confirmation",
                "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                "why_it_might_improve_edge": "Higher funding threshold may survive fees.",
                "expected_edge_mechanism": "More extreme funding rates should survive fees and slippage.",
                "disconfirmation_tests": ["Reject if fee-adjusted expectancy remains non-positive."],
                "stop_conditions": ["Stop after two failed validation runs."],
                "required_data_fields": ["market_candle", "funding_rate"],
                "selected_validator": "funding_price_confirmation",
                "evidence_refs": ["gap:collect_more_walk_forward_data"],
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=safe_llm,
        current_capital_usd=120.0,
    )

    assert result.accepted is True
    assert len(result.proposals) == 1
    assert result.proposals[0].max_notional_usd == 12.0
    assert result.proposals[0].live_order_routing is False
    assert result.proposals[0].proposal_id

    record_id = f"experiment-proposal:{result.batch_id}:{result.proposals[0].proposal_id}"
    persisted = MemoryStore(memory_path).get(record_id)
    assert persisted is not None
    assert persisted.tags == ["experiment-proposal", "accepted"]
    assert persisted.hypothesis["proposal"]["proposal_id"] == result.proposals[0].proposal_id


def test_experiment_planner_graph_writes_result_to_state_and_memory(tmp_path):
    from crypto_alpha_agent.orchestrator import build_experiment_planner_graph

    memory_path = tmp_path / "memory.jsonl"
    graph = build_experiment_planner_graph(
        lambda _task: json.dumps(
            {
                "strategy_family": "funding_extremity_price_confirmation",
                "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                "evidence_refs": ["gap:collect_more_walk_forward_data"],
                "why_it_might_improve_edge": "Higher funding threshold may survive fees.",
                "expected_edge_mechanism": "More extreme public funding rates should survive fees and slippage.",
                "disconfirmation_tests": ["Reject if fee-adjusted expectancy remains non-positive."],
                "stop_conditions": ["Stop after two failed validation runs."],
                "required_data_fields": ["market_candle", "funding_rate"],
                "selected_validator": "funding_price_confirmation",
            }
        )
    )

    state = graph.invoke(
        {
            "db_path": str(tmp_path / "research.sqlite"),
            "memory_path": str(memory_path),
            "current_capital_usd": 300.0,
        }
    )

    assert state["trace"] == ["experiment_planner"]
    assert state["experiment_planner_result"]["accepted"] is True
    assert state["experiment_proposals"]
    assert MemoryStore(memory_path).list_records()


def test_cli_plan_experiments_outputs_safe_json(capsys, monkeypatch, tmp_path):
    from crypto_alpha_agent.cli import main

    runtime = _PlannerRuntime(_planner_response())
    seen: dict[str, Any] = {}

    def fake_build_required_real_llm_runtime(*, role):
        seen["role"] = role
        return runtime

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        fake_build_required_real_llm_runtime,
    )

    exit_code = main(
        [
            "plan-experiments",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--max-proposals",
            "1",
            "--current-capital-usd",
            "90",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "plan-experiments"
    assert payload["current_capital_usd"] == 90.0
    assert payload["accepted"] is True
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert len(payload["proposals"]) == 1
    assert payload["proposals"][0]["max_notional_usd"] == 9.0
    assert seen["role"] == "planning"
    assert runtime.health_commands == ["plan-experiments"]


def test_plan_experiments_auto_uses_configured_planning_llm(
    capsys,
    monkeypatch,
    tmp_path,
):
    from crypto_alpha_agent.cli import main

    seen: dict[str, Any] = {}
    runtime = _PlannerRuntime(_planner_response(threshold_abs=0.001, hold_bars=2))

    def fake_build_required_real_llm_runtime(*, role):
        seen["role"] = role
        return runtime

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        fake_build_required_real_llm_runtime,
    )

    exit_code = main(
        [
            "plan-experiments",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--max-proposals",
            "1",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert seen["role"] == "planning"
    assert runtime.llm.task.task_id.startswith("experiment-planner:")
    assert payload["llm_provider"] == "real"
    assert payload["llm_role"] == "planning"
    assert payload["proposals"][0]["parameter_changes"] == {"threshold_abs": 0.001, "hold_bars": 2}


def test_plan_experiments_offline_only_is_rejected(
    capsys,
    tmp_path,
):
    from crypto_alpha_agent.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "plan-experiments",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--memory",
                str(tmp_path / "memory.jsonl"),
                "--strategy-family",
                "funding_extremity_price_confirmation",
                "--max-proposals",
                "1",
                "--offline-only",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "unrecognized arguments: --offline-only" in captured.err
