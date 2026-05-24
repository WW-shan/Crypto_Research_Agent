from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm.responses import OpenAIResponsesAdapter
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
    with pytest.raises(LLMRuntimeError, match="invalid_json") as exc_info:
        parse_structured_llm_json("not json", LLMHealthCheckResult)

    assert exc_info.value.__cause__ is None


def test_parse_structured_llm_json_rejects_markdown_fence() -> None:
    raw_response = (
        '```json\n{"status":"ok","schema_name":"LLMHealthCheckResult",'
        '"capabilities":["json_schema","research_only"],'
        '"uses_real_capital":false,"live_order_routing":false}\n```'
    )

    with pytest.raises(LLMRuntimeError, match="invalid_json"):
        parse_structured_llm_json(raw_response, LLMHealthCheckResult)


def test_parse_structured_llm_json_rejects_non_strict_output_model() -> None:
    class LooseModel(BaseModel):
        value: int

    with pytest.raises(LLMRuntimeError, match="unsafe_output_schema"):
        parse_structured_llm_json('{"value":"1","extra":"ignored"}', LooseModel)


def test_parse_structured_llm_json_rejects_nested_non_strict_output_model() -> None:
    class LooseChild(BaseModel):
        value: int

    class StrictParent(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

        child: LooseChild

    with pytest.raises(LLMRuntimeError, match="unsafe_output_schema"):
        parse_structured_llm_json(
            '{"child":{"value":"1","extra":"ignored"}}',
            StrictParent,
        )


def test_llm_health_check_result_schema_requires_runtime_capabilities() -> None:
    raw_response = json.dumps(
        {
            "status": "ok",
            "schema_name": "LLMHealthCheckResult",
            "capabilities": ["json_schema", "tool_use"],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )

    with pytest.raises(LLMRuntimeError, match="schema_validation_failed"):
        parse_structured_llm_json(raw_response, LLMHealthCheckResult)


def test_parse_structured_llm_json_schema_error_does_not_echo_raw_input() -> None:
    secret_model_text = "raw-secret-model-output"
    raw_response = json.dumps(
        {
            "status": secret_model_text,
            "schema_name": "LLMHealthCheckResult",
            "capabilities": ["json_schema", "research_only"],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )

    with pytest.raises(LLMRuntimeError, match="schema_validation_failed") as exc_info:
        parse_structured_llm_json(raw_response, LLMHealthCheckResult)

    message = str(exc_info.value)
    assert secret_model_text not in message
    assert "input_value" not in message


def test_llm_health_check_result_requires_capital_and_routing_flags() -> None:
    raw_response = json.dumps(
        {
            "status": "ok",
            "schema_name": "LLMHealthCheckResult",
            "capabilities": ["json_schema", "research_only"],
        }
    )

    with pytest.raises(LLMRuntimeError, match="schema_validation_failed"):
        parse_structured_llm_json(raw_response, LLMHealthCheckResult)


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
    runtime = RealLLMRuntime._for_test_double(llm=llm, role="research")

    result = runtime.health_check(command="research-loop")

    assert result.status == "ok"
    assert llm.calls
    assert runtime.metadata()["llm_provider"] == "real"
    assert runtime.metadata()["used_fake_llm"] is True
    assert runtime.metadata()["llm_provider_verified"] is False
    assert runtime.metadata()["llm_model"] == "test-real-model"


def test_real_runtime_accepts_configured_adapter_metadata_without_calling_provider() -> None:
    llm = OpenAIResponsesAdapter(_settings())
    runtime = RealLLMRuntime(llm=llm, provider="real", role="research")

    assert runtime.metadata()["llm_provider"] == "real"
    assert runtime.metadata()["used_fake_llm"] is False
    assert runtime.metadata()["llm_provider_verified"] is True
    assert runtime.metadata()["llm_model"] == "test-real-model"


def test_real_runtime_health_check_rejects_missing_capabilities_at_schema_boundary() -> None:
    llm = CapturingLLM(
        json.dumps(
            {
                "status": "ok",
                "schema_name": "LLMHealthCheckResult",
                "capabilities": ["json_schema", "tool_use"],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )
    )
    runtime = RealLLMRuntime._for_test_double(llm=llm, role="research")

    with pytest.raises(LLMRuntimeError, match="schema_validation_failed"):
        runtime.health_check(command="research-loop")


def test_real_runtime_rejects_fake_provider() -> None:
    llm = CapturingLLM("{}")

    with pytest.raises(LLMRuntimeError, match="fake_llm_not_allowed"):
        RealLLMRuntime(llm=llm, provider="fake", role="research")


def test_real_runtime_rejects_unverified_callable_by_default() -> None:
    llm = CapturingLLM("{}")

    with pytest.raises(LLMRuntimeError, match="unverified_llm_provider"):
        RealLLMRuntime(llm=llm, provider="real", role="research")


def test_real_runtime_rejects_adapter_with_injected_session() -> None:
    llm = OpenAIResponsesAdapter(_settings(), session=object())

    with pytest.raises(LLMRuntimeError, match="unverified_llm_provider"):
        RealLLMRuntime(llm=llm, provider="real", role="research")


def test_build_required_real_llm_runtime_fails_when_env_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    with pytest.raises(LLMRuntimeError, match="llm_configuration_missing"):
        build_required_real_llm_runtime(env_file=env_path, role="research", env={})


def _settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://llm.example/v1",
        api_key="secret-test-key",
        model="test-real-model",
        role="research",
    )
