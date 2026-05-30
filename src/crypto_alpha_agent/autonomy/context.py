from __future__ import annotations

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
) -> dict[str, Any]:
    reports_base = Path(reports_root)
    autonomy_base = Path(autonomy_root)
    limit = max(0, max_chars_per_report)

    reports: dict[str, str] = {}
    for report_key, path_parts in _REPORT_PATHS:
        path = reports_base.joinpath(*path_parts)
        if path.exists():
            reports[report_key] = path.read_text(encoding="utf-8")[:limit]

    context_refs = sorted(reports)
    return {
        "reports": reports,
        "backlog_count": _backlog_count(autonomy_base / "backlog.jsonl"),
        "context_refs": context_refs,
    }


def _backlog_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
