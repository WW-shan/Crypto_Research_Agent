from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch


class _SmokeRuntime:
    def __init__(self, role: str) -> None:
        self.role = role

    def health_check(self, *, command: str):
        return object()

    def metadata(self) -> dict[str, object]:
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": self.role,
            "llm_model": "test-real-model",
        }

    def structured_call(self, task: Any, output_model: type[Any]) -> Any:
        from crypto_alpha_agent.llm.runtime import parse_structured_llm_json

        evidence_refs = list(getattr(task, "evidence_refs", []) or ["runtime:test"])
        schema_name = str(getattr(task, "schema_name", "RuntimeCommandJudgement"))
        return parse_structured_llm_json(
            json.dumps(
                {
                    "schema_name": schema_name,
                    "decision": "add_data",
                    "rationale": "Smoke command facts were reviewed by the test LLM runtime.",
                    "evidence_refs": evidence_refs,
                    "next_actions": ["Continue with research-only validation."],
                    "uses_real_capital": False,
                    "live_order_routing": False,
                }
            ),
            output_model,
        )


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "crypto_alpha_agent.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _json_from_cli(*args: str) -> dict[str, object]:
    from crypto_alpha_agent.cli import main

    stdout = StringIO()
    with (
        patch(
            "crypto_alpha_agent.cli.build_required_real_llm_runtime",
            lambda role="research": _SmokeRuntime(role),
        ),
        redirect_stdout(stdout),
    ):
        exit_code = main(list(args))
    assert exit_code == 0, stdout.getvalue()
    return json.loads(stdout.getvalue())


def _write_event_log(path: Path) -> None:
    events = [
        {
            "timestamp": "2026-05-16T09:30:00Z",
            "event_type": "opportunity_scored",
            "run_id": "cli-smoke",
            "opportunity_id": "opp-cli-1",
            "decision": "approve",
            "action": "paper_trade",
            "reason_codes": ["positive_expected_value"],
            "metrics": {"expected_net_pnl_usd": 12.5, "confidence": 0.8},
            "evidence_refs": ["scanner:offline"],
            "artifact_refs": ["backtests/opp-cli-1.json"],
        },
        {
            "timestamp": "2026-05-16T10:15:00Z",
            "event_type": "risk_guard",
            "run_id": "cli-smoke",
            "opportunity_id": "opp-cli-2",
            "decision": "block",
            "action": "skip",
            "reason_codes": ["daily_loss_limit_reached"],
            "metrics": {"expected_net_pnl_usd": -2.5},
        },
        {
            "timestamp": "2026-05-17T01:00:00Z",
            "event_type": "risk_guard",
            "run_id": "cli-smoke-next",
            "decision": "approve",
            "action": "paper_trade",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(event) for event in events)
        + '\n{"timestamp": "2026-05-16T11:00:00Z", "event_type": ',
        encoding="utf-8",
    )


def test_repo_ignores_local_macos_and_cache_artifacts():
    ignore_text = Path(".gitignore").read_text(encoding="utf-8")

    assert ".DS_Store" in ignore_text
    assert ".ruff_cache/" in ignore_text
    assert ".venv/" in ignore_text
    assert ".env" in ignore_text
    assert ".env.*" in ignore_text
    assert "!.env.example" in ignore_text
    assert ".agents/" in ignore_text
    assert ".claude/" in ignore_text
    assert "var/" in ignore_text
    assert "*.pyc" in ignore_text


def test_pytest_default_collection_ignores_runtime_worktrees():
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = config["tool"]["pytest"]["ini_options"]

    assert pytest_options["testpaths"] == ["tests"]
    assert "var" in pytest_options["norecursedirs"]
    assert ".worktrees" in pytest_options["norecursedirs"]


def test_cli_help_lists_operator_commands():
    result = _run_cli("--help")

    assert result.returncode == 0
    assert "scan" in result.stdout
    assert "research" in result.stdout
    assert "backtest" in result.stdout
    assert "paper" in result.stdout
    assert "report" in result.stdout
    assert "replay" in result.stdout


def test_cli_dry_run_commands_emit_machine_readable_json():
    for command in ("scan", "research", "backtest", "paper"):
        payload = _json_from_cli(command, "--dry-run")

        assert payload["command"] == command
        assert payload["mode"] == "dry_run"
        assert payload["live_api_calls"] is True
        assert payload["live_api_call_types"] == ["llm_health_check"]
        assert payload["live_market_api_calls"] is False
        assert payload["uses_real_capital"] is False
        assert payload["llm_provider"] == "real"
        assert payload["used_fake_llm"] is False
        assert payload["llm_judgement"]["schema_name"] == "RuntimeCommandJudgement"
        assert payload["llm_judgement"]["evidence_refs"] == [f"runtime:{command}"]


