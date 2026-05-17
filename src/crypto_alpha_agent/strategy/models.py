from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from typing_extensions import Self

from crypto_alpha_agent.data.models import ExecutionRole, RecordType

NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
StringTuple = tuple[str, ...]


class _StrictStrategyModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        validate_assignment=True,
        frozen=True,
    )

    @field_serializer(
        "required_record_types",
        "required_symbols",
        "blocked_reasons",
        check_fields=False,
    )
    def _serialize_string_tuple(self, values: StringTuple) -> list[str]:
        return list(values)


class StrategyFamilySpec(_StrictStrategyModel):
    strategy_family: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    required_record_types: tuple[RecordType, ...] = Field(min_length=1)
    required_symbols: StringTuple = Field(min_length=1)
    execution_role: ExecutionRole = "research_and_paper"
    supports_paper_simulation: bool
    min_capital_usd: NonNegativeFiniteFloat
    max_notional_usd: NonNegativeFiniteFloat
    requires_speed_edge: Literal[False] = False
    requires_premium_rpc: Literal[False] = False
    live_order_routing: Literal[False] = False
    uses_real_capital: Literal[False] = False
    validator_name: str = Field(min_length=1)
    blocked_reasons: StringTuple
    configured_capital_usd: NonNegativeFiniteFloat = 300.0

    @field_validator("strategy_family", "display_name", "validator_name")
    @classmethod
    def _strip_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped

    @field_validator("required_record_types", "required_symbols", "blocked_reasons", mode="before")
    @classmethod
    def _normalize_string_tuple(cls, values: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(values)

    @model_validator(mode="after")
    def _reject_unsafe_or_too_expensive_spec(self) -> Self:
        blocked: list[str] = []
        if self.requires_speed_edge:
            blocked.append("requires_speed_edge")
        if self.requires_premium_rpc:
            blocked.append("requires_premium_rpc")
        if self.live_order_routing:
            blocked.append("live_order_routing")
        if self.min_capital_usd > self.configured_capital_usd:
            blocked.append("min_capital_exceeds_configured_capital")
        if blocked:
            raise ValueError(f"strategy spec is not low-capital paper safe: {', '.join(blocked)}")
        return self


class StrategyValidationRequest(_StrictStrategyModel):
    strategy_family: str = Field(min_length=1)
    records: tuple[dict[str, Any], ...]
    current_capital_usd: NonNegativeFiniteFloat
    parameters: dict[str, Any] = Field(default_factory=dict)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("strategy_family")
    @classmethod
    def _strip_strategy_family(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("records", mode="before")
    @classmethod
    def _normalize_records(cls, records: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        return tuple(records)


class StrategyValidationReport(_StrictStrategyModel):
    strategy_family: str = Field(min_length=1)
    validator_name: str = Field(min_length=1)
    approved: bool
    blocked_reasons: StringTuple
    metrics: dict[str, Any] = Field(default_factory=dict)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("strategy_family", "validator_name")
    @classmethod
    def _strip_nonblank(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("blocked_reasons", mode="before")
    @classmethod
    def _normalize_blocked_reasons(cls, values: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(values)

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> Self:
        if self.approved and self.blocked_reasons:
            raise ValueError("approved validation report cannot include blocked_reasons")
        if not self.approved and not self.blocked_reasons:
            raise ValueError("blocked validation report requires blocked_reasons")
        return self


class StrategyPaperRequest(_StrictStrategyModel):
    strategy_family: str = Field(min_length=1)
    records: tuple[dict[str, Any], ...]
    current_capital_usd: NonNegativeFiniteFloat
    notional_usd: NonNegativeFiniteFloat
    parameters: dict[str, Any] = Field(default_factory=dict)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("strategy_family")
    @classmethod
    def _strip_strategy_family(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("records", mode="before")
    @classmethod
    def _normalize_records(cls, records: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        return tuple(records)


class StrategyPaperReport(_StrictStrategyModel):
    strategy_family: str = Field(min_length=1)
    status: Literal["blocked", "simulated", "unsupported"]
    supports_paper_simulation: bool
    blocked_reasons: StringTuple
    metrics: dict[str, Any] = Field(default_factory=dict)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("strategy_family")
    @classmethod
    def _strip_strategy_family(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("blocked_reasons", mode="before")
    @classmethod
    def _normalize_blocked_reasons(cls, values: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(values)

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> Self:
        if self.status == "simulated" and self.blocked_reasons:
            raise ValueError("simulated paper report cannot include blocked_reasons")
        if self.status in {"blocked", "unsupported"} and not self.blocked_reasons:
            raise ValueError("non-simulated paper report requires blocked_reasons")
        return self


def _strip_nonblank(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("must be non-empty")
    return stripped


def _dedupe_nonempty_strings(values: Iterable[object]) -> StringTuple:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = _strip_nonblank(value)
        if stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return tuple(normalized)
