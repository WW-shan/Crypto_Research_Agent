from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.llm import LLMProviderError
from crypto_alpha_agent.llm.runtime import LLMRuntimeError


class PassingHealth:
    def model_dump(self, *, mode: str = "json") -> dict[str, Any]:
        assert mode == "json"
        return {
            "status": "ok",
            "schema_name": "LLMHealthCheckResult",
            "capabilities": ["json_schema", "research_only"],
            "uses_real_capital": False,
            "live_order_routing": False,
        }


class PassingRuntime:
    def __init__(self) -> None:
        self.health_commands: list[str] = []

    def health_check(self, *, command: str) -> PassingHealth:
        self.health_commands.append(command)
        return PassingHealth()

    def metadata(self) -> dict[str, Any]:
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": "research",
            "llm_model": "test-real-model",
            "llm_health_schema": "LLMHealthCheckResult",
        }


class ProviderFailingRuntime:
    def health_check(self, *, command: str):
        raise LLMProviderError("provider unavailable")


class ProviderFailingStructuredRuntime(PassingRuntime):
    def structured_call(self, task: Any, output_model: type[Any]) -> Any:
        raise LLMProviderError("provider unavailable during judgement")


def test_help_bypasses_llm_gate(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "crypto-alpha-agent" in captured.out


def test_version_bypasses_llm_gate(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "crypto-alpha-agent 0.1.0" in captured.out


def test_llm_health_check_command_runs_required_real_llm(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    runtime = PassingRuntime()
    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": runtime,
        raising=False,
    )

    exit_code = main(["llm-health-check"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "llm-health-check"
    assert payload["llm_required"] is True
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["health"]["schema_name"] == "LLMHealthCheckResult"
    assert runtime.health_commands == ["llm-health-check"]


def test_product_command_fails_closed_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def fail_runtime(*, role: str = "research"):
        raise LLMRuntimeError("llm_configuration_missing", "missing test config")

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        fail_runtime,
        raising=False,
    )
    db_path = tmp_path / "research.sqlite"

    exit_code = main(["ingest", "--offline-check", "--db", str(db_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["command"] == "ingest"
    assert payload["reason_code"] == "llm_configuration_missing"
    assert payload["llm_required"] is True
    assert payload["side_effects_started"] is False
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert not db_path.exists()


def test_product_command_fails_closed_when_llm_connection_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": ProviderFailingRuntime(),
    )
    db_path = tmp_path / "research.sqlite"

    exit_code = main(["ingest", "--offline-check", "--db", str(db_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["command"] == "ingest"
    assert payload["reason_code"] == "llm_provider_unavailable"
    assert payload["side_effects_started"] is False
    assert "provider unavailable" in payload["failure"]
    assert not db_path.exists()


def test_rollout_review_provider_failure_uses_parser_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="research": ProviderFailingStructuredRuntime(),
    )
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "rollout-review",
                "--db",
                str(db_path),
                "--strategy-family",
                "funding_extremity_price_confirmation",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "provider unavailable during judgement" in captured.err


def test_offline_only_argument_is_removed(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "plan-experiments",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--memory",
                str(tmp_path / "memory.jsonl"),
                "--offline-only",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "unrecognized arguments: --offline-only" in captured.err
