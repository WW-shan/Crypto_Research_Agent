from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from crypto_alpha_agent.autonomy.models import CodexExecResult
from crypto_alpha_agent.llm.redaction import redact_text


class CodexUnavailableError(RuntimeError):
    """Raised when the Codex CLI cannot complete a health check."""


class CodexRunner:
    def __init__(
        self,
        *,
        run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: int = 1800,
    ) -> None:
        self._run_command = run_command
        self._timeout_seconds = timeout_seconds

    def health_check(self, *, workdir: Path) -> CodexExecResult:
        result = self.exec_prompt(
            workdir=workdir,
            prompt="Codex health check: reply with OK.",
            sandbox="read-only",
            timeout_seconds=120,
        )
        if result.exit_code != 0:
            detail = result.stderr or result.stdout or f"exit code {result.exit_code}"
            raise CodexUnavailableError(f"Codex health check failed: {detail}")
        return result

    def exec_prompt(
        self,
        *,
        workdir: Path,
        prompt: str,
        sandbox: str = "workspace-write",
        timeout_seconds: int | None = None,
    ) -> CodexExecResult:
        """Run Codex and return its result without raising on nonzero exit.

        Callers that need failure-as-exception semantics should use
        ``ensure_success(result)`` after inspecting or persisting runner output.
        """
        command = [
            "codex",
            "exec",
            "--cd",
            str(workdir),
            "--sandbox",
            sandbox,
            "--ask-for-approval",
            "never",
            "--json",
            "-",
        ]
        env, scrubbed_secrets = _scrub_codex_env(os.environ)
        timeout = self._timeout_seconds if timeout_seconds is None else timeout_seconds

        try:
            completed = self._run_command(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=workdir,
                timeout=timeout,
                env=env,
            )
        except FileNotFoundError as exc:
            return CodexExecResult(
                command=command,
                exit_code=127,
                stderr=redact_text(str(exc), secrets=scrubbed_secrets),
            )
        except subprocess.TimeoutExpired as exc:
            return CodexExecResult(
                command=command,
                exit_code=124,
                stdout=redact_text(_process_output(exc.stdout), secrets=scrubbed_secrets),
                stderr=redact_text(_process_output(exc.stderr), secrets=scrubbed_secrets),
            )

        return CodexExecResult(
            command=command,
            exit_code=int(completed.returncode),
            stdout=redact_text(_process_output(completed.stdout), secrets=scrubbed_secrets),
            stderr=redact_text(_process_output(completed.stderr), secrets=scrubbed_secrets),
        )


def ensure_success(result: CodexExecResult) -> CodexExecResult:
    if result.exit_code != 0:
        detail = result.stderr or result.stdout or f"exit code {result.exit_code}"
        raise CodexUnavailableError(f"Codex exec failed: {detail}")
    return result


def _process_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


_SAFE_ENV_PREFIXES = (
    "ANTHROPIC_",
    "AZURE_OPENAI_",
    "CODEX_",
    "GEMINI_",
    "GOOGLE_AI_",
    "LANGCHAIN_",
    "LLM_",
    "OPENAI_",
)
_SAFE_ENV_NAMES = {
    "ALL_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "all_proxy",
    "http_proxy",
    "https_proxy",
    "no_proxy",
}
_SECRET_ENV_MARKERS = (
    "API_KEY",
    "API_SECRET",
    "MNEMONIC",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "SECRET_KEY",
    "SEED_PHRASE",
    "TOKEN",
)
_TRADING_ENV_MARKERS = (
    "ALCHEMY",
    "BINANCE",
    "BITFINEX",
    "BITGET",
    "BITMEX",
    "BROKER",
    "BYBIT",
    "CCXT",
    "COINBASE",
    "DERIBIT",
    "EXCHANGE",
    "FTX",
    "KRAKEN",
    "KUCOIN",
    "OKX",
    "TRADING",
    "WALLET",
    "WEB3",
)


def _scrub_codex_env(env: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    clean: dict[str, str] = {}
    redaction_secrets: list[str] = []
    for name, value in env.items():
        if _should_scrub_env_var(name):
            if value:
                redaction_secrets.append(value)
            continue
        clean[name] = value
        if value and _should_redact_env_value(name, value):
            redaction_secrets.append(value)
            redaction_secrets.extend(_proxy_credentials(name, value))
    return clean, redaction_secrets


def _should_scrub_env_var(name: str) -> bool:
    upper_name = name.upper()
    if name in _SAFE_ENV_NAMES or upper_name in _SAFE_ENV_NAMES:
        return False
    if upper_name.startswith(_SAFE_ENV_PREFIXES):
        return False
    if any(marker in upper_name for marker in _TRADING_ENV_MARKERS):
        return True
    return any(marker in upper_name for marker in _SECRET_ENV_MARKERS)


def _should_redact_env_value(name: str, value: str) -> bool:
    upper_name = name.upper()
    if any(marker in upper_name for marker in _SECRET_ENV_MARKERS):
        return True
    return _is_authenticated_proxy_url(name, value)


def _is_authenticated_proxy_url(name: str, value: str) -> bool:
    if name not in _SAFE_ENV_NAMES and name.upper() not in _SAFE_ENV_NAMES:
        return False
    parsed = urlsplit(value)
    return bool(parsed.scheme and parsed.hostname and (parsed.username or parsed.password))


def _proxy_credentials(name: str, value: str) -> list[str]:
    if name not in _SAFE_ENV_NAMES and name.upper() not in _SAFE_ENV_NAMES:
        return []
    parsed = urlsplit(value)
    return [secret for secret in (parsed.username, parsed.password) if secret]
