from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import crypto_alpha_agent.autonomy.cycle as cycle_module
from crypto_alpha_agent.autonomy.codex_runner import CodexUnavailableError
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


def test_creation_cycle_rejects_nonzero_injected_health_check_before_llm(
    tmp_path: Path,
) -> None:
    runtime = FakeRuntime(_creation_payload())
    codex = FakeCodex(health_exit_code=99, health_stderr="codex unavailable")

    with pytest.raises(CodexUnavailableError, match="codex unavailable"):
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

    assert runtime.prompts == []
    assert codex.events == ["health"]
    assert codex.exec_workdirs == []


def test_creation_cycle_rejects_malformed_health_check_before_llm(
    tmp_path: Path,
) -> None:
    runtime = FakeRuntime(_creation_payload())
    codex = FakeCodex(health_result=object())

    with pytest.raises(CodexUnavailableError, match="malformed"):
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

    assert runtime.prompts == []
    assert codex.events == ["health"]
    assert codex.exec_workdirs == []


def test_creation_cycle_with_commands_patches_and_promotes_new_builder_file(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    payload = _creation_payload(
        verification_commands=["python -m pytest test_created.py -q"],
    )
    runtime = FakeRuntime(payload)
    codex = FakeCodex(
        exit_code=0,
        created_files={
            "created.txt": "created by fake codex\n",
            "test_created.py": (
                "from pathlib import Path\n\n"
                "def test_created_file_exists():\n"
                "    assert Path('created.txt').read_text() == 'created by fake codex\\n'\n"
            ),
        },
    )

    report = run_creation_cycle(
        repo_root=repo,
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=autonomy_root,
        llm_runtime=runtime,
        codex=codex,
        run_commands=True,
    )

    assert report.accepted is True
    assert report.runner_exit_code == 0
    assert report.patch_path is not None
    assert "created.txt" in Path(report.patch_path).read_text(encoding="utf-8")
    assert (autonomy_root / "active-worktree" / "created.txt").read_text(
        encoding="utf-8"
    ) == "created by fake codex\n"
    assert codex.exec_workdirs == [autonomy_root / "worktrees" / report.task_id]


def test_creation_cycle_command_mode_builder_failure_does_not_promote(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    payload = _creation_payload(
        verification_commands=["python -m pytest test_created.py -q"],
    )
    codex = FakeCodex(
        exit_code=2,
        stderr="builder failed",
        created_files={
            "created.txt": "created by fake codex\n",
            "test_created.py": "def test_created():\n    assert True\n",
        },
    )

    report = run_creation_cycle(
        repo_root=repo,
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=autonomy_root,
        llm_runtime=FakeRuntime(payload),
        codex=codex,
        run_commands=True,
    )

    assert report.accepted is False
    assert report.status == "needs_fix"
    assert report.rejected_reason_codes == ["codex_builder_failed"]
    assert not (autonomy_root / "active-worktree" / "created.txt").exists()


def test_creation_cycle_command_mode_runner_failure_does_not_promote_or_stage(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    payload = _creation_payload(
        verification_commands=["pytest test_created.py -q"],
    )
    codex = FakeCodex(
        exit_code=0,
        created_files={
            "created.txt": "created by fake codex\n",
            "test_created.py": "def test_failure():\n    assert False\n",
        },
    )

    report = run_creation_cycle(
        repo_root=repo,
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=autonomy_root,
        llm_runtime=FakeRuntime(payload),
        codex=codex,
        run_commands=True,
    )

    task_worktree = autonomy_root / "worktrees" / report.task_id
    assert report.accepted is False
    assert report.status == "needs_fix"
    assert report.rejected_reason_codes == ["verification_failed"]
    assert report.runner_exit_code == 1
    assert not (autonomy_root / "active-worktree" / "created.txt").exists()
    status_lines = _git_output(task_worktree, "status", "--short").splitlines()
    assert "?? created.txt" in status_lines
    assert "?? test_created.py" in status_lines
    assert all(line.startswith("?? ") for line in status_lines)


@pytest.mark.parametrize("command", ["env", "bash -c 'echo unsafe'", 'python -c "print(1)"'])
def test_creation_cycle_rejects_unsafe_runner_commands_without_promotion(
    tmp_path: Path,
    command: str,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    payload = _creation_payload(verification_commands=[command])
    codex = FakeCodex(exit_code=0, created_files={"created.txt": "created by fake codex\n"})

    report = run_creation_cycle(
        repo_root=repo,
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=autonomy_root,
        llm_runtime=FakeRuntime(payload),
        codex=codex,
        run_commands=True,
    )

    runner_text = (Path(report.task_path) / "runner.md").read_text(encoding="utf-8")
    assert report.accepted is False
    assert report.status == "needs_fix"
    assert report.rejected_reason_codes == ["verification_failed"]
    assert report.runner_exit_code == 126
    assert "Rejected unsafe verification command" in runner_text
    assert not (autonomy_root / "active-worktree" / "created.txt").exists()


def test_creation_cycle_runner_scrubs_env_and_redacts_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy_url = "http://proxy-user:proxy-password@proxy.example:8080"
    monkeypatch.setenv("BINANCE_API_SECRET", "binance-secret")
    monkeypatch.setenv("HTTPS_PROXY", proxy_url)
    report = run_creation_cycle(
        repo_root=_init_repo(tmp_path / "repo"),
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=tmp_path / "autonomy",
        llm_runtime=FakeRuntime(
            _creation_payload(verification_commands=["pytest test_redaction.py -q"])
        ),
        codex=FakeCodex(
            exit_code=0,
            created_files={
                "test_redaction.py": (
                    "import os\n\n"
                    "def test_runner_redaction():\n"
                    "    assert os.environ.get('BINANCE_API_SECRET') is None\n"
                    "    raise AssertionError(\n"
                    "        os.environ['HTTPS_PROXY'] + ' Bearer runner-secret'\n"
                    "    )\n"
                )
            },
        ),
        run_commands=True,
    )

    runner_text = (Path(report.task_path) / "runner.md").read_text(encoding="utf-8")
    assert report.accepted is False
    assert "binance-secret" not in runner_text
    assert proxy_url not in runner_text
    assert "proxy-user" not in runner_text
    assert "proxy-password" not in runner_text
    assert "runner-secret" not in runner_text
    assert "<redacted>" in runner_text


def test_creation_cycle_promotion_failure_writes_rejected_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingPromotionWorktreeManager:
        def __init__(self, *, repo_root: Path, autonomy_root: Path) -> None:
            self.repo_root = repo_root
            self.autonomy_root = autonomy_root

        def create_task_worktree(self, task_id: str) -> Path:
            path = self.autonomy_root / "worktrees" / task_id
            path.mkdir(parents=True)
            _git(path, "init")
            _git(path, "config", "user.email", "test@example.com")
            _git(path, "config", "user.name", "Test User")
            (path / "README.md").write_text("base\n", encoding="utf-8")
            _git(path, "add", "README.md")
            _git(path, "commit", "-m", "Initial commit")
            return path

        def promote_task(self, *, task_id: str, message: str) -> None:
            raise RuntimeError("promotion refused")

    monkeypatch.setattr(
        cycle_module,
        "AutonomyWorktreeManager",
        FailingPromotionWorktreeManager,
    )
    payload = _creation_payload(verification_commands=["pytest test_created.py -q"])

    report = run_creation_cycle(
        repo_root=tmp_path / "repo",
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=tmp_path / "reports",
        autonomy_root=tmp_path / "autonomy",
        llm_runtime=FakeRuntime(payload),
        codex=FakeCodex(
            exit_code=0,
            created_files={"test_created.py": "def test_created():\n    assert True\n"},
        ),
        run_commands=True,
    )

    latest_json = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
    assert report.accepted is False
    assert report.status == "needs_fix"
    assert report.rejected_reason_codes == ["promotion_failed"]
    assert "promotion refused" in " ".join(report.next_actions)
    assert latest_json["report"]["rejected_reason_codes"] == ["promotion_failed"]
    assert (tmp_path / "autonomy" / "backlog.jsonl").is_file()


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
        health_exit_code: int = 0,
        health_stderr: str = "",
        health_result: object | None = None,
        created_file: str | None = None,
        created_files: dict[str, str] | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.health_exit_code = health_exit_code
        self.health_stderr = health_stderr
        self.health_result = health_result
        self.created_file = created_file
        self.created_files = {} if created_files is None else created_files
        self.events: list[str] = []
        self.exec_workdirs: list[Path] = []

    def health_check(self, *, workdir: Path) -> object:
        self.events.append("health")
        if self.health_result is not None:
            return self.health_result
        return CodexExecResult(
            command=["codex", "health"],
            exit_code=self.health_exit_code,
            stderr=self.health_stderr,
        )

    def exec_prompt(self, *, workdir: Path, prompt: str) -> CodexExecResult:
        self.events.append("exec")
        self.exec_workdirs.append(workdir)
        if self.created_file is not None:
            (workdir / self.created_file).write_text(
                "created by fake codex\n",
                encoding="utf-8",
            )
        for name, text in self.created_files.items():
            path = workdir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return CodexExecResult(
            command=["codex", "exec"],
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
        )


def _creation_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
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
    payload.update(overrides)
    return payload


def _write_report(reports_root: Path, name: str, text: str) -> None:
    path = reports_root / name / "latest.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")


def _init_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "Initial commit")
    return path


def _git(path: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", *args],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )


def _git_output(path: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
