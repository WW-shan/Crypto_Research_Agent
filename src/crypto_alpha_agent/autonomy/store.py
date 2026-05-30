from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any

from crypto_alpha_agent.autonomy.models import (
    CreationObject,
    CreationRoleNote,
    CreationTaskRecord,
)


class AutonomyStore:
    def __init__(self, *, root: str | Path, reports_root: str | Path) -> None:
        self.root = Path(root)
        self.reports_root = Path(reports_root)
        self.tasks_root = self.root / "tasks"
        self.backlog_path = self.root / "backlog.jsonl"

    def create_task(self, *, task_id: str, creation: CreationObject) -> CreationTaskRecord:
        safe_task_id = _safe_relative_path(task_id)
        task_path = self.tasks_root / safe_task_id
        task_path.mkdir(parents=True, exist_ok=False)
        record = CreationTaskRecord(task_id=str(safe_task_id), creation_id=creation.id, path=task_path)
        self.write_json(str(safe_task_id), "task.json", record.model_dump(mode="json"))
        return record

    def write_json(self, task_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.tasks_root / _safe_relative_path(task_id) / _safe_relative_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json_text(payload), encoding="utf-8")
        return path

    def write_text(self, task_id: str, name: str, text: str) -> Path:
        path = self.tasks_root / _safe_relative_path(task_id) / _safe_relative_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_role_note(self, task_id: str, role: str, note: CreationRoleNote) -> Path:
        if role != note.role:
            raise ValueError("role must match note.role")
        safe_role = _safe_relative_path(note.role)
        return self.write_text(task_id, f"{safe_role}.md", _role_note_markdown(str(safe_role), note))

    def append_backlog(self, creation: CreationObject) -> None:
        self.backlog_path.parent.mkdir(parents=True, exist_ok=True)
        with self.backlog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(creation.model_dump(mode="json"), sort_keys=True))
            handle.write("\n")

    def read_backlog(self) -> list[CreationObject]:
        if not self.backlog_path.exists():
            return []
        return [
            CreationObject.model_validate_json(line)
            for line in self.backlog_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def write_latest_report(self, markdown: str) -> Path:
        path = self.reports_root / "creation" / "latest.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        return path

    def write_latest_json(self, payload: dict[str, Any]) -> Path:
        path = self.reports_root / "creation" / "latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json_text(payload), encoding="utf-8")
        return path


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _role_note_markdown(role: str, note: CreationRoleNote) -> str:
    lines = [
        f"# {role}",
        "",
        note.summary,
    ]
    if note.evidence_refs:
        lines.extend(["", "Evidence refs:"])
        lines.extend(f"- {ref}" for ref in note.evidence_refs)
    return "\n".join(lines) + "\n"


def _safe_relative_path(raw: str) -> Path:
    if not raw:
        raise ValueError("path component must not be empty")
    path = Path(raw)
    if path.is_absolute() or PureWindowsPath(raw).is_absolute():
        raise ValueError(f"path component must be relative: {raw}")
    if "/" in raw or "\\" in raw:
        raise ValueError(f"path component must not contain separators: {raw}")
    if raw in {".", ".."}:
        raise ValueError(f"path component is not safe: {raw}")
    return path
