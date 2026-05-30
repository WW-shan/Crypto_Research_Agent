from __future__ import annotations

import json
from pathlib import Path
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
        task_path = self.tasks_root / task_id
        task_path.mkdir(parents=True, exist_ok=False)
        record = CreationTaskRecord(task_id=task_id, creation_id=creation.id, path=task_path)
        self.write_json(task_id, "task.json", record.model_dump(mode="json"))
        return record

    def write_json(self, task_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.tasks_root / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json_text(payload), encoding="utf-8")
        return path

    def write_text(self, task_id: str, name: str, text: str) -> Path:
        path = self.tasks_root / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_role_note(self, task_id: str, role: str, note: CreationRoleNote) -> Path:
        return self.write_text(task_id, f"{role}.md", _role_note_markdown(role, note))

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
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


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
