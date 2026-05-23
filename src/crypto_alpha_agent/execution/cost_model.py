from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CostModelMode = Literal["base", "pessimistic"]
ExecutionEstimateStatus = Literal["tradeable", "blocked"]
FillStatus = Literal["full", "partial", "missed", "blocked"]
StaleSignalStatus = Literal["fresh", "stale", "not_evaluated"]

FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
ParticipationRate = Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]


class _StrictCostModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, frozen=True)


class ExchangeFeeSchedule(_StrictCostModel):
    venue: str = Field(min_length=1)
    fee_model_id: str = Field(min_length=1)
    maker_fee_rate: NonNegativeFiniteFloat
    taker_fee_rate: NonNegativeFiniteFloat
    source: str = Field(default="configured_public_fee_schedule", min_length=1)

    @field_validator("venue", "fee_model_id", "source")
    @classmethod
    def _strip_nonblank(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def _reject_inverted_rates(self) -> ExchangeFeeSchedule:
        if self.taker_fee_rate < self.maker_fee_rate:
            raise ValueError("taker_fee_rate must be greater than or equal to maker_fee_rate")
        return self


class SymbolMarketConstraints(_StrictCostModel):
    venue: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    min_notional_usd: NonNegativeFiniteFloat = 5.0
    min_quantity: NonNegativeFiniteFloat = 0.0
    quantity_step: NonNegativeFiniteFloat = 0.000001
    tick_size: NonNegativeFiniteFloat = 0.01
    source: str = Field(default="configured_public_exchange_metadata", min_length=1)

    @field_validator("venue", "symbol", "source")
    @classmethod
    def _strip_nonblank(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, value: str) -> str:
        return value.lower()


class ExecutionCostAssumptions(_StrictCostModel):
    venue: str = Field(min_length=1)
    cost_model_mode: CostModelMode = "pessimistic"
    max_notional_usd: PositiveFiniteFloat = 25.0
    fee_rate_floor: NonNegativeFiniteFloat = 0.001
    fixed_slippage_bps: NonNegativeFiniteFloat = 5.0
    max_signal_age_seconds: NonNegativeFiniteFloat | None = 3600.0
    max_volume_participation_rate: ParticipationRate = 0.05
    allow_partial_fills: bool = False
    fee_schedule: ExchangeFeeSchedule | None = None
    symbol_constraints: SymbolMarketConstraints | None = None

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, value: str) -> str:
        return _strip_nonblank(value).lower()


class ExecutionTradeSpec(_StrictCostModel):
    symbol: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_reference_price: PositiveFiniteFloat
    exit_reference_price: PositiveFiniteFloat
    raw_return: FiniteFloat
    requested_notional_usd: NonNegativeFiniteFloat
    entry_volume: NonNegativeFiniteFloat | None = None
    exit_volume: NonNegativeFiniteFloat | None = None
    next_funding_at: datetime | None = None

    @field_validator("symbol", "direction")
    @classmethod
    def _strip_nonblank(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, value: str) -> str:
        return _strip_nonblank(value).lower()


class ExecutionCostEstimate(_StrictCostModel):
    status: ExecutionEstimateStatus
    venue: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    cost_model_mode: CostModelMode
    fee_model_id: str = Field(min_length=1)
    maker_fee_rate: NonNegativeFiniteFloat
    taker_fee_rate: NonNegativeFiniteFloat
    applied_entry_fee_rate: NonNegativeFiniteFloat
    applied_exit_fee_rate: NonNegativeFiniteFloat
    slippage_bps: NonNegativeFiniteFloat
    stale_signal_status: StaleSignalStatus
    signal_age_seconds: NonNegativeFiniteFloat | None
    fill_status: FillStatus
    fill_ratio: float = Field(ge=0, le=1, strict=True, allow_inf_nan=False)
    entry_price: NonNegativeFiniteFloat
    exit_price: NonNegativeFiniteFloat
    quantity: NonNegativeFiniteFloat
    requested_notional_usd: NonNegativeFiniteFloat
    effective_notional_usd: NonNegativeFiniteFloat
    gross_pnl_usd: FiniteFloat
    entry_fee_usd: NonNegativeFiniteFloat
    exit_fee_usd: NonNegativeFiniteFloat
    fees_usd: NonNegativeFiniteFloat
    slippage_usd: NonNegativeFiniteFloat
    net_pnl_usd: FiniteFloat
    max_drawdown_usd: NonNegativeFiniteFloat
    failure_reasons: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("venue")
    @classmethod
    def _normalize_venue(cls, value: str) -> str:
        return _strip_nonblank(value).lower()

    @field_validator("symbol", "fee_model_id")
    @classmethod
    def _strip_nonblank(cls, value: str) -> str:
        return _strip_nonblank(value)

    @field_validator("failure_reasons", mode="before")
    @classmethod
    def _dedupe_failure_reasons(cls, values: Iterable[str]) -> tuple[str, ...]:
        return _dedupe_nonempty_strings(values)


