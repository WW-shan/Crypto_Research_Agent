# Phase 1 Real LLM Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 real LLM adapter so the project can read local OpenAI-compatible Responses configuration, route roles to the owner's configured models, call the configured endpoint safely, and prove the integration without leaking secrets.

**Architecture:** Keep Phase 1 as an adapter/config/test/docs slice only. Add strict local `LLMSettings`, a secret redaction helper, and an `OpenAIResponsesAdapter` callable compatible with existing injected LLM seams (`Callable[[ResearchTask], str]` and planner LLM callables). Do not wire the adapter into `research-loop`, `plan-experiments`, `evidence-run`, reports, or autonomous graph execution until Phase 2.

**Tech Stack:** Python 3.12, Pydantic, `requests`, pytest, ruff, existing strict LLM contracts in `crypto_alpha_agent.agents.llm_contracts`, local `.env`/environment variables.

---

## Evidence And Scope

External evidence collected before planning:

- Smart Search deep plan: `/tmp/smart-search-evidence/2026-05-23-phase1/01-deep-plan.json`.
- Broad source discovery: `/tmp/smart-search-evidence/2026-05-23-phase1/02-broad-search.json`.
- Official OpenAI Responses docs fetched from `https://developers.openai.com/api/reference/resources/responses/methods/create/` into `/tmp/smart-search-evidence/2026-05-23-phase1/08-openai-responses-create-developers.md`.
- Official OpenAI API overview fetched from `https://developers.openai.com/api/reference/overview/` into `/tmp/smart-search-evidence/2026-05-23-phase1/09-openai-api-overview.md`.
- Official OpenAI migration guide fetched from `https://developers.openai.com/api/docs/guides/migrate-to-responses` into `/tmp/smart-search-evidence/2026-05-23-phase1/06-openai-responses-vs-chat.md`.
- Pydantic `SecretStr` docs fetched from `https://docs.pydantic.dev/latest/api/types/#pydantic.types.SecretStr` into `/tmp/smart-search-evidence/2026-05-23-phase1/10-pydantic-secretstr.md`.
- Exa official-doc search was attempted and recorded as unavailable because `EXA_API_KEY` is not configured; Smart Search `search` and `fetch` covered the official docs evidence.

Local feasibility verified before planning:

- Worktree started clean on `main...origin/main`.
- `.env` exists locally and is ignored; only variable presence was checked, never printed.
- A raw metadata-only prototype request through `uv run --extra dev python` reached the configured Responses-compatible endpoint with status `200`, JSON body, and `output` items. The prototype did not print base URL, key, headers, or model response text.
- Existing seams already accept injected callables and should remain intact:
  - `src/crypto_alpha_agent/agents/llm_researcher.py` calls an injected `LLMCallable` and parses strict `HypothesisProposal` JSON.
  - `src/crypto_alpha_agent/pipeline/experiment_planner.py` accepts an injected `PlannerLLM` and stores raw-response metadata only.
  - `src/crypto_alpha_agent/orchestrator.py` strips raw LLM text and stores length/hash metadata.

Phase boundary:

- Implement settings, adapter, redaction, factories, deterministic tests, one real smoke integration test, runbook update, roadmap/state/report update.
- Do not change CLI `plan-experiments`, `research-loop`, `evidence-run`, report summaries, memory persistence semantics, or any live/trading path.
- Do not add API-key CLI flags.
- Do not persist raw provider headers or raw LLM responses in docs, memory, reports, or test artifacts.

## File Structure

Create:

- `src/crypto_alpha_agent/llm/__init__.py` — public exports for Phase 1 LLM settings, factory, adapter, and error types.
- `src/crypto_alpha_agent/llm/redaction.py` — small redaction utility for configured secrets, provider URLs, auth headers, and provider error strings.
- `src/crypto_alpha_agent/llm/responses.py` — OpenAI-compatible Responses HTTP adapter and response text extraction.
- `tests/test_llm_configured_client.py` — TDD tests for settings, role routing, redaction, adapter request/extraction behavior, provider error safety, and real smoke test.

Modify:

