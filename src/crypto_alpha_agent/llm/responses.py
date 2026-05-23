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
            raise LLMProviderError(
                self._redact(
                    f"LLM provider request failed: {type(exc).__name__}: {exc}"
                )
            ) from None
        if response.status_code >= 400:
            raise LLMProviderError(
                self._redact(
                    f"LLM provider request failed with status {response.status_code}: "
                    f"{getattr(response, 'text', '')}"
                )
            )
        try:
            response_payload = response.json()
        except Exception as exc:  # noqa: BLE001 - provider JSON parse boundary.
            raise LLMProviderError(
                self._redact(
                    f"LLM provider returned invalid JSON: {type(exc).__name__}"
                )
            ) from None
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
            "You are a research-only crypto alpha assistant. Return only valid JSON "
            "that matches the caller's requested schema. Do not request prohibited "
            "execution capabilities, secret material, privileged infrastructure, "
            "or capital beyond the supplied profile.\n\n"
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


def _extract_response_text(payload: Any) -> str:
    if isinstance(payload, dict):
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
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