def estimate_execution_cost(
    trade: ExecutionTradeSpec,
    assumptions: ExecutionCostAssumptions,
) -> ExecutionCostEstimate:
    fee_schedule = assumptions.fee_schedule or default_fee_schedule(assumptions.venue)
    constraints = assumptions.symbol_constraints or default_symbol_constraints(
        assumptions.venue,
        trade.symbol,
    )
    entry_price = _adverse_price(
        trade.entry_reference_price,
        constraints.tick_size,
        direction=trade.direction,
        leg="entry",
    )
    exit_price = _adverse_price(
        trade.exit_reference_price,
        constraints.tick_size,
        direction=trade.direction,
        leg="exit",
    )
    requested_notional = min(
        float(trade.requested_notional_usd),
        float(assumptions.max_notional_usd),
    )
    failure_reasons: list[str] = []

    if constraints.min_notional_usd > assumptions.max_notional_usd:
        failure_reasons.append("min_notional_exceeds_max_notional")
    min_quantity_notional = float(constraints.min_quantity) * entry_price
    if min_quantity_notional > assumptions.max_notional_usd:
        failure_reasons.append("min_quantity_notional_exceeds_max_notional")

    quantity = _round_quantity_down(
        requested_notional / entry_price,
        constraints.quantity_step,
    )
    if quantity <= 0 or quantity < constraints.min_quantity:
        failure_reasons.append("quantity_precision_not_tradeable")

    effective_notional = quantity * entry_price
    if effective_notional > assumptions.max_notional_usd:
        failure_reasons.append("rounded_notional_exceeds_max_notional")
    if effective_notional < constraints.min_notional_usd and effective_notional > 0:
        failure_reasons.append("effective_notional_below_min_notional")

    signal_age_seconds, stale_status = _signal_age(
        signal_timestamp=trade.signal_timestamp,
        entry_timestamp=trade.entry_timestamp,
        max_signal_age_seconds=assumptions.max_signal_age_seconds,
    )
    if stale_status == "stale":
        failure_reasons.append("stale_signal")

    fill_status: FillStatus = "full"
    fill_ratio = 1.0 if effective_notional > 0 else 0.0
    capacity = _volume_capacity_usd(
        trade,
        entry_price=entry_price,
        exit_price=exit_price,
        participation_rate=assumptions.max_volume_participation_rate,
    )
    if capacity is not None and capacity < effective_notional:
        if assumptions.allow_partial_fills and capacity >= constraints.min_notional_usd:
            partial_quantity = _round_quantity_down(capacity / entry_price, constraints.quantity_step)
            partial_notional = partial_quantity * entry_price
            if partial_quantity > 0 and partial_notional >= constraints.min_notional_usd:
                fill_status = "partial"
                fill_ratio = partial_notional / effective_notional if effective_notional else 0.0
                quantity = partial_quantity
                effective_notional = partial_notional
            else:
                fill_status = "blocked"
                fill_ratio = 0.0
                failure_reasons.append("partial_fill_below_min_notional")
        else:
            fill_status = "missed"
            fill_ratio = 0.0
            failure_reasons.append("missed_fill_assumed")

    if failure_reasons:
        return _blocked_estimate(
            trade,
            assumptions=assumptions,
            fee_schedule=fee_schedule,
            entry_price=entry_price,
            exit_price=exit_price,
            requested_notional=requested_notional,
            stale_signal_status=stale_status,
            signal_age_seconds=signal_age_seconds,
            fill_status=fill_status if fill_status != "full" else "blocked",
            failure_reasons=failure_reasons,
        )

    entry_rate = _applied_fee_rate(fee_schedule, assumptions)
    exit_rate = _applied_fee_rate(fee_schedule, assumptions)
    gross_pnl = effective_notional * float(trade.raw_return)
    entry_fee = effective_notional * entry_rate
    exit_fee = effective_notional * exit_rate
    fees = entry_fee + exit_fee
    slippage = effective_notional * (float(assumptions.fixed_slippage_bps) / 10_000.0) * 2.0
    net_pnl = gross_pnl - fees - slippage
    estimate_status: ExecutionEstimateStatus = "tradeable"
    if gross_pnl > 0 and net_pnl <= 0:
        estimate_status = "blocked"
        failure_reasons.append("pre_cost_only_profitable")

    return ExecutionCostEstimate(
        status=estimate_status,
        venue=assumptions.venue,
        symbol=trade.symbol,
        cost_model_mode=assumptions.cost_model_mode,
        fee_model_id=fee_schedule.fee_model_id,
        maker_fee_rate=fee_schedule.maker_fee_rate,
        taker_fee_rate=fee_schedule.taker_fee_rate,
        applied_entry_fee_rate=entry_rate,
        applied_exit_fee_rate=exit_rate,
        slippage_bps=assumptions.fixed_slippage_bps,
        stale_signal_status=stale_status,
        signal_age_seconds=signal_age_seconds,
        fill_status=fill_status,
        fill_ratio=float(fill_ratio),
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        requested_notional_usd=requested_notional,
        effective_notional_usd=effective_notional,
        gross_pnl_usd=float(gross_pnl),
        entry_fee_usd=float(entry_fee),
        exit_fee_usd=float(exit_fee),
        fees_usd=float(fees),
        slippage_usd=float(slippage),
        net_pnl_usd=float(net_pnl),
        max_drawdown_usd=max(0.0, -float(net_pnl)),
        failure_reasons=failure_reasons,
    )


