from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import pytest

from crypto_alpha_agent.config import LLMRole, LLMSettings, build_configured_llm_settings
from crypto_alpha_agent.security.secret_scan import (
    collect_sensitive_environment_values,
    scan_paths,
    scan_text,
)


def configured_llm_settings_or_fail(role: LLMRole = "research") -> LLMSettings:
    settings = build_configured_llm_settings(role=role, required=True)
    assert settings is not None
    return settings


def secret_values_for_settings(settings: LLMSettings) -> dict[str, str]:
    parsed = urlparse(settings.base_url)
    values = {
        "OPENAI_API_KEY": settings.api_key.get_secret_value(),
        "OPENAI_BASE_URL": settings.base_url,
    }
    if parsed.netloc:
        values["OPENAI_BASE_URL_NETLOC"] = parsed.netloc
    if parsed.hostname:
        values["OPENAI_BASE_URL_HOST"] = parsed.hostname
    return values


def assert_no_secret_leaks(
    *,
    text_surfaces: Mapping[str, object],
    path_surfaces: Iterable[str | Path],
    settings: LLMSettings,
) -> None:
    secret_values = {
        **collect_sensitive_environment_values(),
        **secret_values_for_settings(settings),
    }
    findings = []
    for surface, text in text_surfaces.items():
        findings.extend(scan_text(text, surface=surface, secret_values=secret_values))
    findings.extend(scan_paths(path_surfaces, secret_values=secret_values))
    public_findings = [finding.to_public_dict() for finding in findings]
    assert public_findings == [], (
        "secret scan findings: " + json.dumps(public_findings, sort_keys=True)
    )


def assert_no_raw_response_payload(payload: Any) -> None:
    raw_paths = _find_key_paths(payload, target_key="raw_response")
    assert raw_paths == []


def assert_research_only_payload(payload: Any) -> None:
    violations = []
    for path, value in _iter_key_values(payload):
        key = path[-1] if path else ""
        if key in {"uses_real_capital", "live_order_routing"} and value is not False:
            violations.append(".".join(path))
        if key == "action_mode" and value not in {"research_only", None}:
            violations.append(".".join(path))
    assert violations == []


def run_real_llm_cli_or_fail(
    command: Callable[[], int],
    *,
    capsys: pytest.CaptureFixture[str],
    settings: LLMSettings,
    attempts: int = 3,
) -> int:
    for attempt in range(1, attempts + 1):
        try:
            exit_code = command()
        except SystemExit as exc:
            captured = capsys.readouterr()
            assert_no_secret_leaks(
                text_surfaces={
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "system_exit": str(exc.code),
                },
                path_surfaces=[],
                settings=settings,
            )
            if attempt < attempts and _is_retryable_real_llm_failure(captured.err):
                continue
            pytest.fail(
                "real LLM integration environment failure: "
                f"CLI exited with status {exc.code}; provider output was redacted"
            )
        if exit_code == 0:
            return exit_code
        captured = capsys.readouterr()
        assert_no_secret_leaks(
            text_surfaces={
                "stdout": captured.out,
                "stderr": captured.err,
                "exit_code": str(exit_code),
            },
            path_surfaces=[],
            settings=settings,
        )
        retry_surface = "\n".join([captured.out, captured.err, str(exit_code)])
        if attempt < attempts and _is_retryable_real_llm_failure(retry_surface):
            continue
        pytest.fail(
            "real LLM integration environment failure: "
            f"CLI returned status {exit_code}; provider output was redacted"
        )
    raise AssertionError("unreachable real LLM integration retry state")


def call_real_llm_or_fail(
    call: Callable[[], str],
    *,
    capsys: pytest.CaptureFixture[str],
    settings: LLMSettings,
    attempts: int = 3,
) -> str:
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - provider boundary must stay redacted.
            captured = capsys.readouterr()
            message = f"{type(exc).__name__}: {exc}"
            assert_no_secret_leaks(
                text_surfaces={
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "exception": message,
                },
                path_surfaces=[],
                settings=settings,
            )
            if attempt < attempts and _is_retryable_real_llm_failure(message):
                continue
            pytest.fail(
                "real LLM integration environment failure: "
                f"provider call raised {type(exc).__name__}; output was redacted"
            )
    raise AssertionError("unreachable real LLM integration retry state")


def _find_key_paths(value: Any, *, target_key: str, path: tuple[str, ...] = ()) -> list[str]:
    if isinstance(value, Mapping):
        found: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            current_path = (*path, key_text)
            if key_text == target_key:
                found.append(".".join(current_path))
            found.extend(_find_key_paths(item, target_key=target_key, path=current_path))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(value):
            found.extend(_find_key_paths(item, target_key=target_key, path=(*path, str(index))))
        return found
    return []


def _iter_key_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            current_path = (*path, str(key))
            yield current_path, item
            yield from _iter_key_values(item, current_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_key_values(item, (*path, str(index)))


def _is_retryable_real_llm_failure(stderr: str) -> bool:
    lowered = stderr.lower()
    if "llm provider request failed" not in lowered:
        return False
    if "timeout" in lowered or "time-out" in lowered or "temporarily unavailable" in lowered:
        return True
    return bool(re.search(r"status\s+5\d\d", lowered))
