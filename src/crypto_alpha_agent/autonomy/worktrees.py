from __future__ import annotations

import re
import subprocess
from pathlib import Path


class AutonomyWorktreeManager:
    def __init__(self, *, repo_root: Path, autonomy_root: Path) -> None:
        self.repo_root = repo_root
        self.autonomy_root = autonomy_root

    def ensure_active_worktree(self) -> Path:
        active_path = self.autonomy_root / "active-worktree"
        self.autonomy_root.mkdir(parents=True, exist_ok=True)
        self._ensure_branch("autonomy/active", "HEAD")
        self._ensure_worktree(active_path, "autonomy/active")
        return active_path

    def create_task_worktree(self, task_id: str) -> Path:
        _validate_task_id(task_id)
        self.ensure_active_worktree()
        task_branch = f"autonomy/task/{task_id}"
        task_path = self.autonomy_root / "worktrees" / task_id
        task_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_branch(task_branch, "autonomy/active")
        self._ensure_worktree(task_path, task_branch)
        return task_path

    def promote_task(self, *, task_id: str, message: str) -> None:
        _validate_task_id(task_id)
        active_path = self.ensure_active_worktree()
        task_path = self.autonomy_root / "worktrees" / task_id
        task_branch = f"autonomy/task/{task_id}"
        if not (task_path / ".git").exists():
            raise FileNotFoundError(f"task worktree does not exist: {task_path}")

        _git(task_path, "add", "-A")
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=task_path,
        )
        if staged.returncode == 1:
            _git(task_path, "commit", "-m", message)
        elif staged.returncode != 0:
            staged.check_returncode()

        _git(active_path, "merge", "--ff-only", task_branch)

    def _ensure_branch(self, branch: str, start_point: str) -> None:
        if _branch_exists(self.repo_root, branch):
            return
        _git(self.repo_root, "branch", branch, start_point)

    def _ensure_worktree(self, path: Path, branch: str) -> None:
        if path.exists():
            self._validate_existing_worktree(path, branch)
            return
        _git(self.repo_root, "worktree", "add", str(path), branch)

    def _validate_existing_worktree(self, path: Path, branch: str) -> None:
        if not path.is_dir():
            raise ValueError(f"existing worktree path is not a directory: {path}")
        try:
            expected_common_dir = _git_path(
                self.repo_root,
                "rev-parse",
                "--git-common-dir",
            )
            actual_common_dir = _git_path(path, "rev-parse", "--git-common-dir")
            actual_branch = _git(path, "branch", "--show-current").stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"existing path is not a valid git worktree: {path}") from exc

        if actual_common_dir != expected_common_dir:
            raise ValueError(
                f"existing worktree {path} belongs to a different git repository"
            )
        if actual_branch != branch:
            raise ValueError(
                f"existing worktree {path} is on branch {actual_branch!r}; "
                f"expected {branch!r}"
            )


def _branch_exists(repo_root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


def _git_path(cwd: Path, *args: str) -> Path:
    value = _git(cwd, *args).stdout.strip()
    path = Path(value)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def _validate_task_id(task_id: str) -> None:
    if task_id in {".", ".."}:
        raise ValueError(f"unsafe task_id: {task_id!r}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", task_id):
        raise ValueError(f"unsafe task_id: {task_id!r}")
    branch = f"autonomy/task/{task_id}"
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(f"unsafe task_id: {task_id!r}")
