from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm.runtime import (
    LLMHealthCheckResult,
    LLMRuntimeError,
    RealLLMRuntime,
    build_required_real_llm_runtime,
    parse_structured_llm_json,
)


class CapturingLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []
        self.settings = LLMSettings(
            base_url="https://llm.example/v1",
            api_key="secret-test-key",
            model="test-real-model",
            role="research",
        )

    def __call__(self, task):
        self.calls.append(task)
        return self.response


def test_parse_structured_llm_json_rejects_non_json() -> None:
    with pytest.raises(LLMRuntimeError, match="invalid_json"):
        parse_structured_llm_json("not json", LLMHealthCheckResult)


def test_real_runtime_health_check_records_real_provider_metadata() -> None:
    llm = CapturingLLM(
        json.dumps(
            {
                "status": "ok",
                "schema_name": "LLMHealthCheckResult",
                "capabilities": ["json_schema", "research_only"],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )
    )
    runtime = RealLLMRuntime(llm=llm, provider="real", role="research")

    result = runtime.health_check(command="research-loop")

    assert result.status == "ok"
    assert llm.calls
    assert runtime.metadata()["llm_provider"] == "real"
    assert runtime.metadata()["used_fake_llm"] is False
    assert runtime.metadata()["llm_model"] == "test-real-model"


def test_real_runtime_rejects_fake_provider() -> None:
    llm = CapturingLLM("{}")

    with pytest.raises(LLMRuntimeError, match="fake_llm_not_allowed"):
        RealLLMRuntime(llm=llm, provider="fake", role="research")


def test_build_required_real_llm_runtime_fails_when_env_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    with pytest.raises(LLMRuntimeError, match="llm_configuration_missing"):
        build_required_real_llm_runtime(env_file=env_path, role="research")
