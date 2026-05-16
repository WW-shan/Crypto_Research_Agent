from __future__ import annotations

import json

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.scheduler import build_daily_schedule_plan


def test_build_daily_schedule_plan_returns_ordered_safe_dry_run_commands(tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "reports" / "daily.md"

    plan = build_daily_schedule_plan(
        db_path=db_path,
        report_out=report_path,
        current_capital_usd=300.0,
        run_id="daily-001",
    )

    dumped = plan.model_dump(mode="json")
    assert dumped["command"] == "schedule"
    assert dumped["dry_run"] is True
    assert dumped["runs_subprocesses"] is False
    assert dumped["sleeps"] is False
    assert dumped["uses_real_capital"] is False
    assert dumped["live_order_routing"] is False
    assert dumped["network_allowed"] is False
    assert dumped["planned_commands"] == [
        {
            "name": "offline-ingest-check",
            "argv": [
                "crypto-alpha-agent",
                "ingest",
                "--offline-check",
                "--db",
                str(db_path),
                "--current-capital-usd",
                "300.0",
            ],
        },
        {
            "name": "research-loop",
            "argv": [
                "crypto-alpha-agent",
                "research-loop",
                "--db",
                str(db_path),
                "--current-capital-usd",
                "300.0",
                "--include-validation",
                "--report-out",
                str(report_path),
                "--run-id",
                "daily-001",
            ],
        },
    ]


def test_schedule_cli_dry_run_emits_json_plan_without_live_routing(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "daily.md"

    exit_code = main(["schedule", "--dry-run", "--db", str(db_path), "--report-out", str(report_path)])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["command"] == "schedule"
    assert captured["dry_run"] is True
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert [step["name"] for step in captured["planned_commands"]] == [
        "offline-ingest-check",
        "research-loop",
    ]
    assert captured["planned_commands"][0]["argv"][:5] == [
        "crypto-alpha-agent",
        "ingest",
        "--offline-check",
        "--db",
        str(db_path),
    ]


def test_schedule_cli_rejects_network_ingestion_intent_without_gate(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "daily.md"

    with pytest.raises(SystemExit):
        main(
            [
                "schedule",
                "--dry-run",
                "--db",
                str(db_path),
                "--report-out",
                str(report_path),
                "--source",
                "binance-public",
                "--symbol",
                "BTCUSDT",
                "--year",
                "2026",
                "--month",
                "5",
            ]
        )

    captured = capsys.readouterr()
    assert "--allow-network is required" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not db_path.exists()
    assert not report_path.exists()


def test_schedule_cli_allows_explicit_network_plan_without_live_capital_or_routing(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "daily.md"

    exit_code = main(
        [
            "schedule",
            "--dry-run",
            "--db",
            str(db_path),
            "--report-out",
            str(report_path),
            "--allow-network",
            "--source",
            "binance-public",
            "--symbol",
            "BTCUSDT",
            "--year",
            "2026",
            "--month",
            "5",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    research_argv = captured["planned_commands"][1]["argv"]
    assert exit_code == 0
    assert captured["network_allowed"] is True
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert "--allow-network" in research_argv
    assert research_argv[research_argv.index("--source") + 1] == "binance-public"
    assert research_argv[research_argv.index("--symbol") + 1] == "BTCUSDT"
    assert research_argv[research_argv.index("--timeframe") + 1] == "1h"
    assert research_argv[research_argv.index("--year") + 1] == "2026"
    assert research_argv[research_argv.index("--month") + 1] == "5"
