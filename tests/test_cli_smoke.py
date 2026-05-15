from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "crypto_alpha_agent.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _json_from_cli(*args: str) -> dict[str, object]:
    result = _run_cli(*args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


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
        assert payload["live_api_calls"] is False
        assert payload["uses_real_capital"] is False


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


def test_cli_replay_counts_events_and_can_regenerate_report(tmp_path):
    event_path = tmp_path / "events.jsonl"
    _write_event_log(event_path)

    counts = _json_from_cli("replay", "--events", str(event_path))

    assert counts["command"] == "replay"
    assert counts["event_path"] == str(event_path)
    assert counts["loaded_events"] == 3
    assert counts["skipped_event_lines"] == 1
    assert counts["event_type_counts"] == {"opportunity_scored": 1, "risk_guard": 2}

    replayed = _json_from_cli("replay", "--events", str(event_path), "--date", "2026-05-16")

    assert replayed["loaded_events"] == 3
    assert replayed["report"]["total_events"] == 2
    assert replayed["report"]["skipped_event_lines"] == 1
