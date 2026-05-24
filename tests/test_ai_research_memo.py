from __future__ import annotations

import json

from crypto_alpha_agent.pipeline.ai_research_memo import build_ai_research_memo


def _planning_llm(_task):
    return json.dumps(
        {
            "strategy_family": "funding_extremity_price_confirmation",
            "parameter_changes": {
                "experiment_type": "collect_more_walk_forward_data",
                "threshold_abs": 0.001,
                "hold_bars": 2,
                "min_walk_forward_splits": 3,
            },
            "evidence_refs": ["gap:collect_more_walk_forward_data"],
            "why_it_might_improve_edge": "More public history can test whether the signal survives costs.",
            "expected_edge_mechanism": "Larger public funding extremes may retain fee-adjusted edge.",
            "disconfirmation_tests": ["Reject if deterministic validation remains weak."],
            "stop_conditions": ["Stop after repeated blocked validation runs."],
            "required_data_fields": ["market_candle", "funding_rate"],
            "selected_validator": "funding_price_confirmation",
        }
    )


def test_weekly_ai_research_memo_summarizes_change_failure_and_next_step(tmp_path) -> None:
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    memo = build_ai_research_memo(
        db_path=db_path,
        memory_path=memory_path,
        llm=_planning_llm,
    )

    assert memo.uses_real_capital is False
    assert memo.live_order_routing is False
    assert memo.what_changed
    assert memo.what_failed
    assert memo.what_should_stop
    assert memo.next_experiment
    assert isinstance(json.dumps(memo.model_dump(mode="python")), str)


def test_ai_research_memo_cli_writes_markdown(capsys, tmp_path) -> None:
    from crypto_alpha_agent.cli import main

    out = tmp_path / "ai-memo.md"
    exit_code = main(
        [
            "ai-research-memo",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(out),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "ai-research-memo"
    assert payload["ai_research_memo_out"] == str(out)
    assert payload["memo"]["uses_real_capital"] is False
    assert out.read_text(encoding="utf-8").startswith("# Weekly AI Research Memo")
