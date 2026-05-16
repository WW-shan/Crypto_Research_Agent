from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ExecutionMode = Literal["research_and_paper_only"]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]

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


class _StrictEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class StrategyCandidate(_StrictEvidenceModel):
    candidate_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    parameters: dict[str, Any]
    current_capital_usd: NonNegativeFiniteFloat
    min_capital_usd: NonNegativeFiniteFloat
    data_sources: list[str] = Field(min_length=1)
    created_at: datetime
    execution_mode: ExecutionMode = "research_and_paper_only"
    requires_speed_edge: bool = False
    requires_premium_rpc: bool = False
    live_order_routing: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    @field_validator("data_sources", "blocked_reasons")
    @classmethod
    def _dedupe_string_list(cls, values: list[str]) -> list[str]:
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
    walk_forward_pass_rate: FiniteFloat
    approved: bool
    blocked_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _populate_evidence_id(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or data.get("evidence_id"):
            return data
        generated = _stable_validation_evidence_id(data)
        return {**data, "evidence_id": generated}

    @field_validator("blocked_reasons")
    @classmethod
    def _dedupe_blocked_reasons(cls, reasons: list[str]) -> list[str]:
        return _dedupe_nonempty_strings(reasons)


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
    failure_reasons: list[str] = Field(default_factory=list)
    touched_real_capital: bool = False
    live_order_routing: bool = False

    @field_validator("failure_reasons")
    @classmethod
    def _dedupe_failure_reasons(cls, reasons: list[str]) -> list[str]:
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
    data_sources: list[str] = Field(min_length=1)
    status: str = Field(min_length=1)
    validation_evidence_ids: list[str] = Field(default_factory=list)
    paper_outcome_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    live_order_routing: bool = False

    @field_validator("data_sources", "validation_evidence_ids", "paper_outcome_ids", "notes")
    @classmethod
    def _dedupe_string_list(cls, values: list[str]) -> list[str]:
        return _dedupe_nonempty_strings(values)

    @model_validator(mode="after")
    def _reject_live_order_routing(self) -> Self:
        if self.live_order_routing:
            raise ValueError("experiment run cannot enable live_order_routing")
        return self


def _stable_validation_evidence_id(data: Mapping[str, Any]) -> str:
    payload = {
        field: _jsonable_value(data.get(field))
        for field in _VALIDATION_EVIDENCE_ID_FIELDS
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"validation-{digest}"


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return [_jsonable_value(item) for item in value]
    return value


def _dedupe_nonempty_strings(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped
