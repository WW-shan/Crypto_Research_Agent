# Phase 17 Creation-First Codex Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working creation-first autonomy loop where the product reads recent reports, asks the real LLM for a creation object, lets Codex write code in an isolated worktree, runs focused checks, writes reports, and advances a persistent autonomy branch.

**Architecture:** Add a small `crypto_alpha_agent.autonomy` package with strict models, artifact storage, report context loading, Codex command execution, git worktree management, and the creation-cycle orchestrator. The CLI remains the public product surface and continues to use the existing real LLM preflight; operations run it through one-shot systemd timers.

**Tech Stack:** Python 3.12, argparse CLI, Pydantic strict models, subprocess for `codex` and `git`, pytest, shell ops wrappers, systemd units.

---

## File Structure

- Create `src/crypto_alpha_agent/autonomy/__init__.py`
  - Public package marker for autonomy modules.
- Create `src/crypto_alpha_agent/autonomy/models.py`
  - Strict Pydantic models for creation objects, role notes, cycle reports, Codex outputs, and command specs.
- Create `src/crypto_alpha_agent/autonomy/store.py`
  - Filesystem-backed task artifact store and backlog reader/writer under `var/autonomy/`.
- Create `src/crypto_alpha_agent/autonomy/context.py`
  - Loads recent daily, iteration, weekly, and creation reports into bounded prompt context.
- Create `src/crypto_alpha_agent/autonomy/prompts.py`
  - Renders Director/Creator and Builder prompts from models and context.
- Create `src/crypto_alpha_agent/autonomy/codex_runner.py`
  - Dependency-injected subprocess wrapper for Codex health checks and builder execution.
- Create `src/crypto_alpha_agent/autonomy/worktrees.py`
  - Manages `autonomy/active` and per-task `autonomy/task/<task-id>` git worktrees under `var/autonomy/`.
- Create `src/crypto_alpha_agent/autonomy/cycle.py`
  - Orchestrates one creation-cycle run end to end.
- Modify `src/crypto_alpha_agent/pipeline/markdown.py`
  - Add `render_creation_cycle_markdown`.
- Modify `src/crypto_alpha_agent/cli.py`
  - Add `creation-cycle` subcommand and route it to planning LLM role.
- Create `ops/creation-cycle.sh`
  - One-shot VPS wrapper that runs from active autonomy worktree when present.
- Create `ops/systemd/crypto-alpha-creation.service`
  - systemd service for `ops/creation-cycle.sh`.
- Create `ops/systemd/crypto-alpha-creation.timer`
  - systemd timer for the creation loop.
- Modify `ops/install-systemd.sh`
  - Enable `crypto-alpha-creation.timer`.
- Modify `docs/vps-deployment.md`
  - Document creation-cycle outputs and active worktree behavior.
- Create `tests/test_creation_autonomy_store.py`
  - Model and store contract tests.
- Create `tests/test_creation_context.py`
  - Report context loading tests.
- Create `tests/test_codex_runner.py`
  - Codex command construction and failure tests.
- Create `tests/test_autonomy_worktrees.py`
  - Git worktree manager tests with local temporary repos.
- Create `tests/test_creation_cycle.py`
  - Orchestrator tests with fake LLM, fake Codex, and fake runner.
- Create `tests/test_creation_cycle_cli.py`
  - CLI contract tests.
- Modify `tests/test_vps_ops.py`
  - Add ops wrapper and systemd coverage.
- Modify `tests/test_documentation_contract.py`
  - Add deployment documentation contract terms.

## Task 1: Models And Artifact Store

**Files:**
- Create: `src/crypto_alpha_agent/autonomy/__init__.py`
- Create: `src/crypto_alpha_agent/autonomy/models.py`
- Create: `src/crypto_alpha_agent/autonomy/store.py`
- Test: `tests/test_creation_autonomy_store.py`

- [ ] **Step 1: Write failing model/store tests**

Add `tests/test_creation_autonomy_store.py`:

```python
from __future__ import annotations

import json

from crypto_alpha_agent.autonomy.models import CreationObject, CreationRoleNote
from crypto_alpha_agent.autonomy.store import AutonomyStore


def _creation(**overrides):
    payload = {
        "id": "creation-20260530-001",
        "kind": "family_idea",
        "title": "Funding open interest crowding",
        "hypothesis": "Funding and open interest changes can reveal crowded positioning.",
        "why_now": "Latest reports show funding exists while open interest is missing.",
        "first_code_change": "Add an open-interest-backed family probe path.",
        "expected_experiment": "Collect open interest and run a paper-only validation.",
        "status": "active",
        "continuation_reason": "Needs first source coverage run.",
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    payload.update(overrides)
    return CreationObject.model_validate(payload)


def test_creation_object_rejects_live_capital() -> None:
    try:
        _creation(uses_real_capital=True)
    except ValueError as exc:
        assert "uses_real_capital" in str(exc)
    else:
        raise AssertionError("live-capital creation should be rejected")


def test_autonomy_store_writes_task_artifacts_and_backlog(tmp_path) -> None:
    store = AutonomyStore(root=tmp_path / "autonomy", reports_root=tmp_path / "reports")
    creation = _creation()
    task = store.create_task(task_id="task-001", creation=creation)
    store.write_role_note(
        task.task_id,
        "director",
        CreationRoleNote(role="director", summary="Continue with open interest.", evidence_refs=["daily:latest"]),
    )
    store.write_json(task.task_id, "creation.json", creation.model_dump(mode="json"))
    store.append_backlog(creation)
    store.write_latest_report("# Creation Cycle Report\n")

    assert (task.path / "task.json").is_file()
    assert (task.path / "director.md").read_text(encoding="utf-8").startswith("# director")
    assert json.loads((task.path / "creation.json").read_text(encoding="utf-8"))["id"] == creation.id
    assert store.read_backlog()[0].id == creation.id
    assert (tmp_path / "reports" / "creation" / "latest.md").read_text(encoding="utf-8").startswith("# Creation")
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_creation_autonomy_store.py -q
```

