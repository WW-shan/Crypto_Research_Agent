from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crypto_alpha_agent.config import LLMRole, build_required_real_llm
from crypto_alpha_agent.llm.redaction import redact_text

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class LLMRuntimeError(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}")


class _RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LLMHealthCheckTask(_RuntimeModel):
    command: str = Field(min_length=1)
    schema_name: Literal["LLMHealthCheckResult"] = "LLMHealthCheckResult"
    objective: str = Field(
        default=(
            "Return a strict JSON health response proving structured output support "
            "for the LLM-native crypto research runtime."
        ),
        min_length=1,
    )
    required_capabilities: tuple[str, ...] = ("json_schema", "research_only")


class LLMHealthCheckResult(_RuntimeModel):
    status: Literal["ok"]
    schema_name: Literal["LLMHealthCheckResult"]
    capabilities: list[str] = Field(min_length=2)
    uses_real_capital: Literal[False]
    live_order_routing: Literal[False]


class RealLLMRuntime:
    def __init__(
        self,
        *,
        llm: Any,
        provider: Literal["real"],
        role: LLMRole,
        _allow_test_double: bool = False,
    ) -> None:
        if provider != "real":
            raise LLMRuntimeError(
                "fake_llm_not_allowed",
                "Product runtime requires a real LLM provider.",
            )
        provider_verified = _is_openai_responses_adapter(llm)
        if not provider_verified and not _allow_test_double:
            raise LLMRuntimeError(
                "unverified_llm_provider",
                "Product runtime requires the configured real LLM adapter.",
            )
        self.llm = llm
        self.provider = provider
        self.role = role
        self._provider_verified = provider_verified
        self._used_test_double = _allow_test_double
        self.last_health: LLMHealthCheckResult | None = None

    @classmethod
    def _for_test_double(cls, *, llm: Any, role: LLMRole) -> RealLLMRuntime:
        return cls(
            llm=llm,
            provider="real",
            role=role,
            _allow_test_double=True,
        )

    def health_check(self, *, command: str) -> LLMHealthCheckResult:
        raw_response = self.llm(LLMHealthCheckTask(command=command))
        result = parse_structured_llm_json(raw_response, LLMHealthCheckResult)
        required = {"json_schema", "research_only"}
        if not required.issubset(set(result.capabilities)):
            raise LLMRuntimeError(
                "llm_health_missing_capability",
                "LLM health check did not report required capabilities.",
            )
        self.last_health = result
        return result

    def structured_call(
        self, task: BaseModel, output_model: type[StructuredModel]
    ) -> StructuredModel:
        return parse_structured_llm_json(self.llm(task), output_model)

    def metadata(self) -> dict[str, Any]:
        settings = getattr(self.llm, "settings", None)
        metadata: dict[str, Any] = {
            "llm_provider": self.provider,
            "used_fake_llm": self._used_test_double,
            "llm_role": self.role,
            "llm_provider_verified": self._provider_verified,
        }
        model = getattr(settings, "model", None)
        if model:
            metadata["llm_model"] = str(model)
        if self.last_health is not None:
            metadata["llm_health_schema"] = self.last_health.schema_name
        return metadata


def build_required_real_llm_runtime(
    *,
    env_file: str | Path | None = Path(".env"),
    role: LLMRole = "research",
    env: dict[str, str] | None = None,
) -> RealLLMRuntime:
    try:
        llm = build_required_real_llm(env_file=env_file, role=role, env=env)
    except ValueError as exc:
        raise LLMRuntimeError(
            "llm_configuration_missing",
            redact_text(str(exc)),
        ) from None
    return RealLLMRuntime(llm=llm, provider="real", role=role)


def parse_structured_llm_json(
    raw_response: Any, output_model: type[StructuredModel]
) -> StructuredModel:
    _require_strict_output_model(output_model)
    if not isinstance(raw_response, str):
        raise LLMRuntimeError(
            "invalid_llm_response_type",
            "LLM response must be a string.",
        )
    try:
        payload = json.loads(raw_response, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        digest = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()[:12]
        raise LLMRuntimeError(
            "invalid_json",
            f"LLM response was not valid JSON: sha256={digest}",
        ) from None
    try:
        return output_model.model_validate(payload)
    except ValidationError:
        raise LLMRuntimeError(
            "schema_validation_failed",
            f"LLM response failed schema validation for {output_model.__name__}.",
        ) from None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _require_strict_output_model(output_model: type[StructuredModel]) -> None:
    if not isinstance(output_model, type) or not issubclass(output_model, BaseModel):
        raise LLMRuntimeError(
            "unsafe_output_schema",
            "LLM output schema must be a Pydantic BaseModel.",
        )
    config = output_model.model_config
    if (
        config.get("strict") is not True
        or config.get("extra") != "forbid"
        or config.get("allow_inf_nan") is not False
    ):
        raise LLMRuntimeError(
            "unsafe_output_schema",
            (
                f"LLM output schema {output_model.__name__} must set strict=True, "
                "extra='forbid', and allow_inf_nan=False."
            ),
        )


def _is_openai_responses_adapter(llm: Any) -> bool:
    return (
        llm.__class__.__module__ == "crypto_alpha_agent.llm.responses"
        and llm.__class__.__name__ == "OpenAIResponsesAdapter"
    )
