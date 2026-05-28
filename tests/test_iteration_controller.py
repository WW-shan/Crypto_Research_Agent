from __future__ import annotations

import json
from typing import Any

from crypto_alpha_agent.pipeline.iteration_controller import build_iteration_cycle_report
from crypto_alpha_agent.pipeline.markdown import render_iteration_cycle_markdown


def _candidate_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "code_change_request",
        "title": "Add source probe fixture",
        "rationale": "Current evidence needs a repeatable source probe.",
        "evidence_refs": ["goal:owner_autonomy_target"],
        "expected_value": "Improves source qualification.",
        "risk_level": "medium",
        "next_actions": ["Write failing tests first."],
        "required_tests": ["pytest tests/test_source_probe.py -q"],
        "required_data_fields": ["source_health"],
        "source_discovery_queries": [],
        "source_probe_targets": [],
        "strategy_family": None,
        "target_files": ["src/crypto_alpha_agent/data/source_probe.py"],
        "human_review_required": True,
        "direct_code_write_authorized": False,
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    payload.update(overrides)
    return payload


def _llm_response(*candidates: dict[str, Any], **overrides: Any) -> str:
    payload: dict[str, Any] = {
        "candidates": list(candidates) or [_candidate_payload()],
        "rejected_reason_codes": [],
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_iteration_cycle_accepts_safe_code_change_request(tmp_path):
    result = build_iteration_cycle_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=lambda task: _llm_response(),
        current_capital_usd=300,
    )

    assert result.accepted is True
    assert result.llm_required is True
    assert result.auto_executes_changes is False
    assert result.candidates[0].kind == "code_change_request"
    assert result.candidates[0].direct_code_write_authorized is False


def test_iteration_cycle_rejects_unknown_evidence_refs(tmp_path):
    result = build_iteration_cycle_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=lambda task: _llm_response(
            _candidate_payload(evidence_refs=["unknown:ref"])
        ),
        current_capital_usd=300,
    )

    assert result.accepted is False
    assert result.candidates == []
    assert "missing_evidence_ref" in result.rejected_reason_codes


def test_iteration_cycle_rejects_direct_code_write_authorization(tmp_path):
    result = build_iteration_cycle_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=lambda task: _llm_response(
            _candidate_payload(direct_code_write_authorized=True)
        ),
        current_capital_usd=300,
    )

    assert result.accepted is False
    assert result.candidates == []
    assert "direct_code_write_authorized" in result.rejected_reason_codes


def test_iteration_cycle_rejects_new_data_source_without_probe_plan(tmp_path):
    result = build_iteration_cycle_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=lambda task: _llm_response(
            _candidate_payload(
                kind="new_data_source",
                title="Add a new derivatives source",
                source_discovery_queries=[],
                source_probe_targets=[],
                target_files=[],
            )
        ),
        current_capital_usd=300,
    )

    assert result.accepted is False
    assert result.candidates == []
    assert "missing_source_probe_plan" in result.rejected_reason_codes


def test_iteration_cycle_markdown_records_safety_and_candidates(tmp_path):
    result = build_iteration_cycle_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        llm=lambda task: _llm_response(),
        current_capital_usd=300,
    )

    markdown = render_iteration_cycle_markdown(result)

    assert "# Iteration Cycle Report" in markdown
    assert "LLM required: true" in markdown
    assert "Auto executes changes: false" in markdown
    assert "Direct code write authorized: false" in markdown
    assert "code_change_request" in markdown
    assert "Add source probe fixture" in markdown
    assert "goal:owner_autonomy_target" in markdown
    assert "pytest tests/test_source_probe.py -q" in markdown