Expected: FAIL because `crypto_alpha_agent.autonomy` does not exist.

- [ ] **Step 3: Implement strict models**

Create `src/crypto_alpha_agent/autonomy/__init__.py`:

```python
"""Creation-first Codex autonomy support."""
```

Create `src/crypto_alpha_agent/autonomy/models.py` with:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CreationKind = Literal[
    "family_idea",
    "data_source_idea",
    "validator_idea",
    "strategy_idea",
    "experiment_idea",
    "system_improvement_idea",
]
CreationStatus = Literal["active", "needs_data", "needs_fix", "stale", "archived"]
CreationRole = Literal["director", "scout", "creator", "builder", "runner", "critic"]


class _AutonomyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class CreationObject(_AutonomyModel):
    id: str = Field(min_length=1)
    kind: CreationKind
    title: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    why_now: str = Field(min_length=1)
    first_code_change: str = Field(min_length=1)
    expected_experiment: str = Field(min_length=1)
    status: CreationStatus = "active"
    continuation_reason: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    uses_real_capital: bool = False
    live_order_routing: bool = False

    @model_validator(mode="after")
    def _research_only(self) -> "CreationObject":
        if self.uses_real_capital:
            raise ValueError("uses_real_capital must be false")
        if self.live_order_routing:
            raise ValueError("live_order_routing must be false")
        return self


class CreationRoleNote(_AutonomyModel):
    role: CreationRole
    summary: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class CreationTaskRecord(_AutonomyModel):
    task_id: str = Field(min_length=1)
    creation_id: str = Field(min_length=1)
    path: Path


class CodexExecResult(_AutonomyModel):
    command: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    output_path: str | None = None


class CreationCycleReport(_AutonomyModel):
    task_id: str
    creation: CreationObject
    accepted: bool
    status: CreationStatus
    report_path: str
    json_path: str
    task_path: str
    patch_path: str | None = None
    runner_exit_code: int | None = None
    rejected_reason_codes: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    llm_required: Literal[True] = True
    codex_required: Literal[True] = True
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
```

- [ ] **Step 4: Implement artifact store**

Create `src/crypto_alpha_agent/autonomy/store.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_alpha_agent.autonomy.models import CreationObject, CreationRoleNote, CreationTaskRecord


class AutonomyStore:
    def __init__(self, *, root: str | Path, reports_root: str | Path) -> None:
        self.root = Path(root)
        self.reports_root = Path(reports_root)
        self.tasks_root = self.root / "tasks"
        self.backlog_path = self.root / "backlog.jsonl"

    def create_task(self, *, task_id: str, creation: CreationObject) -> CreationTaskRecord:
        task_path = self.tasks_root / task_id
        task_path.mkdir(parents=True, exist_ok=False)
        record = CreationTaskRecord(task_id=task_id, creation_id=creation.id, path=task_path)
        self.write_json(task_id, "task.json", record.model_dump(mode="json"))
        return record

    def write_json(self, task_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.tasks_root / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path

    def write_text(self, task_id: str, name: str, text: str) -> Path:
        path = self.tasks_root / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_role_note(self, task_id: str, role: str, note: CreationRoleNote) -> Path:
        text = f"# {role}\n\n{note.summary}\n"
        if note.evidence_refs:
            text += "\nEvidence refs:\n" + "".join(f"- {ref}\n" for ref in note.evidence_refs)
        return self.write_text(task_id, f"{role}.md", text)

    def append_backlog(self, creation: CreationObject) -> None:
        self.backlog_path.parent.mkdir(parents=True, exist_ok=True)
        with self.backlog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(creation.model_dump(mode="json"), sort_keys=True) + "\n")

    def read_backlog(self) -> list[CreationObject]:
        if not self.backlog_path.exists():
            return []
        creations: list[CreationObject] = []
        for line in self.backlog_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                creations.append(CreationObject.model_validate_json(line))
        return creations

    def write_latest_report(self, markdown: str) -> Path:
        path = self.reports_root / "creation" / "latest.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        return path

    def write_latest_json(self, payload: dict[str, Any]) -> Path:
        path = self.reports_root / "creation" / "latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path
```

- [ ] **Step 5: Run store tests**

Run:

```bash
pytest tests/test_creation_autonomy_store.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/crypto_alpha_agent/autonomy/__init__.py src/crypto_alpha_agent/autonomy/models.py src/crypto_alpha_agent/autonomy/store.py tests/test_creation_autonomy_store.py
git commit -m "feat: add creation autonomy models and store"
```

## Task 2: Report Context And Creation Prompts

**Files:**
- Create: `src/crypto_alpha_agent/autonomy/context.py`
- Create: `src/crypto_alpha_agent/autonomy/prompts.py`
- Test: `tests/test_creation_context.py`

- [ ] **Step 1: Write failing context tests**

Create `tests/test_creation_context.py`:

```python
from __future__ import annotations

from crypto_alpha_agent.autonomy.context import build_creation_context
from crypto_alpha_agent.autonomy.prompts import render_creator_prompt


def test_build_creation_context_reads_latest_reports_and_backlog(tmp_path) -> None:
    reports = tmp_path / "reports"
    (reports / "daily").mkdir(parents=True)
    (reports / "iteration").mkdir(parents=True)
    (reports / "daily" / "latest.md").write_text("# Daily\nStopped family: true\n", encoding="utf-8")
    (reports / "iteration" / "latest.md").write_text("# Iteration\nopen interest candidate\n", encoding="utf-8")
    (tmp_path / "autonomy").mkdir()
    (tmp_path / "autonomy" / "backlog.jsonl").write_text("", encoding="utf-8")

    context = build_creation_context(
        reports_root=reports,
        autonomy_root=tmp_path / "autonomy",
        max_chars_per_report=200,
    )

    assert context["reports"]["daily/latest.md"].startswith("# Daily")
    assert "open interest candidate" in context["reports"]["iteration/latest.md"]
    assert context["backlog_count"] == 0