def default_fee_schedule(venue: str) -> ExchangeFeeSchedule:
    normalized_venue = _strip_nonblank(venue).lower()
    return _DEFAULT_FEE_SCHEDULES.get(
        normalized_venue,
        ExchangeFeeSchedule(
            venue=normalized_venue,
            fee_model_id=f"{normalized_venue}:generic-conservative-maker-taker",
            maker_fee_rate=0.001,
            taker_fee_rate=0.001,
        ),
    )


def default_symbol_constraints(venue: str, symbol: str) -> SymbolMarketConstraints:
    normalized_venue = _strip_nonblank(venue).lower()
    normalized_symbol = _strip_nonblank(symbol)
    return _DEFAULT_CONSTRAINTS.get(
        (normalized_venue, normalized_symbol),
        SymbolMarketConstraints(
            venue=normalized_venue,
            symbol=normalized_symbol,
            min_notional_usd=5.0,
            min_quantity=0.0,
            quantity_step=0.000001,
            tick_size=0.01,
        ),
    )


def _blocked_estimate(
    trade: ExecutionTradeSpec,
    *,
    assumptions: ExecutionCostAssumptions,
    fee_schedule: ExchangeFeeSchedule,
    entry_price: float,
    exit_price: float,
    requested_notional: float,
    stale_signal_status: StaleSignalStatus,
    signal_age_seconds: float | None,
    fill_status: FillStatus,
    failure_reasons: list[str],
) -> ExecutionCostEstimate:
    entry_rate = _applied_fee_rate(fee_schedule, assumptions)
    exit_rate = _applied_fee_rate(fee_schedule, assumptions)
    return ExecutionCostEstimate(
        status="blocked",
        venue=assumptions.venue,
        symbol=trade.symbol,
        cost_model_mode=assumptions.cost_model_mode,
        fee_model_id=fee_schedule.fee_model_id,
        maker_fee_rate=fee_schedule.maker_fee_rate,
        taker_fee_rate=fee_schedule.taker_fee_rate,
        applied_entry_fee_rate=entry_rate,
        applied_exit_fee_rate=exit_rate,
        slippage_bps=assumptions.fixed_slippage_bps,
        stale_signal_status=stale_signal_status,
        signal_age_seconds=signal_age_seconds,
        fill_status=fill_status,
        fill_ratio=0.0,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=0.0,
        requested_notional_usd=requested_notional,
        effective_notional_usd=0.0,
        gross_pnl_usd=0.0,
        entry_fee_usd=0.0,
        exit_fee_usd=0.0,
        fees_usd=0.0,
        slippage_usd=0.0,
        net_pnl_usd=0.0,
        max_drawdown_usd=0.0,
        failure_reasons=failure_reasons,
    )


