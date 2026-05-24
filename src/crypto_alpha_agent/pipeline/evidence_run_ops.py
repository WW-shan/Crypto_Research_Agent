from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.llm.redaction import redact_text

NetworkRoute = Literal["direct", "proxy", "blocked", "not_applicable", "unknown"]
_URL_PATTERN = re.compile(r"https?://[^\s'\";,)}]+")

_PROXY_ENV_NAMES = (
    "CRYPTO_ALPHA_AGENT_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


class EvidenceRunLockError(RuntimeError):
    reason_code = "evidence_run_lock_held"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__(f"evidence-run lock is already held: {self.path}")


class EvidenceRunLock:
    def __init__(self, path: str | Path, *, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self._acquired = False

    def __enter__(self) -> "EvidenceRunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "run_id": self.run_id,
                "acquired_at": datetime.now(tz=UTC).isoformat(),
            },
            sort_keys=True,
        )
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise EvidenceRunLockError(self.path) from exc
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
        self._acquired = True
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        if not self._acquired:
            return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        if current.get("run_id") == self.run_id:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self._acquired = False


class EvidenceRunArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    path: str
    exists: bool


class EvidenceRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    run_id: str
    status: Literal["success", "failed", "blocked"]
    started_at: str
    completed_at: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    network_route: NetworkRoute
    artifacts: dict[str, str | None] = Field(default_factory=dict)
    artifact_status: dict[str, EvidenceRunArtifact] = Field(default_factory=dict)
    source_health: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    decision_reason_codes: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    failure: str | None = None
    llm_interpretation: dict[str, Any] | None = None
    llm_provider: str | None = None
    used_fake_llm: bool | None = None
    llm_role: str | None = None
    llm_provider_verified: bool | None = None
    llm_model: str | None = None
    llm_health_schema: str | None = None
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def write_json_artifact(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    latest_path: str | Path | None = None,
) -> None:
    encoded = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    write_text_artifact(path, encoded, latest_path=latest_path)


def write_text_artifact(
    path: str | Path,
    text: str,
    *,
    latest_path: str | Path | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, target)
    if latest_path is not None:
        latest = Path(latest_path)
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest_temp = latest.with_name(f".{latest.name}.tmp")
        latest_temp.write_text(text, encoding="utf-8")
        os.replace(latest_temp, latest)


def network_route_from_environment(
    *,
    env: Mapping[str, str] | None = None,
    allow_network: bool,
) -> NetworkRoute:
    if not allow_network:
        return "blocked"
    source = os.environ if env is None else env
    return "proxy" if any(source.get(name) for name in _PROXY_ENV_NAMES) else "direct"


def redacted_evidence_run_inputs(values: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        key_text = str(key)
        if key_text in {"dune_api_key", "subgraph_url"}:
            redacted[f"{key_text}_configured"] = bool(value)
            continue
        if key_text == "dune_params":
            redacted["dune_param_keys"] = _key_value_keys(value)
            continue
        if key_text == "graph_variables":
            redacted["graph_variable_keys"] = _key_value_keys(value)
            continue
        if key_text == "graph_query":
            text = "" if value is None else str(value)
            redacted["graph_query_configured"] = bool(text.strip())
            redacted["graph_query_length"] = len(text)
            continue
        if value is None or isinstance(value, str | int | float | bool):
            redacted[key_text] = value
        elif isinstance(value, Path):
            redacted[key_text] = str(value)
        elif isinstance(value, list | tuple):
            redacted[key_text] = list(value)
        else:
            redacted[key_text] = str(value)
    return redacted


def _key_value_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        raw_keys = value.keys()
    else:
        raw_keys = []
        for item in value or []:
            if isinstance(item, tuple | list) and item:
                raw_keys.append(str(item[0]))
                continue
            text = str(item)
            key, separator, _secret_value = text.partition("=")
            raw_keys.append(key if separator else text)
    seen: set[str] = set()
    for raw_key in raw_keys:
        key = str(raw_key).strip()
        if key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def redacted_failure(message: object, *, secrets: list[str | None] | None = None) -> str:
    redacted = redact_text(message, secrets=[secret for secret in secrets or [] if secret])
    return _URL_PATTERN.sub("[REDACTED_URL]", redacted)
