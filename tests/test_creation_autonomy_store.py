from __future__ import annotations

import json
from pathlib import Path

from crypto_alpha_agent.autonomy.models import (
    CreationCycleReport,
    CreationObject,
    CreationRoleNote,
)
from crypto_alpha_agent.autonomy.store import AutonomyStore


def _creation(**overrides: object) -> CreationObject:
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

    try:
        _creation(live_order_routing=True)
    except ValueError as exc:
        assert "live_order_routing" in str(exc)
    else:
        raise AssertionError("live-routing creation should be rejected")


def test_autonomy_store_writes_task_artifacts(tmp_path: Path) -> None:
    store = AutonomyStore(root=tmp_path / "autonomy", reports_root=tmp_path / "reports")
    creation = _creation()
    task = store.create_task(task_id="task-001", creation=creation)

    store.write_json(task.task_id, "creation.json", creation.model_dump(mode="json"))
    store.write_text(task.task_id, "builder-prompt.md", "# Builder\n")

    assert task.path == tmp_path / "autonomy" / "tasks" / "task-001"
    assert json.loads((task.path / "task.json").read_text(encoding="utf-8")) == {
        "creation_id": creation.id,
        "path": str(task.path),
        "task_id": "task-001",
    }
    assert json.loads((task.path / "creation.json").read_text(encoding="utf-8"))[
        "id"
    ] == creation.id
    assert (task.path / "builder-prompt.md").read_text(encoding="utf-8") == "# Builder\n"


def test_autonomy_store_writes_role_note(tmp_path: Path) -> None:
    store = AutonomyStore(root=tmp_path / "autonomy", reports_root=tmp_path / "reports")
    creation = _creation()
    task = store.create_task(task_id="task-001", creation=creation)

    path = store.write_role_note(
        task.task_id,
        "director",
        CreationRoleNote(
            role="director",
            summary="Continue with open interest.",
            evidence_refs=["daily:latest"],
        ),
    )

    assert path == task.path / "director.md"
    assert path.read_text(encoding="utf-8") == (
        "# director\n\n"
        "Continue with open interest.\n\n"
        "Evidence refs:\n"
        "- daily:latest\n"
    )


def test_autonomy_store_backlog_roundtrip(tmp_path: Path) -> None:
    store = AutonomyStore(root=tmp_path / "autonomy", reports_root=tmp_path / "reports")
    creation = _creation(evidence_refs=["daily:latest"], target_files=["src/example.py"])

    store.append_backlog(creation)

    assert store.read_backlog() == [creation]
    assert (tmp_path / "autonomy" / "backlog.jsonl").read_text(encoding="utf-8").endswith(
        "\n"
    )


def test_autonomy_store_writes_latest_report_files(tmp_path: Path) -> None:
    store = AutonomyStore(root=tmp_path / "autonomy", reports_root=tmp_path / "reports")
    report = CreationCycleReport(
        task_id="task-001",
        creation=_creation(),
        accepted=True,
        status="active",
        report_path=str(tmp_path / "reports" / "creation" / "latest.md"),
        json_path=str(tmp_path / "reports" / "creation" / "latest.json"),
        task_path=str(tmp_path / "autonomy" / "tasks" / "task-001"),
        next_actions=["Needs first source coverage run."],
    )

    markdown_path = store.write_latest_report("# Creation Cycle Report\n")
    json_path = store.write_latest_json({"report": report.model_dump(mode="json")})

    assert markdown_path == tmp_path / "reports" / "creation" / "latest.md"
    assert markdown_path.read_text(encoding="utf-8").startswith("# Creation")
    assert json_path == tmp_path / "reports" / "creation" / "latest.json"
    assert json.loads(json_path.read_text(encoding="utf-8"))["report"]["task_id"] == "task-001"