def _applied_fee_rate(
    fee_schedule: ExchangeFeeSchedule,
    assumptions: ExecutionCostAssumptions,
) -> float:
    if assumptions.cost_model_mode == "base":
        return float(fee_schedule.taker_fee_rate)
    return max(float(fee_schedule.taker_fee_rate), float(assumptions.fee_rate_floor))


def _adverse_price(
    price: float,
    tick_size: float,
    *,
    direction: str,
    leg: Literal["entry", "exit"],
) -> float:
    is_short = direction.startswith("short")
    round_up = (leg == "entry" and not is_short) or (leg == "exit" and is_short)
    return _round_to_step(float(price), float(tick_size), round_up=round_up)


def _round_quantity_down(quantity: float, step: float) -> float:
    return _round_to_step(float(quantity), float(step), round_up=False)


def _round_to_step(value: float, step: float, *, round_up: bool) -> float:
    if step <= 0:
        return float(value)
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    rounding = ROUND_CEILING if round_up else ROUND_FLOOR
    rounded = (decimal_value / decimal_step).to_integral_value(rounding=rounding) * decimal_step
    return float(rounded)


def _signal_age(
    *,
    signal_timestamp: datetime,
    entry_timestamp: datetime,
    max_signal_age_seconds: float | None,
) -> tuple[float | None, StaleSignalStatus]:
    if max_signal_age_seconds is None:
        return None, "not_evaluated"
    age_seconds = max(0.0, (_coerce_utc(entry_timestamp) - _coerce_utc(signal_timestamp)).total_seconds())
    if age_seconds > max_signal_age_seconds:
        return age_seconds, "stale"
    return age_seconds, "fresh"


def _volume_capacity_usd(
    trade: ExecutionTradeSpec,
    *,
    entry_price: float,
    exit_price: float,
    participation_rate: float,
) -> float | None:
    capacities: list[float] = []
    if trade.entry_volume is not None:
        capacities.append(float(trade.entry_volume) * entry_price * participation_rate)
    if trade.exit_volume is not None:
        capacities.append(float(trade.exit_volume) * exit_price * participation_rate)
    if not capacities:
        return None
    return min(capacities)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _strip_nonblank(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("must be non-empty")
    return stripped


def _dedupe_nonempty_strings(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = _strip_nonblank(value)
        if stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return tuple(normalized)


_DEFAULT_FEE_SCHEDULES = {
    "binance": ExchangeFeeSchedule(
        venue="binance",
        fee_model_id="binance:public-maker-taker:conservative",
        maker_fee_rate=0.0002,
        taker_fee_rate=0.0005,
        source="https://www.binance.com/en/fee/futureFee",
    ),
    "okx": ExchangeFeeSchedule(
        venue="okx",
        fee_model_id="okx:public-maker-taker:conservative",
        maker_fee_rate=0.0002,
        taker_fee_rate=0.0005,
    ),
    "bybit": ExchangeFeeSchedule(
        venue="bybit",
        fee_model_id="bybit:public-maker-taker:conservative",
        maker_fee_rate=0.0002,
        taker_fee_rate=0.00055,
    ),
}

_DEFAULT_CONSTRAINTS = {
    ("binance", "BTC/USDT:USDT"): SymbolMarketConstraints(
        venue="binance",
        symbol="BTC/USDT:USDT",
        min_notional_usd=5.0,
        min_quantity=0.001,
        quantity_step=0.001,
        tick_size=0.1,
        source="https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information",
    ),
    ("binance", "ETH/USDT:USDT"): SymbolMarketConstraints(
        venue="binance",
        symbol="ETH/USDT:USDT",
        min_notional_usd=5.0,
        min_quantity=0.001,
        quantity_step=0.001,
        tick_size=0.01,
        source="https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information",
    ),
    ("binance", "BTC/USDT"): SymbolMarketConstraints(
        venue="binance",
        symbol="BTC/USDT",
        min_notional_usd=5.0,
        min_quantity=0.00001,
        quantity_step=0.00001,
        tick_size=0.01,
        source="https://developers.binance.com/docs/binance-spot-api-docs/filters",
    ),
}


__all__ = [
    "ExchangeFeeSchedule",
    "ExecutionCostAssumptions",
    "ExecutionCostEstimate",
    "ExecutionTradeSpec",
    "SymbolMarketConstraints",
    "default_fee_schedule",
    "default_symbol_constraints",
    "estimate_execution_cost",
]
