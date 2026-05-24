from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.agents.llm_contracts import HypothesisProposal, ResearchTask
from crypto_alpha_agent.pipeline.experiment_planner import (
    ExperimentPlannerInput,
    ExperimentPlannerMemoryContext,
    ExperimentPlannerTask,
)
from crypto_alpha_agent.config import LLMSettings, build_configured_llm_settings
from crypto_alpha_agent.llm import (
    LLMHealthCheckTask,
    LLMProviderError,
    OpenAIResponsesAdapter,
    build_configured_llm,
)
from crypto_alpha_agent.llm.redaction import redact_text
from llm_integration_policy import (
    assert_no_secret_leaks,
    call_real_llm_or_fail,
    configured_llm_settings_or_skip,
)


def _write_env(path: Path, *, base_url: str = "https://provider.example/root") -> None:
    path.write_text(
        "\n".join(
            [
                f"OPENAI_BASE_URL={base_url}",
                "OPENAI_API_KEY=fake-api-key-value",
                "OPENAI_API_TYPE=responses",
                "OPENAI_MODEL=gpt-default",
                "OPENAI_RESEARCH_MODEL=gpt-research",
                "OPENAI_CODER_MODEL=gpt-coder",
                "OPENAI_FAST_MODEL=gpt-fast",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_llm_settings_loads_local_env_and_routes_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_API_TYPE",
        "OPENAI_MODEL",
        "OPENAI_RESEARCH_MODEL",
        "OPENAI_CODER_MODEL",
        "OPENAI_FAST_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    env_path = tmp_path / ".env"
    _write_env(env_path)

    research = LLMSettings.from_env(env_file=env_path, role="research", required=True)
    planning = LLMSettings.from_env(env_file=env_path, role="planning", required=True)
    coder = LLMSettings.from_env(env_file=env_path, role="coder", required=True)
    validator = LLMSettings.from_env(env_file=env_path, role="validator_design", required=True)
    summary = LLMSettings.from_env(env_file=env_path, role="summary", required=True)
    report = LLMSettings.from_env(env_file=env_path, role="report", required=True)
    default = LLMSettings.from_env(env_file=env_path, role="default", required=True)

    assert research.model == "gpt-research"
    assert planning.model == "gpt-research"
    assert coder.model == "gpt-coder"
    assert validator.model == "gpt-coder"
    assert summary.model == "gpt-fast"
    assert report.model == "gpt-fast"
    assert default.model == "gpt-research"
    assert research.base_url == "https://provider.example/root"
    assert research.api_type == "responses"


def test_llm_settings_environment_overrides_local_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path)
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "gpt-shell-research")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-shell-api-key")

    settings = LLMSettings.from_env(env_file=env_path, role="research", required=True)

    assert settings.model == "gpt-shell-research"
    assert settings.api_key.get_secret_value() == "fake-shell-api-key"


def test_missing_required_llm_config_fails_closed_without_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in tuple(os.environ):
        if key.startswith("OPENAI_"):
            monkeypatch.delenv(key, raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_MODEL=gpt-default\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        LLMSettings.from_env(env_file=env_path, role="research", required=True)

    message = str(exc_info.value)
    assert "OPENAI_BASE_URL" in message
    assert "OPENAI_API_KEY" in message
    assert "gpt-default" not in message
    assert "fake-api-key-value" not in message


def test_optional_llm_config_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in tuple(os.environ):
        if key.startswith("OPENAI_"):
            monkeypatch.delenv(key, raising=False)

    assert (
        build_configured_llm_settings(
            env_file=tmp_path / ".env", role="research", required=False
        )
        is None
    )


def test_llm_settings_safe_summary_and_redaction_hide_sensitive_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_API_TYPE",
        "OPENAI_MODEL",
        "OPENAI_RESEARCH_MODEL",
        "OPENAI_CODER_MODEL",
        "OPENAI_FAST_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    env_path = tmp_path / ".env"
    _write_env(env_path)

    settings = LLMSettings.from_env(env_file=env_path, role="research", required=True)
    summary = settings.safe_summary()
    summary_text = repr(summary)

    assert summary["base_url_configured"] is True
    assert summary["api_key_configured"] is True
    assert summary["model"] == "gpt-research"
    assert "fake-api-key-value" not in summary_text
    assert "https://provider.example/root" not in summary_text
    assert "Authorization" not in summary_text

    redacted = redact_text(
        "Authorization: Bearer fake-api-key-value at https://provider.example/root",
        secrets=[settings.api_key.get_secret_value(), settings.base_url],
    )
    assert "fake-api-key-value" not in redacted
    assert "https://provider.example/root" not in redacted
    assert "Bearer" not in redacted
    assert "Authorization" not in redacted
    assert "<redacted>" in redacted


def test_redaction_hides_repr_style_authorization_headers() -> None:
    redacted = redact_text(
        "{'Authorization': 'Bearer fake-api-key-value', 'content-type': 'application/json'}",
        secrets=["fake-api-key-value"],
    )

    assert "Authorization" not in redacted
    assert "Bearer" not in redacted
    assert "fake-api-key-value" not in redacted


class _DummyTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    objective: str


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict[str, object] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.content = json.dumps(self._payload).encode("utf-8")
        self.headers = {"x-provider-secret": "secret-header-value"}

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response


def _settings(*, base_url: str = "https://provider.example") -> LLMSettings:
    return LLMSettings(
        base_url=base_url,
        api_key="fake-api-key-value",
        model="gpt-test",
        role="research",
    )


def test_responses_adapter_posts_to_normalized_v1_responses_url_and_extracts_output_text() -> None:
    response = _FakeResponse(payload={"output_text": '{"proposal_id":"p1"}'})
    session = _FakeSession(response)
    adapter = OpenAIResponsesAdapter(_settings(), session=session)

    result = adapter(_DummyTask(task_id="adapter-task-1", objective="Return JSON"))

    assert result == '{"proposal_id":"p1"}'
    assert session.calls[0]["url"] == "https://provider.example/v1/responses"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer fake-api-key-value"
    assert session.calls[0]["json"]["model"] == "gpt-test"
    assert "adapter-task-1" in str(session.calls[0]["json"]["input"])
    assert "fake-api-key-value" not in str(session.calls[0]["json"]["input"])
    assert "https://provider.example" not in str(session.calls[0]["json"]["input"])


def test_responses_adapter_does_not_duplicate_v1_suffix() -> None:
    session = _FakeSession(_FakeResponse(payload={"output_text": "{}"}))
    adapter = OpenAIResponsesAdapter(
        _settings(base_url="https://provider.example/v1"),
        session=session,
    )

    adapter(_DummyTask(task_id="adapter-task-1", objective="Return JSON"))

    assert session.calls[0]["url"] == "https://provider.example/v1/responses"


def test_responses_adapter_extracts_nested_output_items_without_stripping_json_fences() -> None:
    response = _FakeResponse(
        payload={
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '```json\n{"proposal_id":"p2"}\n```'}
                    ],
                }
            ]
        }
    )
    adapter = OpenAIResponsesAdapter(_settings(), session=_FakeSession(response))

    assert adapter(_DummyTask(task_id="adapter-task-2", objective="Return JSON")) == (
        '```json\n{"proposal_id":"p2"}\n```'
    )