- `src/crypto_alpha_agent/config.py` — add `LLMRole`, `LLMSettings`, `.env` loading, model routing, fail-closed construction, and factory helpers while preserving existing `RuntimeConfig` behavior.
- `docs/runbook.md` — replace “optional until adapter is implemented” with Phase 1 operator usage and smoke-test guidance without values.
- `docs/roadmap.md` — mark Immediate Phase 1 complete only after verification passes.
- `docs/goals/project-completion-state.md` — append Phase 1 state, evidence, verification, and next phase.
- `docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md` — complete phase report.

Do not modify unless a test proves the need:

- `src/crypto_alpha_agent/agents/llm_researcher.py`
- `src/crypto_alpha_agent/pipeline/experiment_planner.py`
- `src/crypto_alpha_agent/orchestrator.py`
- `src/crypto_alpha_agent/cli.py`

## Task 1: Settings And Redaction

**Files:**
- Modify: `src/crypto_alpha_agent/config.py`
- Create: `src/crypto_alpha_agent/llm/__init__.py`
- Create: `src/crypto_alpha_agent/llm/redaction.py`
- Test: `tests/test_llm_configured_client.py`

- [ ] **Step 1: Write failing tests for local `.env` loading, role routing, fail-closed behavior, and redaction**

Add these tests to `tests/test_llm_configured_client.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from crypto_alpha_agent.config import LLMSettings, build_configured_llm_settings
from crypto_alpha_agent.llm.redaction import redact_text


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


def test_llm_settings_loads_local_env_and_routes_models(tmp_path, monkeypatch):
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


def test_llm_settings_environment_overrides_local_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    _write_env(env_path)
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "gpt-shell-research")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-shell-api-key")

    settings = LLMSettings.from_env(env_file=env_path, role="research", required=True)

    assert settings.model == "gpt-shell-research"
    assert settings.api_key.get_secret_value() == "fake-shell-api-key"


def test_missing_required_llm_config_fails_closed_without_values(tmp_path, monkeypatch):
    for key in os.environ:
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
    assert "sk-" not in message


def test_optional_llm_config_returns_none_when_missing(tmp_path, monkeypatch):
    for key in os.environ:
        if key.startswith("OPENAI_"):
            monkeypatch.delenv(key, raising=False)

    assert build_configured_llm_settings(env_file=tmp_path / ".env", role="research", required=False) is None


def test_llm_settings_safe_summary_and_redaction_hide_sensitive_values(tmp_path, monkeypatch):
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
    assert "<redacted>" in redacted
```

- [ ] **Step 2: Run the settings tests and verify they fail because `LLMSettings` does not exist**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_llm_settings_loads_local_env_and_routes_models -q
```

Expected: FAIL with an import error or missing `LLMSettings`.

- [ ] **Step 3: Implement minimal `LLMSettings`, `.env` parser, settings factory, and redaction helper**

Add to `src/crypto_alpha_agent/config.py` below `RuntimeConfig`:

```python
from pathlib import Path
from pydantic import SecretStr

LLMRole = Literal["default", "research", "planning", "coder", "validator_design", "summary", "report", "fast"]


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    base_url: str = Field(min_length=1)
    api_key: SecretStr
    model: str = Field(min_length=1)
    role: LLMRole = "research"
    api_type: Literal["responses"] = "responses"
    timeout_seconds: float = Field(default=180.0, gt=0)

    @classmethod
    def from_env(
        cls,
        *,
        env_file: str | Path | None = Path(".env"),
        role: LLMRole = "research",
        required: bool = True,
        env: dict[str, str] | None = None,
    ) -> "LLMSettings | None":
        values = _load_llm_env(env_file=env_file, env=env)
        base_url = values.get("OPENAI_BASE_URL", "").strip()
        api_key = values.get("OPENAI_API_KEY", "").strip()
        api_type = values.get("OPENAI_API_TYPE", "responses").strip() or "responses"
        model = _model_for_role(values, role)
        missing = [name for name, value in (("OPENAI_BASE_URL", base_url), ("OPENAI_API_KEY", api_key), ("OPENAI_MODEL or role model", model)) if not value]
        if api_type != "responses":
            missing.append("OPENAI_API_TYPE=responses")
        if missing:
            if required:
                raise ValueError("Real LLM is required but local configuration is incomplete: " + ", ".join(missing))
            return None
        return cls(base_url=base_url, api_key=SecretStr(api_key), model=model, role=role, api_type="responses")

    def safe_summary(self) -> dict[str, object]:
        return {
            "api_type": self.api_type,
            "role": self.role,
            "model": self.model,
            "base_url_configured": bool(self.base_url),
            "api_key_configured": bool(self.api_key.get_secret_value()),
            "timeout_seconds": self.timeout_seconds,
        }
