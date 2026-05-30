from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPORT_PATHS = (
    ("daily/latest.md", ("daily", "latest.md")),
    ("iteration/latest.md", ("iteration", "latest.md")),
    ("weekly/latest.md", ("weekly", "latest.md")),
    ("creation/latest.md", ("creation", "latest.md")),
)


def build_creation_context(
    *,
    reports_root: str | Path,
    autonomy_root: str | Path,
    max_chars_per_report: int = 6000,
    max_backlog_entries: int = 5,
) -> dict[str, Any]:
    reports_base = Path(reports_root)
    autonomy_base = Path(autonomy_root)
    limit = max(0, max_chars_per_report)

    reports: dict[str, str] = {}
    for report_key, path_parts in _REPORT_PATHS:
        path = reports_base.joinpath(*path_parts)
        if path.is_file():
            reports[report_key] = path.read_text(encoding="utf-8")[:limit]

    context_refs = sorted(reports)
    backlog_recent = _recent_backlog_entries(
        autonomy_base / "backlog.jsonl",
        max_entries=max_backlog_entries,
    )
    return {
        "reports": reports,
        "backlog_count": _backlog_count(autonomy_base / "backlog.jsonl"),
        "backlog_recent": backlog_recent,
        "context_refs": context_refs,
    }


def _backlog_count(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _recent_backlog_entries(path: Path, *, max_entries: int) -> list[dict[str, Any]]:
    if not path.is_file() or max_entries <= 0:
        return []
    entries: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                entries.append(_summarize_backlog_entry(raw))
    return entries[-max_entries:]


def _summarize_backlog_entry(raw: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "kind",
        "status",
        "title",
        "continuation_reason",
        "evidence_refs",
        "target_files",
    )
    return {key: raw[key] for key in keys if key in raw}
