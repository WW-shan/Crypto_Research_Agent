from __future__ import annotations

import json

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.scheduler import build_daily_schedule_plan


def test_build_daily_schedule_plan_returns_ordered_safe_dry_run_commands(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_path = tmp_path / "reports" / "daily.md"

    plan = build_daily_schedule_plan(
        db_path=db_path,
        memory_path=memory_path,
        report_out=report_path,
        current_capital_usd=300.0,
        run_id="daily-001",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        strategy_families=["funding_extremity_price_confirmation"],
    )

    dumped = plan.model_dump(mode="json")
    assert dumped["command"] == "schedule"
    assert dumped["execution_model"] == "external_operator_cron_calls_evidence_run"
    assert dumped["scheduler_executes_commands"] is False
    assert dumped["dry_run"] is True
    assert dumped["runs_subprocesses"] is False
    assert dumped["sleeps"] is False
    assert dumped["uses_real_capital"] is False
    assert dumped["live_order_routing"] is False
    assert dumped["network_allowed"] is True
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
            "name": "evidence-run",
            "argv": [
                "crypto-alpha-agent",
                "evidence-run",
                "--db",
                str(db_path),
                "--memory",
                str(memory_path),
                "--report-out",
                str(report_path),
                "--current-capital-usd",
                "300.0",
                "--allow-network",
                "--ccxt-exchange",
                "binance",
                "--symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
                "--timeframe",
                "1h",
                "--limit",
                "200",
                "--strategy-family",
                "funding_extremity_price_confirmation",
                "--run-id",
                "daily-001",
            ],
        },
    ]


def test_schedule_cli_dry_run_emits_json_plan_without_live_routing(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_path = tmp_path / "daily.md"

    exit_code = main(
        [
            "schedule",
            "--dry-run",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--report-out",
            str(report_path),
            "--allow-network",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--strategy-family",
            "funding_extremity_price_confirmation",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["command"] == "schedule"
    assert captured["execution_model"] == "external_operator_cron_calls_evidence_run"
    assert captured["scheduler_executes_commands"] is False
    assert captured["dry_run"] is True
    assert captured["runs_subprocesses"] is False
    assert captured["sleeps"] is False
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert [step["name"] for step in captured["planned_commands"]] == [
        "offline-ingest-check",
        "evidence-run",
    ]
    assert captured["planned_commands"][0]["argv"][:5] == [
        "crypto-alpha-agent",
        "ingest",
        "--offline-check",
        "--db",
        str(db_path),
    ]
    evidence_argv = captured["planned_commands"][1]["argv"]
    assert evidence_argv[:4] == ["crypto-alpha-agent", "evidence-run", "--db", str(db_path)]
    assert evidence_argv[evidence_argv.index("--memory") + 1] == str(memory_path)
    assert evidence_argv[evidence_argv.index("--report-out") + 1] == str(report_path)
    assert evidence_argv[evidence_argv.index("--symbol") + 1] == "BTC/USDT"
    assert evidence_argv[evidence_argv.index("--funding-symbol") + 1] == "BTC/USDT:USDT"
    assert evidence_argv[evidence_argv.index("--strategy-family") + 1] == "funding_extremity_price_confirmation"


def test_schedule_cli_dry_run_never_runs_subprocesses_or_sleeps(capsys, tmp_path, monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("schedule --dry-run must only emit a plan")

    monkeypatch.setattr("subprocess.run", fail_if_called)
    monkeypatch.setattr("time.sleep", fail_if_called)

    exit_code = main(
        [
            "schedule",
            "--dry-run",
            "--db",
            str(tmp_path / "research.sqlite"),
            "--memory",
            str(tmp_path / "memory.jsonl"),
            "--report-out",
            str(tmp_path / "daily.md"),
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["scheduler_executes_commands"] is False
    assert captured["runs_subprocesses"] is False
    assert captured["sleeps"] is False


def test_schedule_cli_rejects_non_dry_run_mode(capsys, tmp_path):
    with pytest.raises(SystemExit):
        main(
            [
                "schedule",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--memory",
                str(tmp_path / "memory.jsonl"),
                "--report-out",
                str(tmp_path / "daily.md"),
                "--symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
            ]
        )

    captured = capsys.readouterr()
    assert "the following arguments are required: --dry-run" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_schedule_cli_rejects_missing_funding_symbol(capsys, tmp_path):
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
                "--symbol",
                "BTC/USDT",
            ]
        )

    captured = capsys.readouterr()
    assert "the following arguments are required: --funding-symbol" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
    assert not db_path.exists()
    assert not report_path.exists()


def test_schedule_cli_defaults_memory_output_when_not_provided(capsys, tmp_path):
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
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    evidence_argv = captured["planned_commands"][1]["argv"]
    assert exit_code == 0
    assert captured["memory_path"] == str(report_path.with_suffix(".memory.jsonl"))
    assert evidence_argv[evidence_argv.index("--memory") + 1] == str(report_path.with_suffix(".memory.jsonl"))
    assert not db_path.exists()
    assert not report_path.exists()


def test_schedule_cli_allows_explicit_network_plan_without_live_capital_or_routing(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_path = tmp_path / "daily.md"

    exit_code = main(
        [
            "schedule",
            "--dry-run",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--report-out",
            str(report_path),
            "--allow-network",
            "--ccxt-exchange",
            "okx",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "4h",
            "--limit",
            "150",
            "--include-defillama",
            "--min-tvl-usd",
            "1000000",
        ]
    )

    captured = json.loads(capsys.readouterr().out)
    evidence_argv = captured["planned_commands"][1]["argv"]
    assert exit_code == 0
    assert captured["network_allowed"] is True
    assert captured["uses_real_capital"] is False
    assert captured["live_order_routing"] is False
    assert "--allow-network" in evidence_argv
    assert evidence_argv[evidence_argv.index("--ccxt-exchange") + 1] == "okx"
    assert evidence_argv[evidence_argv.index("--symbol") + 1] == "BTC/USDT"
    assert evidence_argv[evidence_argv.index("--funding-symbol") + 1] == "BTC/USDT:USDT"
    assert evidence_argv[evidence_argv.index("--timeframe") + 1] == "4h"
    assert evidence_argv[evidence_argv.index("--limit") + 1] == "150"
    assert "--include-defillama" in evidence_argv
    assert evidence_argv[evidence_argv.index("--min-tvl-usd") + 1] == "1000000.0"
