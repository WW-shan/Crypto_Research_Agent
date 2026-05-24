from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

ActionMode = Literal["research_only", "paper", "gated_live"]
LLMRole = Literal[
    "default",
    "research",
    "planning",
    "coder",
    "validator_design",
    "summary",
    "report",
    "fast",
]


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_mode: ActionMode = "research_only"
    max_capital_per_trade_usd: float | None = Field(default=None, ge=0)
    min_confidence: float = Field(default=0.0, ge=0, le=1)
    require_human_approval: bool = True


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
        missing = [
            name
            for name, value in (
                ("OPENAI_BASE_URL", base_url),
                ("OPENAI_API_KEY", api_key),
                ("OPENAI_MODEL or role model", model),
            )
            if not value
        ]
        if api_type != "responses":
            missing.append("OPENAI_API_TYPE=responses")
        if missing:
            if required:
                raise ValueError(
                    "Real LLM is required but local configuration is incomplete: "
                    + ", ".join(missing)
                )
            return None
        return cls(
            base_url=base_url,
            api_key=SecretStr(api_key),
            model=model,
            role=role,
            api_type="responses",
        )

    def safe_summary(self) -> dict[str, object]:
        return {
            "api_type": self.api_type,
            "role": self.role,
            "model": self.model,
            "base_url_configured": bool(self.base_url),
            "api_key_configured": bool(self.api_key.get_secret_value()),
            "timeout_seconds": self.timeout_seconds,
        }


def build_configured_llm_settings(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    required: bool = False,
    env: dict[str, str] | None = None,
) -> LLMSettings | None:
    return LLMSettings.from_env(
        env_file=env_file,
        role=role,
        required=required,
        env=env,
    )


def build_configured_llm(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    required: bool = False,
    env: dict[str, str] | None = None,
):
    settings = build_configured_llm_settings(
        env_file=env_file,
        role=role,
        required=required,
        env=env,
    )
    if settings is None:
        return None
    from crypto_alpha_agent.llm.responses import OpenAIResponsesAdapter

    return OpenAIResponsesAdapter(settings)


def build_required_real_llm(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    env: dict[str, str] | None = None,
):
    settings = build_configured_llm_settings(
        env_file=env_file,
        role=role,
        required=True,
        env=env,
    )
    if settings is None:
        raise ValueError("Real LLM is required but settings were not built.")
    from crypto_alpha_agent.llm.responses import OpenAIResponsesAdapter

    return OpenAIResponsesAdapter(settings)


def _model_for_role(values: dict[str, str], role: LLMRole) -> str:
    fallback = values.get("OPENAI_MODEL", "").strip()
    if role in {"default", "research", "planning"}:
        return values.get("OPENAI_RESEARCH_MODEL", "").strip() or fallback
    if role in {"coder", "validator_design"}:
        return values.get("OPENAI_CODER_MODEL", "").strip() or fallback
    if role in {"summary", "report", "fast"}:
        return values.get("OPENAI_FAST_MODEL", "").strip() or fallback
    return fallback


def _load_llm_env(
    *, env_file: str | Path | None, env: dict[str, str] | None
) -> dict[str, str]:
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