```

Add helper functions in the same file:

```python
def build_configured_llm_settings(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    required: bool = False,
    env: dict[str, str] | None = None,
) -> LLMSettings | None:
    return LLMSettings.from_env(env_file=env_file, role=role, required=required, env=env)


def _model_for_role(values: dict[str, str], role: LLMRole) -> str:
    fallback = values.get("OPENAI_MODEL", "").strip()
    if role in {"default", "research", "planning"}:
        return values.get("OPENAI_RESEARCH_MODEL", "").strip() or fallback
    if role in {"coder", "validator_design"}:
        return values.get("OPENAI_CODER_MODEL", "").strip() or fallback
    if role in {"summary", "report", "fast"}:
        return values.get("OPENAI_FAST_MODEL", "").strip() or fallback
    return fallback


def _load_llm_env(*, env_file: str | Path | None, env: dict[str, str] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file is not None:
        path = Path(env_file)
        if path.exists():
            values.update(_parse_env_file(path))
    source_env = env if env is not None else dict(os.environ)
    for key, value in source_env.items():
        if key.startswith("OPENAI_") and value is not None:
            values[key] = value
    return values


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        parsed[key] = _unquote_env_value(value.strip())
    return parsed


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
```

Create `src/crypto_alpha_agent/llm/redaction.py`:

```python
from __future__ import annotations

import re
from collections.abc import Iterable

_AUTH_HEADER_PATTERN = re.compile(r"authorization\s*:\s*bearer\s+[^\s,;]+", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"bearer\s+[^\s,;]+", re.IGNORECASE)


def redact_text(text: object, *, secrets: Iterable[str] = ()) -> str:
    value = str(text)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "<redacted>")
    value = _AUTH_HEADER_PATTERN.sub("<redacted>", value)
    value = _BEARER_PATTERN.sub("Bearer <redacted>", value)
    return value
```

Create `src/crypto_alpha_agent/llm/__init__.py` with exports added in later tasks after the adapter exists.

- [ ] **Step 4: Run the settings tests and verify they pass**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_llm_settings_loads_local_env_and_routes_models tests/test_llm_configured_client.py::test_llm_settings_environment_overrides_local_env tests/test_llm_configured_client.py::test_missing_required_llm_config_fails_closed_without_values tests/test_llm_configured_client.py::test_optional_llm_config_returns_none_when_missing tests/test_llm_configured_client.py::test_llm_settings_safe_summary_and_redaction_hide_sensitive_values -q
```

Expected: all selected tests pass.

## Task 2: Responses Adapter

**Files:**
- Create: `src/crypto_alpha_agent/llm/responses.py`
- Modify: `src/crypto_alpha_agent/llm/__init__.py`
- Test: `tests/test_llm_configured_client.py`

- [ ] **Step 1: Add failing fake-session tests for request shape, URL normalization, output extraction, markdown-fence cleanup, and redacted provider errors**

Append to `tests/test_llm_configured_client.py`:

```python
import json

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm import LLMProviderError, OpenAIResponsesAdapter


class _DummyTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    objective: str


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload: dict[str, object] | None = None, text: str = "") -> None:
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
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> _FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response


def _settings(*, base_url: str = "https://provider.example") -> LLMSettings:
    return LLMSettings(base_url=base_url, api_key="fake-api-key-value", model="gpt-test", role="research")


def test_responses_adapter_posts_to_normalized_v1_responses_url_and_extracts_output_text():
    response = _FakeResponse(payload={"output_text": "{\"proposal_id\":\"p1\"}"})
    session = _FakeSession(response)
    adapter = OpenAIResponsesAdapter(_settings(), session=session)

    result = adapter(_DummyTask(task_id="task-1", objective="Return JSON"))

    assert result == '{"proposal_id":"p1"}'
    assert session.calls[0]["url"] == "https://provider.example/v1/responses"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer fake-api-key-value"
    assert session.calls[0]["json"]["model"] == "gpt-test"
    assert "task-1" in session.calls[0]["json"]["input"]
    assert "fake-api-key-value" not in session.calls[0]["json"]["input"]
    assert "https://provider.example" not in session.calls[0]["json"]["input"]


def test_responses_adapter_does_not_duplicate_v1_suffix():
    session = _FakeSession(_FakeResponse(payload={"output_text": "{}"}))
    adapter = OpenAIResponsesAdapter(_settings(base_url="https://provider.example/v1"), session=session)

    adapter(_DummyTask(task_id="task-1", objective="Return JSON"))

    assert session.calls[0]["url"] == "https://provider.example/v1/responses"


def test_responses_adapter_extracts_nested_output_items_and_strips_json_fences():
    response = _FakeResponse(
        payload={
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "```json\n{\"proposal_id\":\"p2\"}\n```"}
                    ],
                }
            ]
        }
    )
    adapter = OpenAIResponsesAdapter(_settings(), session=_FakeSession(response))

    assert adapter(_DummyTask(task_id="task-2", objective="Return JSON")) == '{"proposal_id":"p2"}'


