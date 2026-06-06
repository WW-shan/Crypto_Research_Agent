from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from crypto_alpha_agent.autonomy.codex_runner import (
    CodexRunner,
    CodexUnavailableError,
    ensure_success,
)
from crypto_alpha_agent.autonomy.models import CodexExecResult


def test_health_check_constructs_codex_exec_command(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    runner = CodexRunner(run_command=fake_run)

    result = runner.health_check(workdir=tmp_path)

    assert result.exit_code == 0
    assert calls[0]["command"] == [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--cd",
        str(tmp_path),
        "--sandbox",
        "read-only",
        "--json",
        "-",
    ]
    assert calls[0]["cwd"] == tmp_path
    assert calls[0]["timeout"] == 120
    assert calls[0]["capture_output"] is True
    assert calls[0]["text"] is True
    assert "health" in str(calls[0]["input"]).lower()


def test_health_check_raises_when_codex_exits_nonzero(tmp_path: Path) -> None:
    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 7, stdout="", stderr="not installed")

    runner = CodexRunner(run_command=fake_run)

    with pytest.raises(CodexUnavailableError) as exc_info:
        runner.health_check(workdir=tmp_path)

    assert "not installed" in str(exc_info.value)


def test_exec_prompt_passes_stdin_and_returns_redacted_output(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="authorization: bearer stdout-secret\ncreated",
            stderr="Bearer stderr-secret",
        )

    runner = CodexRunner(run_command=fake_run, timeout_seconds=999)

    result = runner.exec_prompt(
        workdir=tmp_path,
        prompt="Implement the task",
        sandbox="workspace-write",
        timeout_seconds=42,
    )

    assert calls[0]["input"] == "Implement the task"
    assert calls[0]["timeout"] == 42
    assert result.command == calls[0]["command"]
    assert result.stdout == "<redacted>\ncreated"
    assert result.stderr == "<redacted>"


def test_exec_prompt_resolves_relative_workdir_before_passing_to_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    runner = CodexRunner(run_command=fake_run)
    runner.exec_prompt(workdir=Path("repo"), prompt="hello")

    assert calls[0]["command"] == [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--cd",
        str(repo),
        "--sandbox",
        "workspace-write",
        "--json",
        "-",
    ]
    assert calls[0]["cwd"] == repo


def test_env_scrubber_removes_trading_wallet_llm_secrets_but_keeps_codex_home_and_proxy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BINANCE_API_SECRET", "binance-secret")
    monkeypatch.setenv("WALLET_PRIVATE_KEY", "wallet-secret")
    monkeypatch.setenv("EXCHANGE_API_KEY", "exchange-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("CODEX_TOKEN", "codex-token")
    monkeypatch.setenv("CODEX_HOME", "/tmp/codex-home")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example")

    captured_env: dict[str, str] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_env.update(kwargs["env"])  # type: ignore[arg-type]
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    runner = CodexRunner(run_command=fake_run)
    runner.exec_prompt(workdir=tmp_path, prompt="hello")

    assert "BINANCE_API_SECRET" not in captured_env
    assert "WALLET_PRIVATE_KEY" not in captured_env
    assert "EXCHANGE_API_KEY" not in captured_env
    assert "OPENAI_API_KEY" not in captured_env
    assert "ANTHROPIC_API_KEY" not in captured_env
    assert "CODEX_TOKEN" not in captured_env
    assert captured_env["CODEX_HOME"] == "/tmp/codex-home"
    assert captured_env["OPENAI_BASE_URL"] == "https://llm.example"
    assert captured_env["HTTPS_PROXY"] == "http://proxy.example"


def test_scrubbed_llm_and_codex_secret_values_are_redacted_from_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key-secret")
    monkeypatch.setenv("OPENAI_SECRET_KEY", "openai-secret-key")
    monkeypatch.setenv("CODEX_PRIVATE_KEY", "codex-private-key")
    captured_env: dict[str, str] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_env.update(kwargs["env"])  # type: ignore[arg-type]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="stdout openai-key-secret openai-secret-key",
            stderr="stderr codex-private-key",
        )

    runner = CodexRunner(run_command=fake_run)
    result = runner.exec_prompt(workdir=tmp_path, prompt="hello")

    assert "OPENAI_API_KEY" not in captured_env
    assert "OPENAI_SECRET_KEY" not in captured_env
    assert "CODEX_PRIVATE_KEY" not in captured_env
    assert "openai-key-secret" not in result.stdout
    assert "openai-secret-key" not in result.stdout
    assert "codex-private-key" not in result.stderr
    assert result.stdout == "stdout <redacted> <redacted>"
    assert result.stderr == "stderr <redacted>"


def test_authenticated_proxy_values_are_redacted_from_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxy_url = "http://proxy-user:proxy-password@proxy.example:8080"
    monkeypatch.setenv("HTTPS_PROXY", proxy_url)

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"using {proxy_url} user proxy-user",
            stderr=f"failed via {proxy_url} password proxy-password",
        )

    runner = CodexRunner(run_command=fake_run)
    result = runner.exec_prompt(workdir=tmp_path, prompt="hello")

    assert proxy_url not in result.stdout
    assert proxy_url not in result.stderr
    assert "proxy-user" not in result.stdout
    assert "proxy-password" not in result.stderr
    assert result.stdout == "using <redacted> user <redacted>"
    assert result.stderr == "failed via <redacted> password <redacted>"


def test_ensure_success_raises_for_nonzero_codex_result() -> None:
    result = CodexExecResult(
        command=["codex", "exec"],
        exit_code=2,
        stdout="",
        stderr="builder failed",
    )

    with pytest.raises(CodexUnavailableError, match="builder failed"):
        ensure_success(result)
