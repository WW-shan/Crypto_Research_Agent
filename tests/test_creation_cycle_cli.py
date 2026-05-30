from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_alpha_agent.autonomy.models import CodexExecResult
from crypto_alpha_agent.cli import main


class _CreationRuntime:
    def __init__(self, response: str, *, role: str) -> None:
        self.role = role
        self.llm = _CreationLLM(response)
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


class _CreationLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class _FakeCodex:
    def __init__(self, *, builder_exit_code: int = 0) -> None:
        self.builder_exit_code = builder_exit_code
        self.health_workdirs: list[Path] = []
        self.exec_workdirs: list[Path] = []

    def health_check(self, *, workdir: Path) -> CodexExecResult:
        self.health_workdirs.append(workdir)
        return CodexExecResult(command=["codex", "health"], exit_code=0)

    def exec_prompt(self, *, workdir: Path, prompt: str) -> CodexExecResult:
        self.exec_workdirs.append(workdir)
        return CodexExecResult(
            command=["codex", "exec"],
            exit_code=self.builder_exit_code,
            stdout="builder ok" if self.builder_exit_code == 0 else "",
            stderr="" if self.builder_exit_code == 0 else "builder failed",
        )


def test_creation_cycle_cli_writes_latest_reports_and_payload(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime = _CreationRuntime(_creation_response(), role="planning")
    requested_roles: list[str] = []
    codex = _FakeCodex(builder_exit_code=0)

    def fake_build_required_real_llm_runtime(*, role):
        requested_roles.append(role)
        return runtime

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        fake_build_required_real_llm_runtime,
    )
    monkeypatch.setattr("crypto_alpha_agent.cli.CodexRunner", lambda: codex, raising=False)

    reports_root = tmp_path / "reports"
    exit_code = main(
        [
            "creation-cycle",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--autonomy-root",
            str(tmp_path / "autonomy"),
            "--reports-root",
            str(reports_root),
            "--repo-root",
            str(tmp_path / "repo"),
            "--no-run-commands",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    markdown_path = reports_root / "creation" / "latest.md"
    json_path = reports_root / "creation" / "latest.json"
    latest_json = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert requested_roles == ["planning"]
    assert runtime.health_commands == ["creation-cycle"]
    assert codex.health_workdirs == [tmp_path / "repo"]
    assert len(codex.exec_workdirs) == 1
    assert payload["command"] == "creation-cycle"
    assert payload["exit_code"] == 0
    assert payload["accepted"] is True
    assert payload["reason_code"] is None
    assert payload["llm_required"] is True
    assert payload["codex_required"] is True
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["creation_report_out"] == str(markdown_path)
    assert payload["json_out"] == str(json_path)
    assert payload["report"]["accepted"] is True
    assert payload["report"]["runner_exit_code"] is None
    assert payload["llm_role"] == "planning"
    assert latest_json["report"]["task_id"] == payload["report"]["task_id"]
    assert "# Creation Cycle Report" in markdown
    assert "LLM required: true" in markdown
    assert "Codex required: true" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown


def test_creation_cycle_cli_returns_nonzero_for_rejected_builder_result(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime = _CreationRuntime(_creation_response(), role="planning")
    codex = _FakeCodex(builder_exit_code=23)

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda *, role: runtime,
    )
    monkeypatch.setattr("crypto_alpha_agent.cli.CodexRunner", lambda: codex, raising=False)

    reports_root = tmp_path / "reports"
    exit_code = main(
        [
            "creation-cycle",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--reports-root",
            str(reports_root),
            "--autonomy-root",
            str(tmp_path / "autonomy"),
            "--repo-root",
            str(tmp_path / "repo"),
            "--no-run-commands",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["exit_code"] == 2
    assert payload["accepted"] is False
    assert payload["reason_code"] == "creation_cycle_rejected"
    assert payload["report"]["status"] == "needs_fix"
    assert payload["report"]["rejected_reason_codes"] == ["codex_builder_failed"]
    assert (reports_root / "creation" / "latest.md").is_file()
    assert (reports_root / "creation" / "latest.json").is_file()


def _creation_response() -> str:
    return json.dumps(
        {
            "id": "creation-open-interest",
            "kind": "family_idea",
            "title": "Funding open interest crowding",
            "hypothesis": "Funding and open interest changes can reveal crowded positioning.",
            "why_now": "Latest reports show funding exists while open-interest data is missing.",
            "first_code_change": "Add an open-interest-backed family probe path.",
            "expected_experiment": "Collect open interest and run a paper-only validation.",
            "status": "active",
            "continuation_reason": "Needs first source coverage run.",
            "evidence_refs": ["daily/latest.md"],
            "target_files": ["src/crypto_alpha_agent/strategy/funding_oi_crowding.py"],
            "verification_commands": [],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )
