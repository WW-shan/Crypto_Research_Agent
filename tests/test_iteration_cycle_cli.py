from __future__ import annotations

import json
from typing import Any

from crypto_alpha_agent.cli import main


class _IterationRuntime:
    def __init__(self, response: str, *, role: str) -> None:
        self.role = role
        self.llm = _IterationLLM(response)
        self.health_commands: list[str] = []

    def health_check(self, *, command: str):
        self.health_commands.append(command)
        return object()

    def metadata(self) -> dict[str, Any]:
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": self.role,
            "llm_model": "test-real-model",
            "llm_health_schema": "LLMHealthCheckResult",
        }


class _IterationLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.task = None

    def __call__(self, task):
        self.task = task
        return self.response


def _iteration_response() -> str:
    return json.dumps(
        {
            "candidates": [
                {
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
            ],
            "rejected_reason_codes": [],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )


def _invalid_iteration_response() -> str:
    return json.dumps(
        {
            "candidates": [
                {
                    "candidate_kind": "new_data_source",
                    "title": "Probe source with legacy field names",
                    "rationale": "This deliberately does not match IterationCandidate.",
                    "evidence_refs": ["goal:owner_autonomy_target"],
                    "tool_refs": ["source-probe"],
                    "discovery_queries": ["public derivatives open interest API"],
                    "source_probe_targets": [{"target": "binance_usdm_open_interest_history"}],
                    "human_review_required": True,
                    "direct_code_write_authorized": False,
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            ]
        }
    )


def test_iteration_cycle_cli_writes_markdown_and_json(
    capsys,
    monkeypatch,
    tmp_path,
) -> None:
    runtime = _IterationRuntime(_iteration_response(), role="planning")
    requested_roles: list[str] = []

    def fake_build_required_real_llm_runtime(*, role):
        requested_roles.append(role)
        return runtime

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        fake_build_required_real_llm_runtime,
    )
    markdown_path = tmp_path / "iteration-cycle.md"
    json_path = tmp_path / "iteration-cycle.json"

    exit_code = main(
        [
            "iteration-cycle",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(markdown_path),
            "--json-out",
            str(json_path),
            "--current-capital-usd",
            "300",
            "--max-candidates",
            "3",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    persisted_payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert requested_roles == ["planning"]
    assert runtime.health_commands == ["iteration-cycle"]
    assert runtime.llm.task.network_policy == "offline"
    assert payload["command"] == "iteration-cycle"
    assert payload["llm_required"] is True
    assert payload["auto_executes_changes"] is False
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["report"]["accepted"] is True
    assert payload["iteration_cycle_report_out"] == str(markdown_path)
    assert payload["json_out"] == str(json_path)
    assert persisted_payload["command"] == "iteration-cycle"
    assert "# Iteration Cycle Report" in markdown
    assert "Direct code write authorized: false" in markdown


def test_iteration_cycle_cli_fails_when_llm_schema_is_rejected(
    capsys,
    monkeypatch,
    tmp_path,
) -> None:
    runtime = _IterationRuntime(_invalid_iteration_response(), role="planning")

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda *, role: runtime,
    )
    markdown_path = tmp_path / "iteration-cycle.md"
    json_path = tmp_path / "iteration-cycle.json"

    exit_code = main(
        [
            "iteration-cycle",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--out",
            str(markdown_path),
            "--json-out",
            str(json_path),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["exit_code"] == 2
    assert payload["reason_code"] == "iteration_cycle_rejected"
    assert payload["report"]["accepted"] is False
    assert payload["report"]["rejected_reason_codes"] == ["invalid_llm_schema"]
    assert json_path.exists()
    assert markdown_path.exists()
