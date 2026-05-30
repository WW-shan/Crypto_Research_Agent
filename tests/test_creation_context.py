from __future__ import annotations

import json
from pathlib import Path

from crypto_alpha_agent.autonomy.context import build_creation_context
from crypto_alpha_agent.autonomy.prompts import (
    render_builder_prompt,
    render_creator_prompt,
)


def test_creation_context_reads_latest_reports_and_backlog_count(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    autonomy_root = tmp_path / "autonomy"
    (reports_root / "daily").mkdir(parents=True)
    (reports_root / "iteration").mkdir(parents=True)
    (reports_root / "daily" / "latest.md").write_text("Daily report\n", encoding="utf-8")
    (reports_root / "iteration" / "latest.md").write_text(
        "Iteration report\n", encoding="utf-8"
    )
    autonomy_root.mkdir()
    (autonomy_root / "backlog.jsonl").write_text(
        "\n{\"id\":\"one\"}\n  \n{\"id\":\"two\"}\n", encoding="utf-8"
    )

    context = build_creation_context(
        reports_root=reports_root,
        autonomy_root=autonomy_root,
    )

    assert context == {
        "reports": {
            "daily/latest.md": "Daily report\n",
            "iteration/latest.md": "Iteration report\n",
        },
        "backlog_count": 2,
        "context_refs": ["daily/latest.md", "iteration/latest.md"],
    }


def test_creation_context_bounds_report_text(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    autonomy_root = tmp_path / "autonomy"
    (reports_root / "daily").mkdir(parents=True)
    (reports_root / "daily" / "latest.md").write_text("abcdef", encoding="utf-8")

    context = build_creation_context(
        reports_root=reports_root,
        autonomy_root=autonomy_root,
        max_chars_per_report=3,
    )

    assert context["reports"]["daily/latest.md"] == "abc"


def test_creator_prompt_requires_creation_first_json_contract() -> None:
    context = {
        "reports": {"daily/latest.md": "Daily report"},
        "backlog_count": 1,
        "context_refs": ["daily/latest.md"],
    }

    prompt = render_creator_prompt(task_id="task-123", context=context)

    assert "task-123" in prompt
    assert "create first" in prompt.lower()
    assert "CreationObject" in prompt
    assert "uses_real_capital" in prompt
    assert "live_order_routing" in prompt
    assert "uses_real_capital=false" in prompt
    assert "live_order_routing=false" in prompt
    assert json.dumps(context, sort_keys=True, indent=2) in prompt


def test_builder_prompt_includes_creation_runner_and_forbidden_live_behavior() -> None:
    creation_json = {
        "id": "creation-1",
        "kind": "strategy_idea",
        "title": "Funding OI paper probe",
        "hypothesis": "Funding and OI can identify crowded positioning.",
        "uses_real_capital": False,
        "live_order_routing": False,
    }

    prompt = render_builder_prompt(
        creation_json=creation_json,
        runner_commands=["uv run pytest tests/test_creation_context.py -q"],
    )

    assert "Funding OI paper probe" in prompt
    assert "uv run pytest tests/test_creation_context.py -q" in prompt
    assert "live trading" in prompt.lower()
    assert "wallet" in prompt.lower()
    assert "exchange order routing" in prompt.lower()
    assert "secret reads" in prompt.lower()