def test_responses_adapter_provider_errors_are_redacted():
    response = _FakeResponse(
        status_code=401,
        payload={"error": {"message": "bad key fake-api-key-value at https://provider.example"}},
        text=(
            "bad key fake-api-key-value at https://provider.example "
            "Authorization: Bearer fake-api-key-value "
            "HTTPSConnectionPool(host='provider.example', port=443)"
        ),
    )
    adapter = OpenAIResponsesAdapter(_settings(), session=_FakeSession(response))

    with pytest.raises(LLMProviderError) as exc_info:
        adapter(_DummyTask(task_id="task-3", objective="Return JSON"))

    message = str(exc_info.value)
    assert "fake-api-key-value" not in message
    assert "https://provider.example" not in message
    assert "provider.example" not in message
    assert "Authorization" not in message
    assert "secret-header-value" not in message
    assert "status 401" in message
```

- [ ] **Step 2: Run the adapter tests and verify they fail because the adapter does not exist**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_responses_adapter_posts_to_normalized_v1_responses_url_and_extracts_output_text -q
```

Expected: FAIL with missing `OpenAIResponsesAdapter` or `LLMProviderError`.

- [ ] **Step 3: Implement the Responses adapter**

Create `src/crypto_alpha_agent/llm/responses.py`:

```python
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import requests

from crypto_alpha_agent.config import LLMSettings
from crypto_alpha_agent.llm.redaction import redact_text


class LLMProviderError(RuntimeError):
    """Provider request failed without exposing provider credentials."""


class LLMConfigurationError(ValueError):
    """Local LLM configuration is missing or unsupported."""


class OpenAIResponsesAdapter:
    def __init__(self, settings: LLMSettings, *, session: Any | None = None) -> None:
        self.settings = settings
        self.session = session if session is not None else requests.Session()

    def __call__(self, task: Any) -> str:
        payload = {
            "model": self.settings.model,
            "input": self._render_input(task),
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        try:
            response = self.session.post(
                self._responses_url(),
                headers=headers,
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - redacted provider boundary.
            raise LLMProviderError(self._redact(f"LLM provider request failed: {type(exc).__name__}: {exc}")) from None
        if response.status_code >= 400:
            raise LLMProviderError(self._redact(f"LLM provider request failed with status {response.status_code}: {getattr(response, 'text', '')}"))
        try:
            response_payload = response.json()
        except Exception as exc:  # noqa: BLE001 - provider JSON parse boundary.
            raise LLMProviderError(self._redact(f"LLM provider returned invalid JSON: {type(exc).__name__}")) from None
        return _strip_json_fence(_extract_response_text(response_payload))

    def _responses_url(self) -> str:
        base_url = self.settings.base_url.rstrip("/")
        if base_url.endswith("/responses"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/responses"
        return f"{base_url}/v1/responses"

    def _render_input(self, task: Any) -> str:
        if hasattr(task, "model_dump"):
            task_payload = task.model_dump(mode="json")
        elif isinstance(task, dict):
            task_payload = task
        else:
            task_payload = {"task": str(task)}
        return (
            "You are a research-only crypto alpha assistant. Return only valid JSON that matches "
            "the caller's schema. Do not request live trading, wallet keys, private RPC, MEV, "
            "large capital, or order routing.\n\n"
            + json.dumps(task_payload, sort_keys=True, default=str)
        )

    def _redact(self, value: object) -> str:
        return redact_text(
            value,
            secrets=[
                self.settings.api_key.get_secret_value(),
                *self._base_url_redaction_values(),
            ],
        )

    def _base_url_redaction_values(self) -> list[str]:
        parsed = urlparse(self.settings.base_url)
        values = [self.settings.base_url]
        if parsed.netloc:
            values.append(parsed.netloc)
        if parsed.hostname:
            values.append(parsed.hostname)
        return values
```