def test_responses_adapter_includes_hypothesis_schema_hint_for_research_task() -> None:
    session = _FakeSession(_FakeResponse(payload={"output_text": "{}"}))
    adapter = OpenAIResponsesAdapter(_settings(), session=session)

    adapter(
        ResearchTask(
            task_id="research-schema-hint",
            agent_role="hypothesis_generator",
            objective="Generate one hypothesis.",
            context={"run_id": "schema-hint-run"},
            evidence=["funding validation evidence exists"],
            allowed_tools=["local_report", "charter_guard"],
            network_policy="offline",
            current_capital_usd=300.0,
        )
    )

    prompt = str(session.calls[0]["json"]["input"])
    for field_name in [
        "HypothesisProposal",
        "proposal_id",
        "thesis",
        "hypothesis",
        "assumptions",
        "evidence",
        "disconfirmation",
        "data_needed",
        "capital_required_usd",
        "speed_dependency",
        "rpc_dependency",
        "action_mode",
    ]:
        assert field_name in prompt
    assert "markdown" in prompt.lower()


def test_responses_adapter_includes_experiment_schema_hint_for_planner_task() -> None:
    session = _FakeSession(_FakeResponse(payload={"output_text": "{}"}))
    adapter = OpenAIResponsesAdapter(_settings(), session=session)
    task = ExperimentPlannerTask(
        task_id="planner-schema-hint",
        objective="Plan bounded experiments.",
        planner_input=ExperimentPlannerInput(
            db_path="research.sqlite",
            memory_path="memory.jsonl",
            strategy_family="funding_extremity_price_confirmation",
            max_proposals=1,
            current_capital_usd=300.0,
            offline_only=False,
        ),
        validation_evidence_summaries=[],
        paper_evidence_packages=[],
        degraded_strategy_families=[],
        blocked_parameter_sets={},
        memory_context=ExperimentPlannerMemoryContext(
            degraded_strategy_families=[],
            blocked_parameter_sets={},
            blocked_parameter_set_count=0,
        ),
        current_capital_usd=300.0,
    )

    adapter(task)

    prompt = str(session.calls[0]["json"]["input"])
    for field_name in [
        "ExperimentProposal",
        "proposals",
        "strategy_family",
        "parameter_changes",
        "why_it_might_improve_edge",
        "disconfirmation_tests",
        "stop_conditions",
        "uses_real_capital",
        "live_order_routing",
    ]:
        assert field_name in prompt
    assert "false" in prompt