def test_creator_prompt_includes_creation_first_instruction() -> None:
    prompt = render_creator_prompt(
        task_id="task-001",
        context={"reports": {"daily/latest.md": "Stopped family: true"}, "backlog_count": 0},
    )

    assert "create first" in prompt
    assert "CreationObject" in prompt
    assert "uses_real_capital" in prompt
    assert "live_order_routing" in prompt
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_creation_context.py -q
```

Expected: FAIL because `autonomy.context` and `autonomy.prompts` do not exist.

- [ ] **Step 3: Implement report context loading**

Create `src/crypto_alpha_agent/autonomy/context.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


REPORT_CANDIDATES = (
    "daily/latest.md",
    "iteration/latest.md",
    "weekly/latest.md",
    "creation/latest.md",
)


def build_creation_context(
    *,
    reports_root: str | Path,
    autonomy_root: str | Path,
    max_chars_per_report: int = 6000,
) -> dict[str, Any]:
    reports_path = Path(reports_root)
    autonomy_path = Path(autonomy_root)
    report_texts: dict[str, str] = {}
    for relative in REPORT_CANDIDATES:
        path = reports_path / relative
        if path.is_file():
            report_texts[relative] = path.read_text(encoding="utf-8")[:max_chars_per_report]
    backlog_path = autonomy_path / "backlog.jsonl"
    backlog_count = 0
    if backlog_path.is_file():
        backlog_count = sum(1 for line in backlog_path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "reports": report_texts,
        "backlog_count": backlog_count,
        "context_refs": sorted(report_texts.keys()),
    }
```

- [ ] **Step 4: Implement prompts**

Create `src/crypto_alpha_agent/autonomy/prompts.py`:

```python
from __future__ import annotations

import json
from typing import Any


def render_creator_prompt(*, task_id: str, context: dict[str, Any]) -> str:
    return (
        "You are the Creator role for a creation-first crypto research agent.\n"
        "Principle: create first, then test the creation, then learn from the result.\n"
        "Return exactly one JSON object matching CreationObject fields.\n"
        "Do not request real capital, live order routing, wallets, or exchange trading secrets.\n"
        "Set uses_real_capital=false and live_order_routing=false.\n"
        f"Task id: {task_id}\n"
        "Allowed kinds: family_idea, data_source_idea, validator_idea, strategy_idea, "
        "experiment_idea, system_improvement_idea.\n"
        "Context JSON:\n"
        f"{json.dumps(context, sort_keys=True, indent=2)}\n"
    )


def render_builder_prompt(*, creation_json: dict[str, Any], runner_commands: list[str]) -> str:
    return (
        "You are the Builder role. Write real project code for this creation object.\n"
        "Stay research-only. Do not add live trading, wallet access, exchange order routing, "
        "or secret reads.\n"
        "Prefer focused tests and minimal implementation that lets the project keep creating.\n"
        f"Creation JSON:\n{json.dumps(creation_json, sort_keys=True, indent=2)}\n"
        "Runner commands that will be executed after your work:\n"
        + "\n".join(f"- {command}" for command in runner_commands)
        + "\n"
    )
```

- [ ] **Step 5: Run context tests**

Run:

```bash
pytest tests/test_creation_context.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/crypto_alpha_agent/autonomy/context.py src/crypto_alpha_agent/autonomy/prompts.py tests/test_creation_context.py
git commit -m "feat: add creation context and prompts"
```

## Task 3: Codex Runner And Git Worktrees

**Files:**
- Create: `src/crypto_alpha_agent/autonomy/codex_runner.py`
- Create: `src/crypto_alpha_agent/autonomy/worktrees.py`
- Test: `tests/test_codex_runner.py`
- Test: `tests/test_autonomy_worktrees.py`

- [ ] **Step 1: Write failing Codex runner tests**

Create `tests/test_codex_runner.py`:

```python
from __future__ import annotations

from subprocess import CompletedProcess

import pytest

from crypto_alpha_agent.autonomy.codex_runner import CodexRunner, CodexUnavailableError


def test_codex_health_check_uses_real_codex_exec_command(tmp_path) -> None:
    calls = []

    def fake_run(command, *, input=None, text=True, capture_output=True, cwd=None, env=None, timeout=None):
        calls.append((command, input, cwd, timeout))
        return CompletedProcess(command, 0, stdout='{"event":"ok"}\n', stderr="")

    runner = CodexRunner(run_command=fake_run)
    result = runner.health_check(workdir=tmp_path)

    assert result.exit_code == 0
    command = calls[0][0]
    assert command[:2] == ["codex", "exec"]
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ask-for-approval" in command
    assert "never" in command


def test_codex_health_check_fails_closed_on_nonzero(tmp_path) -> None:
    def fake_run(command, *, input=None, text=True, capture_output=True, cwd=None, env=None, timeout=None):
        return CompletedProcess(command, 2, stdout="", stderr="provider unavailable")

    runner = CodexRunner(run_command=fake_run)

    with pytest.raises(CodexUnavailableError):
        runner.health_check(workdir=tmp_path)
```

- [ ] **Step 2: Write failing worktree tests**

Create `tests/test_autonomy_worktrees.py`:

```python
from __future__ import annotations

import subprocess

from crypto_alpha_agent.autonomy.worktrees import AutonomyWorktreeManager