def test_cli_report_generates_daily_report_from_event_jsonl(tmp_path):
    event_path = tmp_path / "events.jsonl"
    _write_event_log(event_path)

    payload = _json_from_cli("report", "--events", str(event_path), "--date", "2026-05-16")

    assert payload["command"] == "report"
    assert payload["event_path"] == str(event_path)
    report = payload["report"]
    assert report["date"] == "2026-05-16"
    assert report["total_events"] == 2
    assert report["event_type_counts"] == {"opportunity_scored": 1, "risk_guard": 1}
    assert report["approvals"] == 1
    assert report["blocks"] == 1
    assert report["skipped_event_lines"] == 1
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_judgement"]["schema_name"] == "RuntimeCommandJudgement"
    assert payload["llm_judgement"]["evidence_refs"] == ["runtime:report"]


def test_cli_replay_counts_events_and_can_regenerate_report(tmp_path):
    event_path = tmp_path / "events.jsonl"
    _write_event_log(event_path)

    counts = _json_from_cli("replay", "--events", str(event_path))

    assert counts["command"] == "replay"
    assert counts["event_path"] == str(event_path)
    assert counts["loaded_events"] == 3
    assert counts["skipped_event_lines"] == 1
    assert counts["event_type_counts"] == {"opportunity_scored": 1, "risk_guard": 2}
    assert counts["llm_provider"] == "real"
    assert counts["used_fake_llm"] is False
    assert counts["llm_judgement"]["schema_name"] == "RuntimeCommandJudgement"
    assert counts["llm_judgement"]["evidence_refs"] == ["runtime:replay"]

    replayed = _json_from_cli("replay", "--events", str(event_path), "--date", "2026-05-16")

    assert replayed["loaded_events"] == 3
    assert replayed["report"]["total_events"] == 2
    assert replayed["report"]["skipped_event_lines"] == 1


def test_cli_report_groups_offset_timestamps_by_utc_calendar_date(tmp_path):
    event_path = tmp_path / "events.jsonl"
    event_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-16T23:30:00-05:00",
                "event_type": "opportunity_scored",
                "run_id": "cli-offset",
                "decision": "approve",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    utc_day = _json_from_cli("report", "--events", str(event_path), "--date", "2026-05-17")
    local_day = _json_from_cli("report", "--events", str(event_path), "--date", "2026-05-16")

    assert utc_day["report"]["total_events"] == 1
    assert utc_day["report"]["event_type_counts"] == {"opportunity_scored": 1}
    assert local_day["report"]["total_events"] == 0


def test_cli_replay_report_groups_offset_timestamps_by_utc_calendar_date(tmp_path):
    event_path = tmp_path / "events.jsonl"
    event_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-05-16T23:30:00-05:00",
                "event_type": "risk_guard",
                "run_id": "cli-offset-replay",
                "decision": "block",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    utc_day = _json_from_cli("replay", "--events", str(event_path), "--date", "2026-05-17")
    local_day = _json_from_cli("replay", "--events", str(event_path), "--date", "2026-05-16")

    assert utc_day["report"]["total_events"] == 1
    assert utc_day["report"]["event_type_counts"] == {"risk_guard": 1}
    assert local_day["report"]["total_events"] == 0


def test_cli_report_rejects_missing_event_file(tmp_path):
    missing_path = tmp_path / "missing-events.jsonl"

    result = _run_cli("report", "--events", str(missing_path), "--date", "2026-05-16")

    assert result.returncode != 0
    assert "event file does not exist" in result.stderr
    assert str(missing_path) in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cli_replay_rejects_missing_event_file(tmp_path):
    missing_path = tmp_path / "missing-events.jsonl"

    result = _run_cli("replay", "--events", str(missing_path))

    assert result.returncode != 0
    assert "event file does not exist" in result.stderr
    assert str(missing_path) in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cli_report_rejects_invalid_date_without_traceback(tmp_path):
    event_path = tmp_path / "events.jsonl"
    _write_event_log(event_path)

    result = _run_cli("report", "--events", str(event_path), "--date", "not-a-date")

    assert result.returncode != 0
    assert "invalid UTC date" in result.stderr
    assert "not-a-date" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_cli_replay_rejects_invalid_date_without_traceback(tmp_path):
    event_path = tmp_path / "events.jsonl"
    _write_event_log(event_path)

    result = _run_cli("replay", "--events", str(event_path), "--date", "2026-02-30")

    assert result.returncode != 0
    assert "invalid UTC date" in result.stderr
    assert "2026-02-30" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