def test_responses_adapter_includes_health_check_schema_hint_for_runtime_task() -> None:
    adapter = OpenAIResponsesAdapter(_settings())

    prompt = adapter._render_input(LLMHealthCheckTask(command="research-loop"))

    for expected_text in [
        "LLMHealthCheckResult",
        "uses_real_capital=false",
        "live_order_routing=false",
        "json_schema",
        "research_only",
    ]:
        assert expected_text in prompt


def test_responses_adapter_provider_errors_are_redacted() -> None:
    response = _FakeResponse(
        status_code=401,
        payload={
            "error": {
                "message": "bad key fake-api-key-value at https://provider.example"
            }
        },
        text=(
            "bad key fake-api-key-value at https://provider.example "
            "Authorization: Bearer fake-api-key-value "
            "HTTPSConnectionPool(host='provider.example', port=443)"
        ),
    )
    adapter = OpenAIResponsesAdapter(_settings(), session=_FakeSession(response))

    with pytest.raises(LLMProviderError) as exc_info:
        adapter(_DummyTask(task_id="adapter-task-3", objective="Return JSON"))

    message = str(exc_info.value)
    assert "fake-api-key-value" not in message
    assert "https://provider.example" not in message
    assert "provider.example" not in message
    assert "Authorization" not in message
    assert "secret-header-value" not in message
    assert "status 401" in message


def test_build_configured_llm_returns_adapter_when_settings_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_API_TYPE",
        "OPENAI_MODEL",
        "OPENAI_RESEARCH_MODEL",
        "OPENAI_CODER_MODEL",
        "OPENAI_FAST_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    env_path = tmp_path / ".env"
    _write_env(env_path)

    adapter = build_configured_llm(env_file=env_path, role="summary", required=True)

    assert isinstance(adapter, OpenAIResponsesAdapter)
    assert adapter.settings.model == "gpt-fast"


@pytest.mark.integration
@pytest.mark.llm_integration
def test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = configured_llm_settings_or_skip("research")

    llm = build_configured_llm(role="research", required=True)
    assert llm is not None
    safe_proposal = {
        "proposal_id": "real-llm-smoke-funding-001",
        "thesis": "Funding extremes can identify slow research candidates.",
        "hypothesis": (
            "When public funding prints are extreme and price confirmation is present, "
            "a small paper-only research candidate may deserve validation."
        ),
        "assumptions": [
            "Only public historical data is used.",
            "The candidate remains paper-only and research-only.",
        ],
        "evidence": [
            "The project tracks funding extremity and price confirmation as a registered family."
        ],
        "disconfirmation": [
            "Reject the idea if after-cost expectancy is not positive.",
            "Reject the idea if walk-forward evidence is unstable.",
        ],
        "data_needed": [
            "funding rate history",
            "OHLCV history",
            "paper outcome ledger",
        ],
        "capital_required_usd": 25.0,
        "speed_dependency": "none",
        "rpc_dependency": "none",
        "action_mode": "research_only",
    }
    task = ResearchTask(
        task_id="real-llm-smoke",
        agent_role="hypothesis_generator",
        objective="Return exactly this JSON object and no other text: "
        + json.dumps(safe_proposal, sort_keys=True),
        context={
            "strategy_family": "funding_extremity_price_confirmation",
            "capital_profile_usd": 300,
        },
        evidence=["This is a smoke test of schema-constrained research output."],
        allowed_tools=["local_report"],
        network_policy="offline",
        current_capital_usd=300.0,
        requires_human_approval=False,
    )

    raw_response = call_real_llm_or_fail(lambda: llm(task), capsys=capsys, settings=settings)
    try:
        proposal = HypothesisProposal.model_validate_json(raw_response)
    except Exception as exc:  # noqa: BLE001 - avoid printing raw provider output.
        pytest.fail(f"real LLM smoke returned invalid proposal: {type(exc).__name__}")
    captured = capsys.readouterr()
    leak_surface = captured.out + captured.err + raw_response

    assert proposal.action_mode == "research_only"
    assert proposal.capital_required_usd <= 25
    assert proposal.speed_dependency == "none"
    assert proposal.rpc_dependency == "none"
    assert_no_secret_leaks(
        text_surfaces={"real_llm_smoke": leak_surface},
        path_surfaces=[],
        settings=settings,
    )