def _init_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "README.md").write_text("root\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def test_worktree_manager_creates_active_and_task_worktrees(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=repo / "var" / "autonomy")
    active = manager.ensure_active_worktree()
    task = manager.create_task_worktree("task-001")

    assert active.is_dir()
    assert task.is_dir()
    assert (task / "README.md").read_text(encoding="utf-8") == "root\n"
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
pytest tests/test_codex_runner.py tests/test_autonomy_worktrees.py -q
```

Expected: FAIL because modules do not exist.

- [ ] **Step 4: Implement Codex runner**

Create `src/crypto_alpha_agent/autonomy/codex_runner.py`:

```python
from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from crypto_alpha_agent.autonomy.models import CodexExecResult
from crypto_alpha_agent.llm.redaction import redact_text


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class CodexUnavailableError(RuntimeError):
    pass


class CodexRunner:
    def __init__(self, *, run_command: RunCommand = subprocess.run, timeout_seconds: int = 1800) -> None:
        self._run_command = run_command
        self.timeout_seconds = timeout_seconds

    def health_check(self, *, workdir: str | Path) -> CodexExecResult:
        result = self.exec_prompt(
            workdir=workdir,
            prompt=(
                "Return a short confirmation that Codex is available. "
                "Do not modify files."
            ),
            sandbox="read-only",
            timeout_seconds=120,
        )
        if result.exit_code != 0:
            raise CodexUnavailableError(redact_text(result.stderr or result.stdout or "codex unavailable"))
        return result

    def exec_prompt(
        self,
        *,
        workdir: str | Path,
        prompt: str,
        sandbox: str = "workspace-write",
        timeout_seconds: int | None = None,
    ) -> CodexExecResult:
        command = [
            "codex",
            "exec",
            "--cd",
            str(Path(workdir)),
            "--sandbox",
            sandbox,
            "--ask-for-approval",
            "never",
            "--json",
            "-",
        ]
        env = _scrub_env(os.environ)
        completed = self._run_command(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=str(workdir),
            env=env,
            timeout=timeout_seconds or self.timeout_seconds,
        )
        return CodexExecResult(
            command=command,
            exit_code=int(completed.returncode),
            stdout=redact_text(completed.stdout or ""),
            stderr=redact_text(completed.stderr or ""),
        )


def _scrub_env(env: os._Environ[str]) -> dict[str, str]:
    allowed_prefixes = (
        "OPENAI_",
        "CODEX_",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "PATH",
        "HOME",
        "LANG",
        "LC_",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
    )
    clean: dict[str, str] = {}
    for key, value in env.items():
        if key.startswith(("BINANCE_", "BYBIT_", "OKX_", "DUNE_", "WALLET_", "PRIVATE_KEY")):
            continue
        if key in allowed_prefixes or any(key.startswith(prefix) for prefix in allowed_prefixes):
            clean[key] = value
    return clean
```

- [ ] **Step 5: Implement worktree manager**

Create `src/crypto_alpha_agent/autonomy/worktrees.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


class AutonomyWorktreeManager:
    def __init__(self, *, repo_root: str | Path, autonomy_root: str | Path) -> None:
        self.repo_root = Path(repo_root)
        self.autonomy_root = Path(autonomy_root)
        self.active_path = self.autonomy_root / "active-worktree"

    def ensure_active_worktree(self) -> Path:
        self.autonomy_root.mkdir(parents=True, exist_ok=True)
        self._ensure_branch("autonomy/active")
        if not self.active_path.exists():
            self._git("worktree", "add", str(self.active_path), "autonomy/active")
        return self.active_path

    def create_task_worktree(self, task_id: str) -> Path:
        self.ensure_active_worktree()
        task_branch = f"autonomy/task/{task_id}"
        task_path = self.autonomy_root / "worktrees" / task_id
        if task_path.exists():
            raise FileExistsError(task_path)
        self._git("branch", "-f", task_branch, "autonomy/active")
        self._git("worktree", "add", str(task_path), task_branch)
        return task_path

    def promote_task(self, *, task_id: str, message: str) -> None:
        task_path = self.autonomy_root / "worktrees" / task_id
        self._git_in(task_path, "add", "-A")
        diff = subprocess.run(["git", "-C", str(task_path), "diff", "--cached", "--quiet"], check=False)
        if diff.returncode == 1:
            self._git_in(task_path, "commit", "-m", message)
        self._git_in(self.active_path, "merge", "--ff-only", f"autonomy/task/{task_id}")

    def _ensure_branch(self, branch: str) -> None:
        result = subprocess.run(["git", "-C", str(self.repo_root), "rev-parse", "--verify", branch], check=False)
        if result.returncode != 0:
            self._git("branch", branch, "HEAD")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo_root), *args], check=True)

    def _git_in(self, path: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(path), *args], check=True)
```

- [ ] **Step 6: Run Codex/worktree tests**

Run:

```bash
pytest tests/test_codex_runner.py tests/test_autonomy_worktrees.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add src/crypto_alpha_agent/autonomy/codex_runner.py src/crypto_alpha_agent/autonomy/worktrees.py tests/test_codex_runner.py tests/test_autonomy_worktrees.py
git commit -m "feat: add codex runner and autonomy worktrees"
```

## Task 4: Creation Cycle Orchestrator

**Files:**
- Create: `src/crypto_alpha_agent/autonomy/cycle.py`
- Test: `tests/test_creation_cycle.py`

- [ ] **Step 1: Write failing cycle tests**

Create `tests/test_creation_cycle.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from crypto_alpha_agent.autonomy.cycle import run_creation_cycle


class FakeRuntime:
    def __init__(self, response: str) -> None:
        self.llm = lambda task: response

    def metadata(self):
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": "planning",
            "llm_model": "test-real-model",
        }


class FakeCodex:
    def __init__(self) -> None:
        self.prompts = []

    def health_check(self, *, workdir):
        return object()

    def exec_prompt(self, *, workdir, prompt, sandbox="workspace-write", timeout_seconds=None):
        self.prompts.append(prompt)
        path = Path(workdir) / "AUTONOMY_BUILDER_OUTPUT.txt"
        path.write_text("builder wrote code\n", encoding="utf-8")
        return type("Result", (), {"exit_code": 0, "stdout": "ok", "stderr": "", "command": ["codex"]})()