Add module helpers in `responses.py`:

```python
def _extract_response_text(payload: Any) -> str:
    if isinstance(payload, dict):
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
            text = _extract_output_item_text(item)
            if text:
                return text
    raise LLMProviderError("LLM provider response did not contain output text")


def _extract_output_item_text(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    content = item.get("content")
    if isinstance(content, list):
        for content_item in content:
            if isinstance(content_item, dict):
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _strip_json_fence(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return value
```

Update `src/crypto_alpha_agent/llm/__init__.py`:

```python
from crypto_alpha_agent.config import LLMRole, LLMSettings, build_configured_llm_settings
from crypto_alpha_agent.llm.responses import LLMConfigurationError, LLMProviderError, OpenAIResponsesAdapter

__all__ = [
    "LLMConfigurationError",
    "LLMProviderError",
    "LLMRole",
    "LLMSettings",
    "OpenAIResponsesAdapter",
    "build_configured_llm_settings",
]
```

- [ ] **Step 4: Run the adapter tests and verify they pass**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_responses_adapter_posts_to_normalized_v1_responses_url_and_extracts_output_text tests/test_llm_configured_client.py::test_responses_adapter_does_not_duplicate_v1_suffix tests/test_llm_configured_client.py::test_responses_adapter_extracts_nested_output_items_and_strips_json_fences tests/test_llm_configured_client.py::test_responses_adapter_provider_errors_are_redacted -q
```

Expected: all selected tests pass.

## Task 3: Configured Factory And Real Smoke Test

**Files:**
- Modify: `src/crypto_alpha_agent/config.py`
- Modify: `src/crypto_alpha_agent/llm/__init__.py`
- Test: `tests/test_llm_configured_client.py`

- [ ] **Step 1: Add failing tests for configured adapter factory and real integration smoke**

Append to `tests/test_llm_configured_client.py`:

```python
from crypto_alpha_agent.agents.llm_contracts import HypothesisProposal, ResearchTask
from crypto_alpha_agent.llm import build_configured_llm


def test_build_configured_llm_returns_adapter_when_settings_exist(tmp_path, monkeypatch):
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


def _real_llm_credentials_present() -> bool:
    settings = build_configured_llm_settings(role="research", required=False)
    return settings is not None


@pytest.mark.integration
def test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks(capsys):
    if os.environ.get("CI") and os.environ.get("CRYPTO_ALPHA_AGENT_RUN_REAL_LLM_TESTS") != "1":
        pytest.skip("real LLM smoke is disabled in CI unless explicitly opted in")
    if not _real_llm_credentials_present():
        pytest.skip("real LLM credentials are not configured")

    llm = build_configured_llm(role="research", required=True)
    assert llm is not None
    task = ResearchTask(
        task_id="real-llm-smoke",
        agent_role="hypothesis_generator",
        objective=(
            "Return one JSON object matching HypothesisProposal exactly. Use research_only action_mode, "
            "capital_required_usd 25, speed_dependency none, rpc_dependency none."
        ),
        context={"strategy_family": "funding_extremity_price_confirmation", "capital_profile_usd": 300},
        evidence=["This is a smoke test of schema-constrained research output."],
        allowed_tools=["local_report"],
        network_policy="offline",
        current_capital_usd=300.0,
        requires_human_approval=False,
    )

    raw_response = llm(task)
    proposal = HypothesisProposal.model_validate_json(raw_response)
    captured = capsys.readouterr()
    settings = llm.settings
    leak_surface = captured.out + captured.err + raw_response

    assert proposal.action_mode == "research_only"
    assert proposal.capital_required_usd <= 25
    assert proposal.speed_dependency == "none"
    assert proposal.rpc_dependency == "none"
    assert settings.api_key.get_secret_value() not in leak_surface
    assert settings.base_url not in leak_surface
