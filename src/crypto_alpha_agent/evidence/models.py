from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

ExecutionMode = Literal["research_and_paper_only"]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
PassRate = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
StringTuple = tuple[str, ...]
_UNSAFE_DATA_SOURCE_TOKENS = ("privaterpc", "premiumrpc", "mempool", "mev")

_VALIDATION_EVIDENCE_ID_FIELDS = (
    "strategy_family",
    "symbol",
    "timeframe",
    "validator_name",
    "trade_count",
    "net_return",
    "gross_expectancy",
    "fee_adjusted_expectancy",
    "slippage_adjusted_expectancy",
    "max_drawdown",
    "walk_forward_split_count",
    "walk_forward_pass_rate",
    "approved",
    "blocked_reasons",
)


class _FrozenJSONDict(dict[str, Any]):
    def _reject_mutation(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("parameters are immutable")

    __setitem__ = _reject_mutation
    __delitem__ = _reject_mutation
    clear = _reject_mutation
    pop = _reject_mutation
    popitem = _reject_mutation
    setdefault = _reject_mutation
    update = _reject_mutation
    __ior__ = _reject_mutation


class _StrictEvidenceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        validate_assignment=True,
        frozen=True,
    )

    @field_serializer(
        "data_sources",
        "blocked_reasons",
        "failure_reasons",
        "validation_evidence_ids",
        "paper_outcome_ids",
        "notes",
        check_fields=False,
    )
    def _serialize_string_tuple(self, values: StringTuple) -> list[str]:
        return list(values)

    @field_serializer(
        "created_at",
        "observed_at",
        "signal_timestamp",
        "started_at",
        check_fields=False,
    )
    def _serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class StrategyCandidate(_StrictEvidenceModel):
    candidate_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    parameters: dict[str, Any]
    current_capital_usd: NonNegativeFiniteFloat
    min_capital_usd: NonNegativeFiniteFloat
    data_sources: StringTuple = Field(min_length=1)
    created_at: datetime
    execution_mode: ExecutionMode = "research_and_paper_only"
    requires_speed_edge: bool = False
    requires_premium_rpc: bool = False
    live_order_routing: bool = False
    blocked_reasons: StringTuple = Field(default_factory=tuple)

    @field_validator("candidate_id", "strategy_family", "symbol", "venue", "timeframe")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("data_sources", mode="before")
    @classmethod
    def _normalize_data_sources(cls, values: Iterable[str]) -> StringTuple:
        return _normalize_required_data_sources(values)

    @field_validator("parameters", mode="after")
    @classmethod
    def _validate_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        return _freeze_json_safe_parameters(parameters)

    @field_serializer("parameters")
    def _serialize_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return _thaw_json_safe_value(parameters)

    @field_validator("blocked_reasons", mode="before")
    @classmethod
    def _dedupe_blocked_reasons(cls, values: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(values)

    @model_validator(mode="after")
    def _reject_unsafe_execution_requirements(self) -> Self:
        blocked: list[str] = []
        if self.requires_speed_edge:
            blocked.append("requires_speed_edge")
        if self.requires_premium_rpc:
            blocked.append("requires_premium_rpc")
        if self.live_order_routing:
            blocked.append("live_order_routing")
        if self.min_capital_usd > self.current_capital_usd:
            blocked.append("min_capital_exceeds_current_capital")
        if blocked:
            raise ValueError(f"strategy candidate is not low-capital paper safe: {', '.join(blocked)}")
        return self


class ValidationEvidence(_StrictEvidenceModel):
    evidence_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    validator_name: str = Field(min_length=1)
    trade_count: int = Field(ge=0)
    net_return: FiniteFloat
    gross_expectancy: FiniteFloat
    fee_adjusted_expectancy: FiniteFloat
    slippage_adjusted_expectancy: FiniteFloat
    max_drawdown: NonNegativeFiniteFloat
    walk_forward_split_count: int = Field(ge=0)
    walk_forward_pass_rate: PassRate
    approved: bool
    blocked_reasons: StringTuple = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _populate_evidence_id(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or "evidence_id" in data:
            return data
        generated = _stable_validation_evidence_id(data)
        return {**data, "evidence_id": generated}

    @field_validator("evidence_id", "strategy_family", "symbol", "timeframe", "validator_name")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("blocked_reasons", mode="before")
    @classmethod
    def _dedupe_blocked_reasons(cls, reasons: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(reasons)

    @model_validator(mode="after")
    def _reject_noncanonical_evidence_id(self) -> Self:
        canonical_id = _stable_validation_evidence_id(
            {
                field: getattr(self, field)
                for field in _VALIDATION_EVIDENCE_ID_FIELDS
            }
        )
        if self.evidence_id != canonical_id:
            raise ValueError("evidence_id must match canonical validation evidence payload")
        return self

    @model_validator(mode="after")
    def _reject_approval_contradictions(self) -> Self:
        if not self.approved:
            return self
        if self.walk_forward_split_count == 0:
            raise ValueError("approved validation evidence requires walk-forward splits")
        if self.blocked_reasons:
            raise ValueError("approved validation evidence cannot include blocked_reasons")
        return self


class PaperSimulationOutcome(_StrictEvidenceModel):
    outcome_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    observed_at: datetime
    status: str = Field(min_length=1)
    signal_timestamp: datetime
    entry_price: NonNegativeFiniteFloat
    exit_price: NonNegativeFiniteFloat
    quantity: NonNegativeFiniteFloat
    notional_usd: NonNegativeFiniteFloat
    gross_pnl_usd: FiniteFloat
    fees_usd: NonNegativeFiniteFloat
    slippage_usd: NonNegativeFiniteFloat
    net_pnl_usd: FiniteFloat
    max_drawdown_usd: NonNegativeFiniteFloat
    failure_reasons: StringTuple = Field(default_factory=tuple)
    touched_real_capital: bool = False
    live_order_routing: bool = False

    @field_validator("outcome_id", "run_id", "candidate_id", "strategy_family", "symbol", "status")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("failure_reasons", mode="before")
    @classmethod
    def _dedupe_failure_reasons(cls, reasons: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(reasons)

    @model_validator(mode="after")
    def _reject_live_capital_paths(self) -> Self:
        blocked: list[str] = []
        if self.touched_real_capital:
            blocked.append("touched_real_capital")
        if self.live_order_routing:
            blocked.append("live_order_routing")
        if blocked:
            raise ValueError(f"paper simulation outcome cannot use live execution paths: {', '.join(blocked)}")
        return self


class ExperimentRun(_StrictEvidenceModel):
    run_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    started_at: datetime
    data_sources: StringTuple = Field(min_length=1)
    status: str = Field(min_length=1)
    validation_evidence_ids: StringTuple = Field(default_factory=tuple)
    paper_outcome_ids: StringTuple = Field(default_factory=tuple)
    notes: StringTuple = Field(default_factory=tuple)
    live_order_routing: bool = False

    @field_validator("run_id", "candidate_id", "strategy_family", "status")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("data_sources", mode="before")
    @classmethod
    def _normalize_data_sources(cls, values: Iterable[str]) -> StringTuple:
        return _normalize_required_data_sources(values)

    @field_validator("validation_evidence_ids", "paper_outcome_ids", "notes", mode="before")
    @classmethod
    def _dedupe_string_list(cls, values: Iterable[str]) -> StringTuple:
        return _dedupe_nonempty_strings(values)

    @model_validator(mode="after")
    def _reject_live_order_routing(self) -> Self:
        if self.live_order_routing:
            raise ValueError("experiment run cannot enable live_order_routing")
        return self


def _stable_validation_evidence_id(data: Mapping[str, Any]) -> str:
    payload = {
        field: _canonical_evidence_id_value(field, data.get(field))
        for field in _VALIDATION_EVIDENCE_ID_FIELDS
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"validation-{digest}"


def _canonical_evidence_id_value(field: str, value: Any) -> Any:
    if field == "blocked_reasons":
        if value is None:
            return ()
        return _dedupe_nonempty_strings(value)
    if isinstance(value, str):
        return value.strip()
    return _jsonable_value(value)


def _jsonable_value(value: Any) -> Any:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical evidence values must contain only finite floats")
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return [_jsonable_value(item) for item in value]
    raise ValueError("canonical evidence values must be JSON-safe")


def _strip_nonblank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized


def _normalize_required_data_sources(values: Iterable[str]) -> StringTuple:
    normalized = _dedupe_nonempty_strings(values)
    if not normalized:
        raise ValueError("data_sources must include at least one nonblank source")
    unsafe_sources = [
        source
        for source in normalized
        if any(token in _data_source_safety_key(source) for token in _UNSAFE_DATA_SOURCE_TOKENS)
    ]
    if unsafe_sources:
        raise ValueError(f"data_sources include unsafe live-only sources: {', '.join(unsafe_sources)}")
    return normalized


def _data_source_safety_key(source: str) -> str:
    return "".join(character for character in source.lower() if character.isalnum())


def _freeze_json_safe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return _freeze_json_safe_value(parameters)


def _freeze_json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("parameters must contain only finite floats")
        return value
    if isinstance(value, list):
        return tuple(_freeze_json_safe_value(item) for item in value)
    if isinstance(value, dict):
        frozen = _FrozenJSONDict()
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("parameters must use string keys")
            dict.__setitem__(frozen, key, _freeze_json_safe_value(item))
        return frozen
    raise ValueError("parameters must contain only JSON-safe values")


def _thaw_json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_safe_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_safe_value(item) for item in value]
    return value


def _dedupe_nonempty_strings(values: Iterable[str]) -> StringTuple:
    if values is None or isinstance(values, str | bytes) or not isinstance(values, Iterable):
        raise ValueError("value must be a collection of strings")
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("value must be a string")
        normalized = value.strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return tuple(deduped)