def _creation_response() -> str:
    return json.dumps(
        {
            "id": "creation-20260530-001",
            "kind": "family_idea",
            "title": "Funding open interest crowding",
            "hypothesis": "Funding and open interest can expose crowded positioning.",
            "why_now": "Latest report asks for open interest coverage.",
            "first_code_change": "Add the first open-interest-backed family path.",
            "expected_experiment": "Run source probe and paper-only validation.",
            "status": "active",
            "continuation_reason": "Needs source coverage.",
            "evidence_refs": ["iteration/latest.md"],
            "target_files": ["src/crypto_alpha_agent/strategy/funding_oi_crowding.py"],
            "verification_commands": ["python -m pytest tests/test_creation_autonomy_store.py -q"],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )


def test_creation_cycle_creates_task_artifacts_and_report(tmp_path) -> None:
    reports = tmp_path / "reports"
    (reports / "iteration").mkdir(parents=True)
    (reports / "iteration" / "latest.md").write_text("open interest candidate\n", encoding="utf-8")

    result = run_creation_cycle(
        repo_root=tmp_path,
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        reports_root=reports,
        autonomy_root=tmp_path / "autonomy",
        llm_runtime=FakeRuntime(_creation_response()),
        codex=FakeCodex(),
        max_creations=1,
        run_commands=False,
    )

    assert result.accepted is True
    assert result.creation.kind == "family_idea"
    assert Path(result.task_path).is_dir()
    assert Path(result.report_path).is_file()
    assert Path(result.json_path).is_file()
    assert (Path(result.task_path) / "builder-prompt.md").is_file()
    assert "open interest" in Path(result.report_path).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the failing cycle test**

Run:

```bash
pytest tests/test_creation_cycle.py -q
```

Expected: FAIL because `autonomy.cycle` does not exist.

- [ ] **Step 3: Implement cycle orchestration**

Create `src/crypto_alpha_agent/autonomy/cycle.py` with the following public function and helpers:

```python
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from crypto_alpha_agent.autonomy.codex_runner import CodexRunner
from crypto_alpha_agent.autonomy.context import build_creation_context
from crypto_alpha_agent.autonomy.models import CreationCycleReport, CreationObject, CreationRoleNote
from crypto_alpha_agent.autonomy.prompts import render_builder_prompt, render_creator_prompt
from crypto_alpha_agent.autonomy.store import AutonomyStore
from crypto_alpha_agent.autonomy.worktrees import AutonomyWorktreeManager
from crypto_alpha_agent.llm.runtime import parse_structured_llm_json
from crypto_alpha_agent.pipeline.markdown import render_creation_cycle_markdown


def run_creation_cycle(
    *,
    repo_root: str | Path,
    db_path: str | Path,
    memory_path: str | Path,
    reports_root: str | Path,
    autonomy_root: str | Path,
    llm_runtime: Any,
    codex: CodexRunner | Any | None = None,
    max_creations: int = 1,
    run_commands: bool = True,
) -> CreationCycleReport:
    repo_path = Path(repo_root)
    autonomy_path = Path(autonomy_root)
    reports_path = Path(reports_root)
    codex_runner = codex or CodexRunner()
    codex_runner.health_check(workdir=repo_path)

    context = build_creation_context(reports_root=reports_path, autonomy_root=autonomy_path)
    task_id = _task_id(context)
    creator_prompt = render_creator_prompt(task_id=task_id, context=context)
    raw_creation = llm_runtime.llm(creator_prompt)
    creation = _parse_creation(raw_creation)

    store = AutonomyStore(root=autonomy_path, reports_root=reports_path)
    task = store.create_task(task_id=task_id, creation=creation)
    store.write_role_note(
        task_id,
        "director",
        CreationRoleNote(role="director", summary="Selected one creation-first object from latest reports.", evidence_refs=context["context_refs"]),
    )
    store.write_json(task_id, "creation.json", creation.model_dump(mode="json"))

    worktrees = AutonomyWorktreeManager(repo_root=repo_path, autonomy_root=autonomy_path)
    task_worktree = worktrees.create_task_worktree(task_id) if run_commands else task.path
    runner_commands = creation.verification_commands or ["python -m pytest tests/test_creation_autonomy_store.py -q"]
    builder_prompt = render_builder_prompt(creation_json=creation.model_dump(mode="json"), runner_commands=runner_commands)
    store.write_text(task_id, "builder-prompt.md", builder_prompt)
    builder_result = codex_runner.exec_prompt(workdir=task_worktree, prompt=builder_prompt)
    store.write_json(task_id, "builder-output.json", _result_payload(builder_result))

    runner_exit_code = None
    if run_commands:
        runner_exit_code = _run_verification(task_worktree, runner_commands, task.path / "runner.md")
        _write_patch(task_worktree, task.path / "patch.diff")
        if runner_exit_code == 0:
            worktrees.promote_task(task_id=task_id, message=f"autonomy: {creation.title}")
    else:
        (task.path / "runner.md").write_text("Verification skipped by run_commands=false.\n", encoding="utf-8")

    accepted = builder_result.exit_code == 0
    report = CreationCycleReport(
        task_id=task_id,
        creation=creation,
        accepted=accepted,
        status=creation.status if accepted else "needs_fix",
        report_path=str(reports_path / "creation" / "latest.md"),
        json_path=str(reports_path / "creation" / "latest.json"),
        task_path=str(task.path),
        patch_path=str(task.path / "patch.diff"),
        runner_exit_code=runner_exit_code,
        rejected_reason_codes=[] if accepted else ["codex_builder_failed"],
        next_actions=[creation.continuation_reason],
    )
    markdown = render_creation_cycle_markdown(report)
    store.write_latest_report(markdown)
    store.write_latest_json({"command": "creation-cycle", "report": report.model_dump(mode="json"), **llm_runtime.metadata()})
    store.append_backlog(creation)
    return report


def _parse_creation(raw_creation: Any) -> CreationObject:
    if isinstance(raw_creation, str):
        return parse_structured_llm_json(raw_creation, CreationObject)
    try:
        return CreationObject.model_validate(raw_creation)
    except ValidationError as exc:
        raise ValueError("creation object failed schema validation") from exc


def _task_id(context: dict[str, Any]) -> str:
    material = json.dumps(context, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"creation-{timestamp}-{digest}"


def _result_payload(result: Any) -> dict[str, Any]:
    return {
        "command": list(getattr(result, "command", [])),
        "exit_code": int(getattr(result, "exit_code", 1)),
        "stdout": str(getattr(result, "stdout", "")),
        "stderr": str(getattr(result, "stderr", "")),
    }


def _run_verification(workdir: Path, commands: list[str], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    worst = 0
    lines: list[str] = []
    for command in commands:
        completed = subprocess.run(command, cwd=workdir, shell=True, text=True, capture_output=True)
        worst = max(worst, completed.returncode)
        lines.extend([f"$ {command}", completed.stdout, completed.stderr, f"exit_code={completed.returncode}", ""])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return worst


def _write_patch(workdir: Path, patch_path: Path) -> None:
    completed = subprocess.run(["git", "-C", str(workdir), "diff", "--binary"], text=True, capture_output=True, check=False)
    patch_path.write_text(completed.stdout, encoding="utf-8")
```

- [ ] **Step 4: Run cycle tests**

Run:

```bash
pytest tests/test_creation_cycle.py tests/test_creation_autonomy_store.py tests/test_creation_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add src/crypto_alpha_agent/autonomy/cycle.py tests/test_creation_cycle.py
git commit -m "feat: add creation cycle orchestrator"
```

## Task 5: Markdown Renderer And CLI Command

**Files:**
- Modify: `src/crypto_alpha_agent/pipeline/markdown.py`
- Modify: `src/crypto_alpha_agent/cli.py`
- Test: `tests/test_creation_cycle_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_creation_cycle_cli.py`:

```python
from __future__ import annotations

import json

from crypto_alpha_agent.cli import main


class _Runtime:
    def __init__(self) -> None:
        self.health_commands = []
        self.llm = lambda task: json.dumps(
            {
                "id": "creation-20260530-001",
                "kind": "system_improvement_idea",
                "title": "Keep creation loop moving",
                "hypothesis": "A minimal autonomy report improves iteration.",
                "why_now": "The project needs creation-first feedback.",
                "first_code_change": "Write a small autonomy report.",
                "expected_experiment": "Run focused tests.",
                "status": "active",
                "continuation_reason": "Use result in the next cycle.",
                "evidence_refs": ["creation-test"],
                "target_files": [],
                "verification_commands": ["python -m pytest tests/test_creation_autonomy_store.py -q"],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )

    def health_check(self, *, command):
        self.health_commands.append(command)
        return object()

    def metadata(self):
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": "planning",
            "llm_model": "test-real-model",
        }


class _Codex:
    def health_check(self, *, workdir):
        return object()

    def exec_prompt(self, *, workdir, prompt, sandbox="workspace-write", timeout_seconds=None):
        return type("Result", (), {"exit_code": 0, "stdout": "ok", "stderr": "", "command": ["codex"]})()


def test_creation_cycle_cli_writes_latest_report_and_json(capsys, monkeypatch, tmp_path) -> None:
    runtime = _Runtime()
    monkeypatch.setattr("crypto_alpha_agent.cli.build_required_real_llm_runtime", lambda *, role: runtime)
    monkeypatch.setattr("crypto_alpha_agent.cli.CodexRunner", lambda: _Codex())

    exit_code = main(
        [
            "creation-cycle",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--task-root",
            str(tmp_path / "autonomy" / "tasks"),
            "--worktree-root",
            str(tmp_path / "autonomy" / "worktrees"),
            "--autonomy-root",
            str(tmp_path / "autonomy"),
            "--reports-root",
            str(tmp_path / "reports"),
            "--repo-root",
            str(tmp_path),
            "--no-run-commands",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert runtime.health_commands == ["creation-cycle"]
    assert payload["command"] == "creation-cycle"
    assert payload["llm_required"] is True
    assert payload["codex_required"] is True
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert (tmp_path / "reports" / "creation" / "latest.md").is_file()
    assert (tmp_path / "reports" / "creation" / "latest.json").is_file()
```

- [ ] **Step 2: Run failing CLI test**

Run:

```bash
pytest tests/test_creation_cycle_cli.py -q
```

Expected: FAIL because `creation-cycle` command is missing.

- [ ] **Step 3: Add markdown renderer**

Modify `src/crypto_alpha_agent/pipeline/markdown.py`:

```python
def render_creation_cycle_markdown(report: CreationCycleReport) -> str:
    lines = [
        "# Creation Cycle Report",
        "",
        "## Safety",
        f"LLM required: {_bool_text(report.llm_required)}",
        f"Codex required: {_bool_text(report.codex_required)}",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Creation",
        f"Task id: {_escape_text(report.task_id)}",
        f"Accepted: {_bool_text(report.accepted)}",
        f"Status: {_escape_text(report.status)}",
        f"Kind: {_escape_text(report.creation.kind)}",
        f"Title: {_escape_text(report.creation.title)}",
        f"Hypothesis: {_escape_text(report.creation.hypothesis)}",
        f"Why now: {_escape_text(report.creation.why_now)}",
        f"First code change: {_escape_text(report.creation.first_code_change)}",
        f"Expected experiment: {_escape_text(report.creation.expected_experiment)}",
        "",
        "## Artifacts",
        f"Task path: {_escape_text(report.task_path)}",
        f"Patch path: {_escape_text(report.patch_path or 'none')}",
        f"Runner exit code: {_escape_text(str(report.runner_exit_code) if report.runner_exit_code is not None else 'not-run')}",
        "",
        "## Next Actions",
    ]
    lines.extend(_bullet_lines(report.next_actions or [report.creation.continuation_reason]))
    if report.rejected_reason_codes:
        lines.extend(["", "## Rejected Reason Codes"])
        lines.extend(_bullet_lines(report.rejected_reason_codes))
    return "\n".join(lines) + "\n"
```

Also import `CreationCycleReport` near the other report imports.

- [ ] **Step 4: Add CLI parser and handler**

Modify `src/crypto_alpha_agent/cli.py`:

- Import `CodexRunner` and `run_creation_cycle`.
- Add `creation-cycle` to `_llm_role_for_command` planning role set.
- Add parser arguments:

```python
creation_cycle_parser = subparsers.add_parser(
    "creation-cycle",
    help="Run one creation-first Codex autonomy cycle.",
)
creation_cycle_parser.add_argument("--db", required=True, type=Path)
creation_cycle_parser.add_argument("--memory", required=True, type=Path)
creation_cycle_parser.add_argument("--autonomy-root", type=Path, default=Path("var/autonomy"))
creation_cycle_parser.add_argument("--task-root", type=Path, default=Path("var/autonomy/tasks"))
creation_cycle_parser.add_argument("--worktree-root", type=Path, default=Path("var/autonomy/worktrees"))
creation_cycle_parser.add_argument("--reports-root", type=Path, default=Path("var/reports"))
creation_cycle_parser.add_argument("--repo-root", type=Path, default=Path("."))
creation_cycle_parser.add_argument("--max-creations", type=_positive_int, default=1)
creation_cycle_parser.add_argument("--no-run-commands", action="store_true")
creation_cycle_parser.set_defaults(handler=_handle_creation_cycle, parser=creation_cycle_parser)
```

Add handler:

```python
def _handle_creation_cycle(args: argparse.Namespace) -> dict[str, Any]:
    runtime: RealLLMRuntime = args.llm_runtime
    try:
        report = run_creation_cycle(
            repo_root=args.repo_root,
            db_path=args.db,
            memory_path=args.memory,
            reports_root=args.reports_root,
            autonomy_root=args.autonomy_root,
            llm_runtime=runtime,
            codex=CodexRunner(),
            max_creations=args.max_creations,
            run_commands=not args.no_run_commands,
        )
    except (LLMProviderError, LLMRuntimeError, ValueError, RuntimeError) as exc:
        args.parser.error(str(exc))
        raise AssertionError("argparse parser.error should exit") from exc
    return {
        "command": "creation-cycle",
        "exit_code": 0 if report.accepted else 2,
        "report": report.model_dump(mode="json"),
        "llm_required": report.llm_required,
        "codex_required": report.codex_required,
        "uses_real_capital": False,
        "live_order_routing": False,
        **runtime.metadata(),
    }
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
pytest tests/test_creation_cycle_cli.py tests/test_cli_llm_native_gate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add src/crypto_alpha_agent/pipeline/markdown.py src/crypto_alpha_agent/cli.py tests/test_creation_cycle_cli.py
git commit -m "feat: expose creation cycle CLI"
```

## Task 6: VPS Operations Integration

**Files:**
- Create: `ops/creation-cycle.sh`
- Create: `ops/systemd/crypto-alpha-creation.service`
- Create: `ops/systemd/crypto-alpha-creation.timer`
- Modify: `ops/install-systemd.sh`
- Modify: `docs/vps-deployment.md`
- Modify: `tests/test_vps_ops.py`
- Modify: `tests/test_documentation_contract.py`

- [ ] **Step 1: Add failing ops tests**

Modify `tests/test_vps_ops.py`:

```python
def test_creation_wrapper_runs_creation_cycle_with_artifact_contract() -> None:
    script = read_text("ops/creation-cycle.sh")

    for expected in [
        "set -euo pipefail",
        "creation-cycle",
        "--autonomy-root",
        "--reports-root",
        "--max-creations",
        "var/reports/creation/latest.md",
        "var/reports/creation/latest.json",
        "CRYPTO_ALPHA_AGENT_DRY_RUN",
        "CRYPTO_ALPHA_AGENT_ACTIVE_WORKTREE",
    ]:
        assert expected in script
```

Extend existing required files list with:

```python
"ops/creation-cycle.sh",
"ops/systemd/crypto-alpha-creation.service",
"ops/systemd/crypto-alpha-creation.timer",
```

Extend expected service scripts with:

```python
"crypto-alpha-creation.service": "ops/creation-cycle.sh",
```

- [ ] **Step 2: Run failing ops tests**

Run:

```bash
pytest tests/test_vps_ops.py -q
```

Expected: FAIL because creation ops files are missing.

- [ ] **Step 3: Create ops wrapper**

Create executable `ops/creation-cycle.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="${CRYPTO_ALPHA_AGENT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ACTIVE_WORKTREE="${CRYPTO_ALPHA_AGENT_ACTIVE_WORKTREE:-${REPO}/var/autonomy/active-worktree}"
RUN_REPO="$REPO"
if [[ -d "$ACTIVE_WORKTREE" ]]; then
  RUN_REPO="$ACTIVE_WORKTREE"
fi
cd "$RUN_REPO"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
db_path="${CRYPTO_ALPHA_AGENT_DB:-var/research.sqlite}"
memory_path="${CRYPTO_ALPHA_AGENT_MEMORY:-var/memory/evidence.jsonl}"
autonomy_root="${CRYPTO_ALPHA_AGENT_AUTONOMY_ROOT:-var/autonomy}"
reports_root="${CRYPTO_ALPHA_AGENT_REPORTS_ROOT:-var/reports}"
max_creations="${CRYPTO_ALPHA_AGENT_MAX_CREATIONS:-1}"
log_dir="${CRYPTO_ALPHA_AGENT_CREATION_LOG_DIR:-var/log/creation-cycle}"
stdout_log="${log_dir}/${timestamp}.stdout.log"
stderr_log="${log_dir}/${timestamp}.stderr.log"

mkdir -p "$(dirname "$db_path")" "$(dirname "$memory_path")" "$reports_root/creation" "$log_dir"

command=(
  uv run crypto-alpha-agent creation-cycle
  --db "$db_path"
  --memory "$memory_path"
  --autonomy-root "$autonomy_root"
  --task-root "${autonomy_root}/tasks"
  --worktree-root "${autonomy_root}/worktrees"
  --reports-root "$reports_root"
  --repo-root "$RUN_REPO"
  --max-creations "$max_creations"
)

if [[ "${CRYPTO_ALPHA_AGENT_DRY_RUN:-0}" == "1" ]]; then
  printf 'DRY RUN:'
  printf ' %q' "${command[@]}"
  printf '\n'
  printf 'DRY RUN: latest markdown %q\n' "${reports_root}/creation/latest.md"
  printf 'DRY RUN: latest json %q\n' "${reports_root}/creation/latest.json"
  printf 'stdout: %s\nstderr: %s\n' "$stdout_log" "$stderr_log"
  exit 0
fi

exec >"$stdout_log" 2>"$stderr_log"
"${command[@]}"
```

Run:

```bash
chmod +x ops/creation-cycle.sh
```

- [ ] **Step 4: Add systemd units**

Create `ops/systemd/crypto-alpha-creation.service`:

```ini
[Unit]
Description=Crypto Alpha Agent creation-first Codex autonomy cycle
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/crypto-alpha-agent
ExecStart=/opt/crypto-alpha-agent/ops/creation-cycle.sh
```

Create `ops/systemd/crypto-alpha-creation.timer`:

```ini
[Unit]
Description=Run Crypto Alpha Agent creation cycle every 4 hours

[Timer]
OnCalendar=*-*-* 00/4:20:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 5: Update install script**

Modify `ops/install-systemd.sh` enable list:

```bash
sudo systemctl enable --now \
  crypto-alpha-daily.timer \
  crypto-alpha-weekly.timer \
  crypto-alpha-monthly.timer \
  crypto-alpha-backup.timer \
  crypto-alpha-creation.timer
```

Also update the dry-run printed enable command to include `crypto-alpha-creation.timer`.

- [ ] **Step 6: Update deployment docs**

Modify `docs/vps-deployment.md` to include these exact phrases:

```text
crypto-alpha-creation.timer
ops/creation-cycle.sh
creation-cycle
var/autonomy/backlog.jsonl
var/autonomy/active-worktree
var/reports/creation/latest.md
var/reports/creation/latest.json
Codex must be available or the creation cycle exits nonzero
```

- [ ] **Step 7: Run ops and documentation tests**

Run:

```bash
pytest tests/test_vps_ops.py tests/test_documentation_contract.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

Run:

```bash
git add ops/creation-cycle.sh ops/systemd/crypto-alpha-creation.service ops/systemd/crypto-alpha-creation.timer ops/install-systemd.sh docs/vps-deployment.md tests/test_vps_ops.py tests/test_documentation_contract.py
git commit -m "feat: schedule creation cycle on vps"
```

## Task 7: End-To-End Verification

**Files:**
- Modify only files needed to fix failures from the verification commands.

- [ ] **Step 1: Run focused autonomy test suite**

Run:

```bash
pytest \
  tests/test_creation_autonomy_store.py \
  tests/test_creation_context.py \
  tests/test_codex_runner.py \
  tests/test_autonomy_worktrees.py \
  tests/test_creation_cycle.py \
  tests/test_creation_cycle_cli.py \
  tests/test_vps_ops.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run existing affected tests**

Run:

```bash
pytest \
  tests/test_iteration_controller.py \
  tests/test_iteration_cycle_cli.py \
  tests/test_cli_llm_native_gate.py \
  tests/test_documentation_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
ruff check src/crypto_alpha_agent/autonomy src/crypto_alpha_agent/cli.py src/crypto_alpha_agent/pipeline/markdown.py tests/test_creation_*.py tests/test_codex_runner.py tests/test_autonomy_worktrees.py
```

Expected: PASS.

- [ ] **Step 4: Run a dry CLI command**

Run:

```bash
CRYPTO_ALPHA_AGENT_DRY_RUN=1 bash ops/creation-cycle.sh
```

Expected output contains:

```text
DRY RUN:
creation-cycle
var/reports/creation/latest.md
var/reports/creation/latest.json
```

- [ ] **Step 5: Commit fixes if needed**

If any verification command required code changes, commit them:

```bash
git add src tests ops docs
git commit -m "fix: stabilize creation cycle verification"
```

If no changes were required, do not create an empty commit.

## Self-Review Checklist

- Spec coverage:
  - Codex/LLM required: Tasks 3, 4, and 5.
  - Creation backlog: Task 1 and Task 4.
  - Role-shaped flow: Task 2 and Task 4.
  - Builder writes code in isolated worktree: Task 3 and Task 4.
  - Runner feedback instead of hard stop: Task 4.
  - Latest reports and JSON artifacts: Task 1, Task 4, Task 5, and Task 6.
  - VPS one-shot timer: Task 6.
  - No live capital/order routing: Task 1 model validation and Task 5 payload.
- Placeholder scan:
  - The plan uses no open placeholder markers and names concrete paths, commands, and expected outputs.
- Type consistency:
  - `CreationObject`, `CreationRoleNote`, `CreationCycleReport`, `CodexRunner`, `AutonomyStore`, and `run_creation_cycle` names are consistent across tests, implementation, CLI, and markdown.