```

- [ ] **Step 2: Run the factory test and verify it fails because `build_configured_llm` does not exist**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_build_configured_llm_returns_adapter_when_settings_exist -q
```

Expected: FAIL with missing `build_configured_llm`.

- [ ] **Step 3: Implement `build_configured_llm` factory**

Add to `src/crypto_alpha_agent/config.py`:

```python
def build_configured_llm(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    required: bool = False,
    env: dict[str, str] | None = None,
):
    settings = build_configured_llm_settings(env_file=env_file, role=role, required=required, env=env)
    if settings is None:
        return None
    from crypto_alpha_agent.llm.responses import OpenAIResponsesAdapter

    return OpenAIResponsesAdapter(settings)
```

Update `src/crypto_alpha_agent/llm/__init__.py` to export `build_configured_llm`:

```python
from crypto_alpha_agent.config import LLMRole, LLMSettings, build_configured_llm, build_configured_llm_settings

__all__ = [
    "LLMConfigurationError",
    "LLMProviderError",
    "LLMRole",
    "LLMSettings",
    "OpenAIResponsesAdapter",
    "build_configured_llm",
    "build_configured_llm_settings",
]
```

- [ ] **Step 4: Run deterministic factory tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_build_configured_llm_returns_adapter_when_settings_exist -q
```

Expected: PASS.

- [ ] **Step 5: Run real LLM integration smoke test with local credentials**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks -q
```

Expected locally: PASS when `.env` has valid credentials; SKIP only if credentials are absent. In this repository run, credentials are configured, so a skip is not acceptable unless the provider is unavailable. Provider failures must be reported as integration environment failures, not product success.

- [ ] **Step 6: Add pytest integration marker if pytest warns about an unknown marker**

If pytest emits `PytestUnknownMarkWarning`, add this to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: tests that call configured external services",
]
```

Run the smoke test again after adding the marker.

## Task 4: Documentation And Phase State

**Files:**
- Modify: `docs/runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/goals/project-completion-state.md`
- Create: `docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md`

- [ ] **Step 1: Update `docs/runbook.md` with Phase 1 operator guidance**

Replace the sentence “Local LLM credentials are optional operator configuration until the real LLM adapter is implemented.” with:

```markdown
Local LLM credentials are optional operator configuration for offline-only runs,
but the Phase 1 real LLM adapter uses them by default whenever a local operator
or integration test explicitly requests a configured LLM. Keep them in `.env` or
the shell environment only, and never commit or paste the values into docs,
reports, memory, logs, screenshots, or tests.
```

Add this paragraph after the LLM environment variable block:

```markdown
To smoke-test the configured LLM adapter without exposing secrets, run:

```bash
uv run --extra dev pytest \
  tests/test_llm_configured_client.py::test_real_configured_llm_smoke_returns_valid_research_proposal_without_secret_leaks \
  -q
```

The smoke test prints no API key, provider URL, provider headers, or raw HTTP
metadata. It validates only that the configured Responses-compatible endpoint can
return schema-valid research-only JSON. If this test fails because the external
provider is down or rejects the configured model, treat it as an integration
environment failure and keep deterministic fake LLM tests for adversarial cases.
```

- [ ] **Step 2: Update `docs/roadmap.md` Immediate Phase 1 status**

In the Immediate Phase 1 section, add a completion note after the completion standard:

```markdown
Phase 1 completion record: implemented by
`docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md`.
The adapter remains research-only and is not wired into Phase 2 research-loop or
evidence-run commands yet.
```

- [ ] **Step 3: Update `docs/goals/project-completion-state.md`**

Append a new Phase 1 section that records:

- Phase name and date.
- Smart Search evidence paths.
- Raw metadata-only prototype result: configured endpoint returned HTTP `200`, JSON, and `output` items; no values printed.
- Implemented files.
- Real LLM smoke test result.
- Deterministic test result.
- Ruff/full test result.
- Secret-safety result.
- Next phase: Immediate Phase 2, connect LLM to research loop.

Use this wording for the next-phase boundary:

```markdown
Immediate Phase 2 may use `build_configured_llm(...)` to inject the real adapter
into existing research/planning seams, but Phase 1 deliberately did not change
`research-loop`, `plan-experiments`, `evidence-run`, report summaries, memory
persistence, or any execution/live path.
```

- [ ] **Step 4: Write the Phase 1 completion report**

Create `docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md` with these sections:

```markdown
# Phase 1 Real LLM Adapter Completion Report

