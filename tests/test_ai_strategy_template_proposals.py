from __future__ import annotations

import json

from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.experiment_planner import plan_next_experiments


def test_planner_accepts_design_only_strategy_template_proposal(tmp_path) -> None:
    memory_path = tmp_path / "memory.jsonl"

    def llm(_task):
        return json.dumps(
            {
                "strategy_template_proposals": [
                    {
                        "proposal_id": "template-001",
                        "strategy_family": "funding_extremity_price_confirmation",
                        "proposed_validator_name": "funding_price_confirmation_v2",
                        "thesis": "A stricter validator can disconfirm fee-killed edge faster.",
                        "expected_edge_mechanism": "Higher funding extremes may survive fees and slippage.",
                        "required_data_fields": ["market_candle", "funding_rate"],
                        "evidence_refs": ["gap:collect_more_walk_forward_data"],
                        "disconfirmation_tests": ["Reject if fee-adjusted expectancy stays non-positive."],
                        "stop_conditions": ["Stop if validation remains blocked after two runs."],
                        "deterministic_tests_required": True,
                        "human_review_required": True,
                    }
                ]
            }
        )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        llm=llm,
        current_capital_usd=120.0,
    )

    assert result.accepted is True
    assert result.strategy_template_proposals
    template = result.strategy_template_proposals[0]
    assert template.proposed_validator_name == "funding_price_confirmation_v2"
    assert template.deterministic_tests_required is True
    assert template.human_review_required is True
    records = MemoryStore(memory_path).list_records()
    assert records[0].tags == ["strategy-template-proposal", "design-only", "accepted"]
    assert records[0].hypothesis["template_proposal"]["proposal_id"] == "template-001"
