from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from crypto_alpha_agent.autonomy.worktrees import AutonomyWorktreeManager


def test_worktree_manager_creates_active_and_task_worktrees(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=autonomy_root)

    active_path = manager.ensure_active_worktree()
    task_path = manager.create_task_worktree("task-001")

    assert active_path == autonomy_root / "active-worktree"
    assert task_path == autonomy_root / "worktrees" / "task-001"
    assert _git(repo, "rev-parse", "--verify", "autonomy/active").returncode == 0
    assert _git(repo, "rev-parse", "--verify", "autonomy/task/task-001").returncode == 0
    assert (active_path / "README.md").read_text(encoding="utf-8") == "base\n"
    assert (task_path / "README.md").read_text(encoding="utf-8") == "base\n"


def test_promote_task_commits_task_changes_and_updates_active_worktree(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=autonomy_root)
    active_path = manager.ensure_active_worktree()
    task_path = manager.create_task_worktree("task-001")
    (task_path / "feature.txt").write_text("created by task\n", encoding="utf-8")

    manager.promote_task(task_id="task-001", message="Promote task 001")

    assert (active_path / "feature.txt").read_text(encoding="utf-8") == "created by task\n"
    assert _git(task_path, "status", "--short").stdout == ""
    log = _git(active_path, "log", "--oneline", "-1").stdout
    assert "Promote task 001" in log


def test_promote_task_without_changes_does_not_create_empty_commit(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=autonomy_root)
    active_path = manager.ensure_active_worktree()
    manager.create_task_worktree("task-001")
    before = _git(active_path, "rev-parse", "HEAD").stdout.strip()

    manager.promote_task(task_id="task-001", message="No-op promotion")

    after = _git(active_path, "rev-parse", "HEAD").stdout.strip()
    assert after == before
    assert "No-op promotion" not in _git(active_path, "log", "--oneline", "-1").stdout


def test_existing_active_worktree_on_wrong_branch_is_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    active_path = autonomy_root / "active-worktree"
    _git(repo, "branch", "wrong-active")
    _git(repo, "worktree", "add", str(active_path), "wrong-active")
    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=autonomy_root)

    with pytest.raises(ValueError, match="autonomy/active"):
        manager.ensure_active_worktree()


def test_existing_task_worktree_on_wrong_branch_is_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=autonomy_root)
    manager.ensure_active_worktree()
    task_path = autonomy_root / "worktrees" / "task-001"
    _git(repo, "branch", "wrong-task")
    _git(repo, "worktree", "add", str(task_path), "wrong-task")

    with pytest.raises(ValueError, match="autonomy/task/task-001"):
        manager.create_task_worktree("task-001")


def test_promote_task_rejects_wrong_branch_task_worktree_before_staging(
    tmp_path: Path,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    autonomy_root = tmp_path / "autonomy"
    manager = AutonomyWorktreeManager(repo_root=repo, autonomy_root=autonomy_root)
    active_path = manager.ensure_active_worktree()
    _git(repo, "branch", "autonomy/task/task-001", "autonomy/active")
    _git(repo, "branch", "wrong-task", "autonomy/active")
    task_path = autonomy_root / "worktrees" / "task-001"
    _git(repo, "worktree", "add", str(task_path), "wrong-task")
    (task_path / "wrong.txt").write_text("do not promote\n", encoding="utf-8")

    with pytest.raises(ValueError, match="autonomy/task/task-001"):
        manager.promote_task(task_id="task-001", message="Promote task 001")

    assert not (active_path / "wrong.txt").exists()
    assert _git(task_path, "status", "--short").stdout == "?? wrong.txt\n"


@pytest.mark.parametrize("task_id", [".", "..", "feature.lock", "-bad"])
def test_worktree_manager_rejects_unsafe_task_ids(
    tmp_path: Path,
    task_id: str,
) -> None:
    repo = _init_repo(tmp_path / "repo")
    manager = AutonomyWorktreeManager(
        repo_root=repo,
        autonomy_root=tmp_path / "autonomy",
    )

    with pytest.raises(ValueError):
        manager.create_task_worktree(task_id)


def _init_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "Initial commit")
    return path


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        text=True,
        capture_output=True,
        check=True,
    )
