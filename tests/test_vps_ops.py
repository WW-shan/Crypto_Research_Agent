from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_vps_ops_files_exist() -> None:
    required_files = [
        "Dockerfile",
        ".dockerignore",
        "docker-compose.yml",
        "ops/daily-evidence-run.sh",
        "ops/weekly-review.sh",
        "ops/monthly-owner-review.sh",
        "ops/backup-var.sh",
        "ops/install-systemd.sh",
        "ops/systemd/crypto-alpha-daily.service",
        "ops/systemd/crypto-alpha-daily.timer",
        "ops/systemd/crypto-alpha-weekly.service",
        "ops/systemd/crypto-alpha-weekly.timer",
        "ops/systemd/crypto-alpha-monthly.service",
        "ops/systemd/crypto-alpha-monthly.timer",
        "ops/systemd/crypto-alpha-backup.service",
        "ops/systemd/crypto-alpha-backup.timer",
        "docs/vps-deployment.md",
    ]

    missing = [path for path in required_files if not (ROOT / path).is_file()]

    assert missing == []


def test_ops_scripts_are_syntax_valid() -> None:
    scripts = sorted((ROOT / "ops").glob("*.sh"))

    assert scripts

    for script in scripts:
        subprocess.run(["bash", "-n", str(script)], check=True, cwd=ROOT)


@pytest.mark.parametrize(
    ("script", "extra_env"),
    [
        ("ops/daily-evidence-run.sh", {}),
        ("ops/weekly-review.sh", {}),
        (
            "ops/monthly-owner-review.sh",
            {"CRYPTO_ALPHA_AGENT_REVIEW_FAMILY": "funding_extremity_price_confirmation"},
        ),
        ("ops/backup-var.sh", {}),
        ("ops/install-systemd.sh", {}),
    ],
)
def test_ops_scripts_support_portable_dry_run(script: str, extra_env: dict[str, str]) -> None:
    env = {
        "CRYPTO_ALPHA_AGENT_DRY_RUN": "1",
        "CRYPTO_ALPHA_AGENT_SYSTEMD_DIR": str(ROOT / "var" / "systemd-test"),
        **extra_env,
    }

    result = subprocess.run(
        ["bash", script],
        check=False,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    assert "DRY RUN:" in result.stdout


def test_docker_runtime_keeps_secrets_out_of_image_and_mounts_state() -> None:
    dockerignore = read_text(".dockerignore")
    dockerfile = read_text("Dockerfile")
    compose = read_text("docker-compose.yml")

    for ignored_path in [".env", "var", ".venv", ".worktrees", ".git"]:
        assert ignored_path in dockerignore

    for expected in [
        "python:3.12-slim",
        "uv sync --extra dev --frozen",
        "USER app",
        "crypto-alpha-agent",
    ]:
        assert expected in dockerfile

    for expected in [
        "crypto-alpha-agent:",
        "env_file:",
        ".env",
        "./var:/app/var",
        "extra_hosts:",
        "host.docker.internal:host-gateway",
    ]:
        assert expected in compose
    assert "docker.sock" not in compose


def test_daily_wrapper_runs_evidence_run_with_artifact_contract() -> None:
    script = read_text("ops/daily-evidence-run.sh")

    for expected in [
        "set -euo pipefail",
        "docker compose",
        "CRYPTO_ALPHA_AGENT_DOCKER_PROXY",
        "HTTP_PROXY",
        "run",
        "--rm",
        "crypto-alpha-agent",
        "evidence-run",
        "--latest-report-out",
        "--latest-json-out",
        "--latest-manifest-out",
        "--manifest-out",
        "--failed-marker-out",
        "--lock-path",
        "stdout.log",
        "stderr.log",
        "CRYPTO_ALPHA_AGENT_DRY_RUN",
    ]:
        assert expected in script


def test_daily_wrapper_can_pass_host_proxy_to_container() -> None:
    result = subprocess.run(
        ["bash", "ops/daily-evidence-run.sh"],
        check=False,
        cwd=ROOT,
        env={
            "CRYPTO_ALPHA_AGENT_DRY_RUN": "1",
            "CRYPTO_ALPHA_AGENT_DOCKER_PROXY": "http://host.docker.internal:10808",
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    assert "DRY RUN:" in result.stdout
    assert "-e HTTP_PROXY=http://host.docker.internal:10808" in result.stdout
    assert "-e HTTPS_PROXY=http://host.docker.internal:10808" in result.stdout
    assert "-e ALL_PROXY=http://host.docker.internal:10808" in result.stdout


def test_weekly_wrapper_runs_governance_memo_and_iteration_cycle() -> None:
    script = read_text("ops/weekly-review.sh")

    for expected in [
        "set -euo pipefail",
        "docker compose",
        "run",
        "--rm",
        "crypto-alpha-agent",
        "governance-report",
        "ai-research-memo",
        "iteration-cycle",
        "--json-out",
        "latest.md",
        "latest.json",
        "CRYPTO_ALPHA_AGENT_DRY_RUN",
    ]:
        assert expected in script


def test_monthly_and_backup_wrappers_are_safe() -> None:
    monthly = read_text("ops/monthly-owner-review.sh")
    backup = read_text("ops/backup-var.sh")

    for expected in [
        "set -euo pipefail",
        "CRYPTO_ALPHA_AGENT_REVIEW_FAMILY",
        "rollout-review",
        "--artifact-out",
        "--evidence-package-out",
        "CRYPTO_ALPHA_AGENT_DRY_RUN",
    ]:
        assert expected in monthly

    for expected in [
        "set -euo pipefail",
        "tar -czf",
        "research.sqlite",
        "evidence.jsonl",
        "run-manifests",
        "reports",
        "CRYPTO_ALPHA_AGENT_DRY_RUN",
    ]:
        assert expected in backup


def test_systemd_units_call_ops_scripts_without_secrets() -> None:
    services = sorted((ROOT / "ops/systemd").glob("*.service"))
    timers = sorted((ROOT / "ops/systemd").glob("*.timer"))

    assert services
    assert timers

    service_text_by_name = {service.name: service.read_text(encoding="utf-8") for service in services}
    timer_text_by_name = {timer.name: timer.read_text(encoding="utf-8") for timer in timers}

    expected_scripts = {
        "crypto-alpha-daily.service": "ops/daily-evidence-run.sh",
        "crypto-alpha-weekly.service": "ops/weekly-review.sh",
        "crypto-alpha-monthly.service": "ops/monthly-owner-review.sh",
        "crypto-alpha-backup.service": "ops/backup-var.sh",
    }

    for name, text in service_text_by_name.items():
        assert "OPENAI_API_KEY" not in text
        assert "DUNE_API_KEY" not in text
        assert "WorkingDirectory=/opt/crypto-alpha-agent" in text
        assert expected_scripts[name] in text

    for text in timer_text_by_name.values():
        assert "OnCalendar=" in text
        assert "Persistent=true" in text


def test_vps_deployment_doc_documents_outputs_and_boundaries() -> None:
    doc = read_text("docs/vps-deployment.md")

    for expected in [
        "Docker Compose",
        "systemd",
        "crypto-alpha-daily.timer",
        "var/research.sqlite",
        "var/memory/evidence.jsonl",
        "var/reports/daily/latest.md",
        "var/reports/iteration/latest.json",
        "var/run-manifests/latest.json",
        "failed marker",
        "no live order routing",
        "auto_executes_changes=false",
        ".env stays outside git",
    ]:
        assert expected in doc
