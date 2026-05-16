from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Annotated, Any, Literal

from crypto_alpha_agent.execution.paper import PaperTradeResult
from pydantic import BaseModel, ConfigDict, Field, field_validator

PaperEvidenceStatus = Literal["closed", "filled", "success", "failed", "rejected", "blocked"]

FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]

_CLOSED_STATUSES = {"closed", "filled", "success"}
_FAILED_STATUSES = {"failed", "rejected", "blocked"}


class PaperEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str = Field(min_length=1)
    trade_id: str | None = None
    symbol: str | None = None
    status: PaperEvidenceStatus
    realized_net_pnl: FiniteFloat | None = None
    max_drawdown_usd: NonNegativeFiniteFloat | None = None
    failure_reasons: list[str] = Field(default_factory=list)

    @field_validator("failure_reasons")
    @classmethod
    def _dedupe_failure_reasons(cls, reasons: list[str]) -> list[str]:
        return _dedupe([reason for reason in reasons if reason])


class PaperEvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    closed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    net_pnl_usd: FiniteFloat
    hit_rate: FiniteFloat
    max_drawdown_usd: NonNegativeFiniteFloat
    failure_reasons: list[str] = Field(default_factory=list)
    approved_for_review: bool = False


def aggregate_paper_evidence(
    items: Iterable[PaperEvidenceInput | PaperTradeResult | Mapping[str, Any]],
    *,
    strategy_family: str | None = None,
) -> list[PaperEvidencePackage]:
    evidence_inputs = [_coerce_input(item, strategy_family=strategy_family) for item in items]
    if strategy_family is not None:
        evidence_inputs = [item for item in evidence_inputs if item.strategy_family == strategy_family]
    if not evidence_inputs:
        return []

    packages: list[PaperEvidencePackage] = []
    for family in sorted({item.strategy_family for item in evidence_inputs}):
        family_items = [item for item in evidence_inputs if item.strategy_family == family]
        closed_items = [item for item in family_items if item.status in _CLOSED_STATUSES]
        failed_items = [item for item in family_items if item.status in _FAILED_STATUSES]
        pnl_values = [item.realized_net_pnl for item in family_items if item.realized_net_pnl is not None]
        failure_reasons: list[str] = []
        max_drawdown = 0.0

        for item in family_items:
            failure_reasons.extend(item.failure_reasons)
            if item.max_drawdown_usd is not None:
                max_drawdown = max(max_drawdown, item.max_drawdown_usd)
            if item.realized_net_pnl is not None and item.realized_net_pnl < 0:
                max_drawdown = max(max_drawdown, abs(item.realized_net_pnl))

        packages.append(
            PaperEvidencePackage(
                strategy_family=family,
                sample_size=len(family_items),
                closed_count=len(closed_items),
                failed_count=len(failed_items),
                net_pnl_usd=sum(pnl_values),
                hit_rate=_hit_rate(closed_items),
                max_drawdown_usd=max_drawdown,
                failure_reasons=_dedupe(failure_reasons),
            )
        )

    return packages


def _coerce_input(
    item: PaperEvidenceInput | PaperTradeResult | Mapping[str, Any],
    *,
    strategy_family: str | None,
) -> PaperEvidenceInput:
    if isinstance(item, PaperEvidenceInput):
        return item
    if isinstance(item, PaperTradeResult):
        return PaperEvidenceInput(
            strategy_family=strategy_family or "paper_execution",
            symbol=item.fill.symbol,
            status="closed",
            realized_net_pnl=item.realized_net_pnl,
        )
    if isinstance(item, Mapping):
        return PaperEvidenceInput.model_validate(_normalize_mapping(item))
    raise TypeError(f"unsupported paper evidence input type: {type(item).__name__}")


def _normalize_mapping(item: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "strategy_family": item.get("strategy_family"),
        "trade_id": item.get("trade_id"),
        "symbol": item.get("symbol"),
        "status": item.get("status"),
        "realized_net_pnl": _first_present(item, "realized_net_pnl", "realized_pnl_usd"),
        "max_drawdown_usd": _drawdown_value(item),
        "failure_reasons": _failure_reasons(item),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def _first_present(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def _drawdown_value(item: Mapping[str, Any]) -> Any:
    value = _first_present(item, "max_drawdown_usd", "drawdown_usd", "max_downside_usd")
    if value is None:
        return None
    return abs(value)


def _failure_reasons(item: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key in ("reason_codes", "failure_reasons"):
        value = item.get(key)
        if isinstance(value, str):
            reasons.append(value)
        elif value is not None:
            reasons.extend(str(reason) for reason in value if reason)
    error_reason = item.get("error_reason")
    if error_reason:
        reasons.append(str(error_reason))
    return _dedupe(reasons)


def _hit_rate(closed_items: list[PaperEvidenceInput]) -> float:
    if not closed_items:
        return 0.0
    wins = sum(1 for item in closed_items if item.realized_net_pnl is not None and item.realized_net_pnl > 0)
    return wins / len(closed_items)


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
