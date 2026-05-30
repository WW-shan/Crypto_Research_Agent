from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from crypto_alpha_agent.autonomy.cycle import run_creation_cycle
from crypto_alpha_agent.autonomy.models import CodexExecResult


def test_creation_cycle_without_commands_writes_artifacts_and_reports(
    tmp_path: Path,
) -> None:
    reports_root = tmp_path / "reports"
    autonomy_root = tmp_path / "autonomy"
    _write_report(reports_root, "daily", "Open-interest coverage is missing.\n")
    runtime = FakeRuntime(_creation_payload())
    codex = FakeCodex(exit_code=0, stdout="builder created files")

    report = run_creation_cycle(
        repo_root=tmp_path / "repo",
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=reports_root,
        autonomy_root=autonomy_root,
        llm_runtime=runtime,
        codex=codex,
        run_commands=False,
    )

    task_path = Path(report.task_path)
    assert report.accepted is True
    assert report.status == "active"
    assert report.patch_path is None
    assert "Funding open interest crowding" in report.creation.title
    assert codex.exec_workdirs == [task_path]
    assert "Open-interest coverage is missing" in runtime.prompts[0]

    assert (task_path / "task.json").is_file()
    assert (task_path / "director.md").read_text(encoding="utf-8").startswith("# director")
    assert json.loads((task_path / "creation.json").read_text(encoding="utf-8"))[
        "title"
    ] == "Funding open interest crowding"
    assert "Funding open interest crowding" in (
        task_path / "builder-prompt.md"
    ).read_text(encoding="utf-8")
    assert json.loads((task_path / "builder-output.json").read_text(encoding="utf-8"))[
        "stdout"
    ] == "builder created files"
    assert "Verification skipped" in (task_path / "runner.md").read_text(encoding="utf-8")

    latest_md = (reports_root / "creation" / "latest.md").read_text(encoding="utf-8")
    latest_json = json.loads(
        (reports_root / "creation" / "latest.json").read_text(encoding="utf-8")
    )
    backlog_lines = (autonomy_root / "backlog.jsonl").read_text(encoding="utf-8").splitlines()
    assert "Funding open interest crowding" in latest_md
    assert "open interest" in latest_md.lower()
    assert latest_json["report"]["task_id"] == report.task_id
    assert latest_json["llm_metadata"] == {"provider": "fake"}
    assert len(backlog_lines) == 1
    assert json.loads(backlog_lines[0])["id"] == "creation-open-interest"


def test_creation_cycle_calls_codex_health_check_before_builder_prompt(
    tmp_path: Path,
) -> None:
    runtime = FakeRuntime(_creation_payload())
    codex = FakeCodex(exit_code=0)

    run_creation_cycle(
        repo_root=tmp_path / "repo",
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=tmp_path / "autonomy",
        llm_runtime=runtime,
        codex=codex,
        run_commands=False,
    )

    assert codex.events[0] == "health"
    assert codex.events.index("health") < codex.events.index("exec")


def test_creation_cycle_builder_failure_rejects_but_writes_artifacts(
    tmp_path: Path,
) -> None:
    codex = FakeCodex(exit_code=12, stderr="builder failed")

    report = run_creation_cycle(
        repo_root=tmp_path / "repo",
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=tmp_path / "autonomy",
        llm_runtime=FakeRuntime(_creation_payload()),
        codex=codex,
        run_commands=False,
    )

    task_path = Path(report.task_path)
    assert report.accepted is False
    assert report.status == "needs_fix"
    assert report.rejected_reason_codes == ["codex_builder_failed"]
    assert (task_path / "builder-output.json").is_file()
    assert (task_path / "runner.md").is_file()
    assert "needs_fix" in Path(report.report_path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"uses_real_capital": True},
        {"live_order_routing": True},
        {"title": ""},
    ],
)
def test_creation_cycle_rejects_unsafe_or_invalid_llm_creation(
    tmp_path: Path,
    bad_payload: dict[str, object],
) -> None:
    payload = _creation_payload()
    payload.update(bad_payload)

    with pytest.raises(ValidationError):
        run_creation_cycle(
            repo_root=tmp_path / "repo",
            db_path=tmp_path / "research.sqlite",
            memory_path=tmp_path / "memory.jsonl",
            reports_root=tmp_path / "reports",
            autonomy_root=tmp_path / "autonomy",
            llm_runtime=FakeRuntime(payload),
            codex=FakeCodex(exit_code=0),
            run_commands=False,
        )


class FakeRuntime:
    def __init__(self, response: dict[str, Any] | str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def llm(self, prompt: str) -> dict[str, Any] | str:
        self.prompts.append(prompt)
        return self.response

    def metadata(self) -> dict[str, str]:
        return {"provider": "fake"}


class FakeCodex:
    def __init__(
        self,
        *,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.events: list[str] = []
        self.exec_workdirs: list[Path] = []

    def health_check(self, *, workdir: Path) -> CodexExecResult:
        self.events.append("health")
        return CodexExecResult(command=["codex", "health"], exit_code=0)

    def exec_prompt(self, *, workdir: Path, prompt: str) -> CodexExecResult:
        self.events.append("exec")
        self.exec_workdirs.append(workdir)
        return CodexExecResult(
            command=["codex", "exec"],
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def _creation_payload() -> dict[str, Any]:
    return {
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


def _write_report(reports_root: Path, name: str, text: str) -> None:
    path = reports_root / name / "latest.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