## Scope

## External Evidence

## Local Feasibility And Prototype

## Implementation Summary

## Verification

## Secret Safety

## Review Passes

## Boundaries Preserved

## Remaining Work For Phase 2
```

Fill every section with concrete results from this Phase. Do not include API key, base URL, provider headers, raw provider response, or local proxy values.

- [ ] **Step 5: Run documentation contract tests**

Run:

```bash
uv run --extra dev pytest tests/test_documentation_contract.py tests/test_cli_smoke.py::test_repo_ignores_local_macos_and_cache_artifacts -q
```

Expected: PASS.

## Task 5: Review, Verification, Secret Safety, Commit, Push

**Files:**
- Review all changed files.

- [ ] **Step 1: Run Review Pass 1 (spec compliance)**

Use a subagent reviewer or local checklist to verify these Phase 1 requirements:

- `LLMSettings` reads `.env` and environment variables.
- Environment variables override `.env` values.
- Role routing matches roadmap.
- Adapter calls an OpenAI-compatible Responses endpoint based on `OPENAI_BASE_URL`.
- Real smoke test calls configured endpoint and parses a valid `HypothesisProposal`.
- Missing credentials fail closed when required.
- No Phase 2 wiring was added.
- No live trading, wallet, order routing, MEV, speed edge, premium RPC, or private infrastructure path was introduced.

Fix all Critical and Important findings, then re-run the relevant tests.

- [ ] **Step 2: Run Review Pass 2 (code quality and secret safety)**

Use a second subagent reviewer or local checklist to verify:

- Exceptions redact API key, base URL, Authorization header, and provider error body values.
- `safe_summary()` cannot reveal key or base URL.
- Tests do not print secrets.
- Docs list variable names only.
- Adapter has no raw provider header logging or persistence.
- The `.env` parser is conservative and does not become a broad config subsystem.

Fix all Critical and Important findings, then re-run the relevant tests.

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run --extra dev pytest tests/test_llm_configured_client.py tests/test_llm_researcher_adapter.py tests/test_llm_contracts.py tests/test_llm_graph_routing.py tests/test_ai_experiment_planner.py tests/test_documentation_contract.py -q
```

Expected: PASS. The real smoke test should run locally when credentials are configured and be marked integration.

- [ ] **Step 4: Run full tests and ruff**

Run:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check .
```

Expected: PASS and ruff clean.

- [ ] **Step 5: Run diff and secret-safety checks**

Run:

```bash
git diff --check
git status --short --branch --untracked-files=all
git diff -- src tests docs pyproject.toml
```

Then run this staged-file secret scan after staging:

```bash
git add src/crypto_alpha_agent/config.py \
  src/crypto_alpha_agent/llm/__init__.py \
  src/crypto_alpha_agent/llm/redaction.py \
  src/crypto_alpha_agent/llm/responses.py \
  tests/test_llm_configured_client.py \
  docs/runbook.md \
  docs/roadmap.md \
  docs/goals/project-completion-state.md \
  docs/goals/phase-reports/2026-05-23-phase-1-real-llm-adapter-completion-report.md \
  docs/superpowers/plans/2026-05-23-phase-1-real-llm-adapter.md \
  pyproject.toml

git diff --cached --name-only

git diff --cached | rg -n "(?i)\bsk-[A-Za-z0-9]{16,}\b|Authorization: Bearer (?!fake-api-key-value)[A-Za-z0-9._-]{24,}|configured provider host|local proxy endpoint|real API key" && exit 1 || true
```

Expected: no secret scan match. If the regex matches an intentional fake value in tests, rewrite the fake value so it cannot be confused with the owner's real key or provider URL.

- [ ] **Step 6: Commit and push Phase 1**

Run:

```bash
git commit -m "feat: add real llm adapter"
git push
```

Expected: commit succeeds and push reports the branch is up to date with the remote after upload.

- [ ] **Step 7: Update the active plan after push**

Mark Phase 1 complete in the session plan and keep the overall goal active. Do not start Immediate Phase 2 in the same round.
