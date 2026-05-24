from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.execution.cost_model import (
    ExecutionCostAssumptions,
    ExecutionCostEstimate,
    ExecutionTradeSpec,
    SymbolMarketConstraints,
    default_fee_schedule,
    default_symbol_constraints,
    estimate_execution_cost,
)
from crypto_alpha_agent.strategy.models import (
    StrategyPaperReport,
    StrategyPaperRequest,
    StrategyValidationReport,
)
from crypto_alpha_agent.strategy.registry import default_strategy_registry

_BLOCKED_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)
_PAPER_REPORT_METRICS_INVALID = "paper_report_metrics_invalid"


class PaperSimLoopReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    run_id: str = Field(min_length=1)
    db_path: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    price_symbol: str = Field(min_length=1)
    funding_symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    venue: str = Field(default="binance", min_length=1)
    cost_model_mode: Literal["base", "pessimistic"] = "pessimistic"
    current_capital_usd: float = Field(ge=0)
    notional_usd: float = Field(ge=0)
    max_notional_usd: float = Field(default=25.0, gt=0)
    max_signal_age_seconds: float | None = Field(default=3600.0, ge=0)
    validation: StrategyValidationReport
    outcome_count: int = Field(ge=0)
    outcomes: list[PaperSimulationOutcome]
    paper_evidence_packages: list[PaperEvidencePackage]
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False
    notes: list[str] = Field(default_factory=list)


def run_paper_sim_loop(
    db_path: str | Path,
    *,
    strategy_family: str,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    run_id: str | None = None,
    current_capital_usd: float = 300.0,
    notional_usd: float = 25.0,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    min_trades: int = 3,
    require_walk_forward: bool = True,
    walk_forward_train_size: int = 24,
    walk_forward_test_size: int = 8,
    walk_forward_min_splits: int = 3,
    walk_forward_min_pass_rate: float = 1.0,
    max_drawdown_limit: float = 0.20,
    now: datetime | None = None,
    max_age_hours: float | None = None,
    venue: str = "binance",
    cost_model_mode: Literal["base", "pessimistic"] = "pessimistic",
    max_notional_usd: float = 25.0,
    max_signal_age_seconds: float | None = 3600.0,
    min_notional_usd: float | None = None,
    min_quantity: float | None = None,
    quantity_step: float | None = None,
    tick_size: float | None = None,
    max_volume_participation_rate: float = 0.05,
    allow_partial_fills: bool = False,
    observed_at_start: datetime | None = None,
    observed_at_end: datetime | None = None,
    persist_outcomes: bool = True,
) -> PaperSimLoopReport:
    capital = _require_non_negative_finite("current_capital_usd", current_capital_usd)
    requested_notional = _require_non_negative_finite("notional_usd", notional_usd)
    owner_max_notional = _require_positive_finite("max_notional_usd", max_notional_usd)
    if owner_max_notional > 25.0:
        raise ValueError("max_notional_usd cannot exceed the current owner profile limit of 25")
    _validate_optional_positive("max_signal_age_seconds", max_signal_age_seconds)
    _validate_optional_non_negative("min_notional_usd", min_notional_usd)
    _validate_optional_non_negative("min_quantity", min_quantity)
    _validate_optional_non_negative("quantity_step", quantity_step)
    _validate_optional_non_negative("tick_size", tick_size)
    _require_positive_finite("max_volume_participation_rate", max_volume_participation_rate)
    capped_notional = min(requested_notional, capital, owner_max_notional)
    execution_symbol = funding_symbol if ":" in funding_symbol else price_symbol
    cost_assumptions = _cost_assumptions(
        venue=venue,
        execution_symbol=execution_symbol,
        cost_model_mode=cost_model_mode,
        max_notional_usd=owner_max_notional,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        max_signal_age_seconds=max_signal_age_seconds,
        min_notional_usd=min_notional_usd,
        min_quantity=min_quantity,
        quantity_step=quantity_step,
        tick_size=tick_size,
        max_volume_participation_rate=max_volume_participation_rate,
        allow_partial_fills=allow_partial_fills,
    )
    resolved_run_id = run_id or _stable_run_id(
        strategy_family=strategy_family,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        current_capital_usd=capital,
        requested_notional_usd=requested_notional,
        capped_notional_usd=capped_notional,
        max_notional_usd=owner_max_notional,
        min_trades=min_trades,
        require_walk_forward=require_walk_forward,
        max_drawdown_limit=max_drawdown_limit,
        max_age_hours=max_age_hours,
        now=now.isoformat() if now is not None else None,
        venue=venue,
        cost_model_mode=cost_model_mode,
        max_signal_age_seconds=max_signal_age_seconds,
        min_notional_usd=min_notional_usd,
        min_quantity=min_quantity,
        quantity_step=quantity_step,
        tick_size=tick_size,
        max_volume_participation_rate=max_volume_participation_rate,
        allow_partial_fills=allow_partial_fills,
        observed_at_start=observed_at_start.isoformat() if observed_at_start is not None else None,
        observed_at_end=observed_at_end.isoformat() if observed_at_end is not None else None,
        persist_outcomes=persist_outcomes,
    )
    execution_config_id = _stable_execution_config_id(
        strategy_family=strategy_family,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        current_capital_usd=capital,
        requested_notional_usd=requested_notional,
        effective_notional_usd=capped_notional,
        max_notional_usd=owner_max_notional,
        threshold_abs=threshold_abs,
        hold_bars=hold_bars,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        min_trades=min_trades,
        require_walk_forward=require_walk_forward,
        walk_forward_train_size=walk_forward_train_size,
        walk_forward_test_size=walk_forward_test_size,
        walk_forward_min_splits=walk_forward_min_splits,
        walk_forward_min_pass_rate=walk_forward_min_pass_rate,
        max_drawdown_limit=max_drawdown_limit,
        max_age_hours=max_age_hours,
        now=now.isoformat() if now is not None else None,
        venue=venue,
        cost_model_mode=cost_model_mode,
        max_signal_age_seconds=max_signal_age_seconds,
        min_notional_usd=min_notional_usd,
        min_quantity=min_quantity,
        quantity_step=quantity_step,
        tick_size=tick_size,
        max_volume_participation_rate=max_volume_participation_rate,
        allow_partial_fills=allow_partial_fills,
        observed_at_start=observed_at_start.isoformat() if observed_at_start is not None else None,
        observed_at_end=observed_at_end.isoformat() if observed_at_end is not None else None,
        persist_outcomes=persist_outcomes,
    )

    strategy_parameters = {
        "price_symbol": price_symbol,
        "funding_symbol": funding_symbol,
        "timeframe": timeframe,
        "threshold_abs": threshold_abs,
        "hold_bars": hold_bars,
        "fee_rate": fee_rate,
        "slippage_rate": slippage_rate,
        "min_trades": min_trades,
        "require_walk_forward": require_walk_forward,
        "walk_forward_train_size": walk_forward_train_size,
        "walk_forward_test_size": walk_forward_test_size,
        "walk_forward_min_splits": walk_forward_min_splits,
        "walk_forward_min_pass_rate": walk_forward_min_pass_rate,
        "max_drawdown_limit": max_drawdown_limit,
    }
    if now is not None:
        strategy_parameters["now"] = now
    if max_age_hours is not None:
        strategy_parameters["max_age_hours"] = max_age_hours
    records = _load_strategy_records(
        db_path,
        observed_at_start=observed_at_start,
        observed_at_end=observed_at_end,
    )
    paper_report = default_strategy_registry(current_capital_usd=capital).run_paper(
        StrategyPaperRequest(
            strategy_family=strategy_family,
            records=records,
            current_capital_usd=capital,
            notional_usd=capped_notional,
            parameters=strategy_parameters,
        )
    )
    if "unknown_strategy_family" in paper_report.blocked_reasons:
        raise ValueError(f"unsupported strategy_family: {strategy_family}")

    if paper_report.status != "simulated":
        validation, observed_at = _safe_blocked_validation_context(
            strategy_family,
            paper_report,
            records,
        )
        outcomes = [
            _blocked_validation_outcome(
                run_id=resolved_run_id,
                execution_config_id=execution_config_id,
                strategy_family=strategy_family,
                symbol=price_symbol,
                observed_at=observed_at,
                failure_reasons=validation.blocked_reasons,
                cost_assumptions=cost_assumptions,
            )
        ]
    else:
        outcomes = []
        try:
            validation = _validation_from_paper_report(strategy_family, paper_report)
            trades = _paper_trades_from_report(paper_report)
            observed_at = _observed_at_from_paper_report(paper_report, records)
        except (TypeError, ValueError) as exc:
            validation = _metrics_invalid_validation(strategy_family, paper_report, exc)
            observed_at = _latest_observed_at_from_records(records)
            outcomes = [
                _blocked_validation_outcome(
                    run_id=resolved_run_id,
                    execution_config_id=execution_config_id,
                    strategy_family=strategy_family,
                    symbol=price_symbol,
                    observed_at=observed_at,
                    failure_reasons=validation.blocked_reasons,
                    cost_assumptions=cost_assumptions,
                )
            ]
            trades = []

        if not outcomes:
            if not trades:
                outcomes = [
                    _blocked_no_signal_outcome(
                        run_id=resolved_run_id,
                        execution_config_id=execution_config_id,
                        strategy_family=strategy_family,
                        symbol=price_symbol,
                        observed_at=observed_at,
                        failure_reasons=("no_signal", *validation.blocked_reasons),
                        cost_assumptions=cost_assumptions,
                    )
                ]
            elif not validation.approved:
                outcomes = [
                    _blocked_validation_outcome(
                        run_id=resolved_run_id,
                        execution_config_id=execution_config_id,
                        strategy_family=strategy_family,
                        symbol=price_symbol,
                        observed_at=observed_at,
                        failure_reasons=validation.blocked_reasons,
                        cost_assumptions=cost_assumptions,
                    )
                ]
            else:
                outcomes = _closed_outcomes(
                    run_id=resolved_run_id,
                    execution_config_id=execution_config_id,
                    strategy_family=strategy_family,
                    symbol=price_symbol,
                    funding_symbol=funding_symbol,
                    timeframe=timeframe,
                    trades=trades,
                    notional_usd=capped_notional,
                    threshold_abs=threshold_abs,
                    hold_bars=hold_bars,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    cost_assumptions=cost_assumptions,
                )

    if persist_outcomes:
        PaperOutcomeLedger(db_path).replace_run_outcomes(resolved_run_id, outcomes)
    evidence_packages = aggregate_paper_evidence(
        [_paper_evidence_mapping(outcome) for outcome in outcomes],
        strategy_family=strategy_family,
    )

    return PaperSimLoopReport(
        run_id=resolved_run_id,
        db_path=str(db_path),
        strategy_family=strategy_family,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        venue=venue,
        cost_model_mode=cost_model_mode,
        current_capital_usd=capital,
        notional_usd=capped_notional,
        max_notional_usd=owner_max_notional,
        max_signal_age_seconds=max_signal_age_seconds,
        validation=validation,
        outcome_count=len(outcomes),
        outcomes=outcomes,
        paper_evidence_packages=evidence_packages,
        notes=_report_notes(
            validation=validation,
            requested_notional=requested_notional,
            capped_notional=capped_notional,
            outcomes=outcomes,
            cost_model_mode=cost_model_mode,
        ),
    )


@dataclass(frozen=True, slots=True)
class _PaperTrade:
    funding_symbol: str
    funding_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: float
    exit_price: float
    raw_return: float
    direction: str
    entry_volume: float | None = None
    exit_volume: float | None = None
    next_funding_at: datetime | None = None


def _closed_outcomes(
    *,
    run_id: str,
    execution_config_id: str,
    strategy_family: str,
    symbol: str,
    funding_symbol: str,
    timeframe: str,
    trades: list[_PaperTrade],
    notional_usd: float,
    threshold_abs: float,
    hold_bars: int,
    fee_rate: float,
    slippage_rate: float,
    cost_assumptions: ExecutionCostAssumptions,
) -> list[PaperSimulationOutcome]:
    outcomes: list[PaperSimulationOutcome] = []
    for trade in trades:
        estimate = estimate_execution_cost(
            _execution_trade_spec(
                trade,
                symbol=funding_symbol if ":" in funding_symbol else symbol,
                venue=cost_assumptions.venue,
                notional_usd=notional_usd,
            ),
            cost_assumptions,
        )
        candidate_id = _stable_candidate_id(
            strategy_family,
            trade,
            execution_config_id=execution_config_id,
            price_symbol=symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            threshold_abs=threshold_abs,
            hold_bars=hold_bars,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )
        if estimate.status == "blocked":
            outcomes.append(
                _blocked_execution_outcome(
                    run_id=run_id,
                    candidate_id=candidate_id,
                    strategy_family=strategy_family,
                    symbol=symbol,
                    observed_at=trade.exit_timestamp,
                    signal_timestamp=trade.funding_timestamp,
                    estimate=estimate,
                )
            )
            continue
        outcomes.append(
            PaperSimulationOutcome(
                outcome_id=f"{run_id}:{candidate_id}",
                run_id=run_id,
                candidate_id=candidate_id,
                strategy_family=strategy_family,
                symbol=symbol,
                observed_at=trade.exit_timestamp,
                status="closed",
                signal_timestamp=trade.funding_timestamp,
                entry_price=estimate.entry_price,
                exit_price=estimate.exit_price,
                quantity=estimate.quantity,
                notional_usd=estimate.effective_notional_usd,
                gross_pnl_usd=estimate.gross_pnl_usd,
                fees_usd=estimate.fees_usd,
                slippage_usd=estimate.slippage_usd,
                net_pnl_usd=estimate.net_pnl_usd,
                max_drawdown_usd=estimate.max_drawdown_usd,
                venue=estimate.venue,
                cost_model_mode=estimate.cost_model_mode,
                fee_model_id=estimate.fee_model_id,
                maker_fee_rate=estimate.maker_fee_rate,
                taker_fee_rate=estimate.taker_fee_rate,
                applied_entry_fee_rate=estimate.applied_entry_fee_rate,
                applied_exit_fee_rate=estimate.applied_exit_fee_rate,
                entry_fee_usd=estimate.entry_fee_usd,
                exit_fee_usd=estimate.exit_fee_usd,
                slippage_bps=estimate.slippage_bps,
                stale_signal_status=estimate.stale_signal_status,
                signal_age_seconds=estimate.signal_age_seconds,
                fill_status=estimate.fill_status,
                fill_ratio=estimate.fill_ratio,
            )
        )
    return outcomes


def _execution_trade_spec(
    trade: _PaperTrade,
    *,
    symbol: str,
    venue: str,
    notional_usd: float,
) -> ExecutionTradeSpec:
    return ExecutionTradeSpec(
        symbol=symbol,
        venue=venue,
        direction=trade.direction,
        signal_timestamp=trade.funding_timestamp,
        entry_timestamp=trade.entry_timestamp,
        exit_timestamp=trade.exit_timestamp,
        entry_reference_price=trade.entry_price,
        exit_reference_price=trade.exit_price,
        raw_return=trade.raw_return,
        requested_notional_usd=notional_usd,
        entry_volume=trade.entry_volume,
        exit_volume=trade.exit_volume,
        next_funding_at=trade.next_funding_at,
    )


def _blocked_execution_outcome(
    *,
    run_id: str,
    candidate_id: str,
    strategy_family: str,
    symbol: str,
    observed_at: datetime,
    signal_timestamp: datetime,
    estimate: ExecutionCostEstimate,
) -> PaperSimulationOutcome:
    return PaperSimulationOutcome(
        outcome_id=f"{run_id}:{candidate_id}",
        run_id=run_id,
        candidate_id=candidate_id,
        strategy_family=strategy_family,
        symbol=symbol,
        observed_at=observed_at,
        status="blocked",
        signal_timestamp=signal_timestamp,
        entry_price=estimate.entry_price,
        exit_price=estimate.exit_price,
        quantity=estimate.quantity,
        notional_usd=estimate.effective_notional_usd,
        gross_pnl_usd=estimate.gross_pnl_usd,
        fees_usd=estimate.fees_usd,
        slippage_usd=estimate.slippage_usd,
        net_pnl_usd=estimate.net_pnl_usd,
        max_drawdown_usd=estimate.max_drawdown_usd,
        failure_reasons=estimate.failure_reasons,
        venue=estimate.venue,
        cost_model_mode=estimate.cost_model_mode,
        fee_model_id=estimate.fee_model_id,
        maker_fee_rate=estimate.maker_fee_rate,
        taker_fee_rate=estimate.taker_fee_rate,
        applied_entry_fee_rate=estimate.applied_entry_fee_rate,
        applied_exit_fee_rate=estimate.applied_exit_fee_rate,
        entry_fee_usd=estimate.entry_fee_usd,
        exit_fee_usd=estimate.exit_fee_usd,
        slippage_bps=estimate.slippage_bps,
        stale_signal_status=estimate.stale_signal_status,
        signal_age_seconds=estimate.signal_age_seconds,
        fill_status=estimate.fill_status,
        fill_ratio=estimate.fill_ratio,
    )


def _blocked_validation_outcome(
    *,
    run_id: str,
    execution_config_id: str,
    strategy_family: str,
    symbol: str,
    observed_at: datetime,
    failure_reasons: Iterable[str],
    cost_assumptions: ExecutionCostAssumptions,
) -> PaperSimulationOutcome:
    reasons = _dedupe_strings(failure_reasons) or ["validation_not_approved"]
    return PaperSimulationOutcome(
        outcome_id=f"{run_id}:blocked:validation:{execution_config_id}",
        run_id=run_id,
        candidate_id=f"validation_blocked:{execution_config_id}",
        strategy_family=strategy_family,
        symbol=symbol,
        observed_at=observed_at,
        status="blocked",
        signal_timestamp=observed_at,
        entry_price=0.0,
        exit_price=0.0,
        quantity=0.0,
        notional_usd=0.0,
        gross_pnl_usd=0.0,
        fees_usd=0.0,
        slippage_usd=0.0,
        net_pnl_usd=0.0,
        max_drawdown_usd=0.0,
        failure_reasons=reasons,
        **_blocked_outcome_execution_metadata(cost_assumptions),
    )


def _blocked_no_signal_outcome(
    *,
    run_id: str,
    execution_config_id: str,
    strategy_family: str,
    symbol: str,
    observed_at: datetime,
    failure_reasons: Iterable[str],
    cost_assumptions: ExecutionCostAssumptions,
) -> PaperSimulationOutcome:
    return PaperSimulationOutcome(
        outcome_id=f"{run_id}:blocked:no_signal:{execution_config_id}",
        run_id=run_id,
        candidate_id=f"no_signal:{execution_config_id}",
        strategy_family=strategy_family,
        symbol=symbol,
        observed_at=observed_at,
        status="blocked",
        signal_timestamp=observed_at,
        entry_price=0.0,
        exit_price=0.0,
        quantity=0.0,
        notional_usd=0.0,
        gross_pnl_usd=0.0,
        fees_usd=0.0,
        slippage_usd=0.0,
        net_pnl_usd=0.0,
        max_drawdown_usd=0.0,
        failure_reasons=_dedupe_strings(failure_reasons),
        **_blocked_outcome_execution_metadata(cost_assumptions),
    )


def _blocked_outcome_execution_metadata(
    cost_assumptions: ExecutionCostAssumptions,
) -> dict[str, object]:
    fee_schedule = cost_assumptions.fee_schedule or default_fee_schedule(cost_assumptions.venue)
    applied_fee_rate = float(fee_schedule.taker_fee_rate)
    if cost_assumptions.cost_model_mode == "pessimistic":
        applied_fee_rate = max(applied_fee_rate, float(cost_assumptions.fee_rate_floor))
    return {
        "venue": cost_assumptions.venue,
        "cost_model_mode": cost_assumptions.cost_model_mode,
        "fee_model_id": fee_schedule.fee_model_id,
        "maker_fee_rate": fee_schedule.maker_fee_rate,
        "taker_fee_rate": fee_schedule.taker_fee_rate,
        "applied_entry_fee_rate": applied_fee_rate,
        "applied_exit_fee_rate": applied_fee_rate,
        "slippage_bps": cost_assumptions.fixed_slippage_bps,
        "stale_signal_status": "not_evaluated",
        "signal_age_seconds": None,
        "fill_status": "blocked",
        "fill_ratio": 0.0,
    }


def _paper_evidence_mapping(outcome: PaperSimulationOutcome) -> dict[str, object]:
    return {
        "strategy_family": outcome.strategy_family,
        "trade_id": outcome.outcome_id,
        "symbol": outcome.symbol,
        "status": outcome.status,
        "realized_net_pnl": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "notional_usd": outcome.notional_usd,
        "gross_pnl_usd": outcome.gross_pnl_usd,
        "fees_usd": outcome.fees_usd,
        "slippage_usd": outcome.slippage_usd,
        "cost_model_mode": outcome.cost_model_mode,
        "stale_signal_status": outcome.stale_signal_status,
        "fill_status": outcome.fill_status,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _load_strategy_records(
    db_path: str | Path,
    *,
    observed_at_start: datetime | None = None,
    observed_at_end: datetime | None = None,
) -> tuple[dict[str, object], ...]:
    return tuple(
        record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records(
            observed_at_start=observed_at_start,
            observed_at_end=observed_at_end,
        )
    )


def _stable_run_id(**values: object) -> str:
    digest = _stable_digest(values)
    return f"paper-sim-{digest}"


def _stable_execution_config_id(**values: object) -> str:
    digest = _stable_digest(values)
    return f"exec-{digest}"


def _stable_candidate_id(
    strategy_family: str,
    trade: _PaperTrade,
    *,
    execution_config_id: str,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
    threshold_abs: float,
    hold_bars: int,
    fee_rate: float,
    slippage_rate: float,
) -> str:
    digest = _stable_digest(
        {
            "strategy_family": strategy_family,
            "execution_config_id": execution_config_id,
            "price_symbol": price_symbol,
            "funding_symbol": funding_symbol,
            "timeframe": timeframe,
            "funding_timestamp": trade.funding_timestamp.isoformat(),
            "entry_timestamp": trade.entry_timestamp.isoformat(),
            "exit_timestamp": trade.exit_timestamp.isoformat(),
            "hold_bars": hold_bars,
            "threshold_abs": float(threshold_abs),
            "fee_rate": float(fee_rate),
            "slippage_rate": float(slippage_rate),
        }
    )
    return f"candidate-{digest}"


def _stable_digest(values: dict[str, object]) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _require_non_negative_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be finite and non-negative")
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric_value


def _require_positive_finite(name: str, value: float) -> float:
    numeric_value = _require_non_negative_finite(name, value)
    if numeric_value <= 0:
        raise ValueError(f"{name} must be finite and greater than 0")
    return numeric_value


def _validate_optional_non_negative(name: str, value: float | None) -> None:
    if value is None:
        return
    _require_non_negative_finite(name, value)


def _validate_optional_positive(name: str, value: float | None) -> None:
    if value is None:
        return
    _require_positive_finite(name, value)


def _cost_assumptions(
    *,
    venue: str,
    execution_symbol: str,
    cost_model_mode: Literal["base", "pessimistic"],
    max_notional_usd: float,
    fee_rate: float,
    slippage_rate: float,
    max_signal_age_seconds: float | None,
    min_notional_usd: float | None,
    min_quantity: float | None,
    quantity_step: float | None,
    tick_size: float | None,
    max_volume_participation_rate: float,
    allow_partial_fills: bool,
) -> ExecutionCostAssumptions:
    base_constraints = default_symbol_constraints(venue, execution_symbol)
    constraint_payload = base_constraints.model_dump()
    if min_notional_usd is not None:
        constraint_payload["min_notional_usd"] = min_notional_usd
    if min_quantity is not None:
        constraint_payload["min_quantity"] = min_quantity
    if quantity_step is not None:
        constraint_payload["quantity_step"] = quantity_step
    if tick_size is not None:
        constraint_payload["tick_size"] = tick_size

    return ExecutionCostAssumptions(
        venue=venue,
        cost_model_mode=cost_model_mode,
        max_notional_usd=max_notional_usd,
        fee_rate_floor=float(fee_rate),
        fixed_slippage_bps=float(slippage_rate) * 10_000.0,
        max_signal_age_seconds=max_signal_age_seconds,
        max_volume_participation_rate=max_volume_participation_rate,
        allow_partial_fills=allow_partial_fills,
        symbol_constraints=SymbolMarketConstraints(**constraint_payload),
    )


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped


def _report_notes(
    *,
    validation: StrategyValidationReport,
    requested_notional: float,
    capped_notional: float,
    outcomes: list[PaperSimulationOutcome],
    cost_model_mode: str,
) -> list[str]:
    notes = [
        "paper_simulation_only",
        "no_real_capital_touched",
        "no_live_order_routing",
        f"cost_model_mode:{cost_model_mode}",
    ]
    if capped_notional < requested_notional:
        notes.append("notional_capped")
    if not validation.approved:
        notes.append("validation_not_approved")
        notes.extend(validation.blocked_reasons)
    validation_metrics = getattr(validation, "metrics", {})
    if isinstance(validation_metrics, dict):
        metric_notes = validation_metrics.get("notes", [])
        if isinstance(metric_notes, list | tuple):
            notes.extend(str(note) for note in metric_notes)
    if any(
        outcome.status == "blocked" and "no_signal" in outcome.failure_reasons
        for outcome in outcomes
    ):
        notes.append("blocked_no_signal")
    if any(
        outcome.status == "blocked" and "no_signal" not in outcome.failure_reasons
        for outcome in outcomes
    ):
        notes.append("blocked_validation")
    return _dedupe_strings(notes)


def _validation_from_paper_report(
    strategy_family: str,
    paper_report: StrategyPaperReport,
) -> StrategyValidationReport:
    validation_payload = paper_report.metrics.get("validation")
    if isinstance(validation_payload, Mapping):
        return StrategyValidationReport.model_validate(dict(validation_payload))

    return StrategyValidationReport(
        strategy_family=strategy_family,
        validator_name="strategy_registry_paper_gate",
        approved=False,
        blocked_reasons=paper_report.blocked_reasons,
        metrics={
            "paper_status": paper_report.status,
            "supports_paper_simulation": paper_report.supports_paper_simulation,
            "paper_metrics": paper_report.metrics,
        },
    )


def _safe_blocked_validation_context(
    strategy_family: str,
    paper_report: StrategyPaperReport,
    records: tuple[dict[str, object], ...],
) -> tuple[StrategyValidationReport, datetime]:
    try:
        return (
            _validation_from_paper_report(strategy_family, paper_report),
            _observed_at_from_paper_report(paper_report, records),
        )
    except (TypeError, ValueError) as exc:
        return (
            _metrics_invalid_validation(strategy_family, paper_report, exc),
            _latest_observed_at_from_records(records),
        )


def _metrics_invalid_validation(
    strategy_family: str,
    paper_report: StrategyPaperReport,
    exc: Exception,
) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=strategy_family,
        validator_name="strategy_registry_paper_gate",
        approved=False,
        blocked_reasons=[_PAPER_REPORT_METRICS_INVALID],
        metrics={
            "paper_status": paper_report.status,
            "supports_paper_simulation": paper_report.supports_paper_simulation,
            "metrics_error": str(exc),
        },
    )


def _paper_trades_from_report(paper_report: StrategyPaperReport) -> list[_PaperTrade]:
    trades_payload = paper_report.metrics.get("paper_trades", [])
    if not isinstance(trades_payload, list | tuple):
        raise ValueError("paper_report metrics.paper_trades must be a list")

    return [_paper_trade_from_mapping(item) for item in trades_payload]


def _paper_trade_from_mapping(value: object) -> _PaperTrade:
    if not isinstance(value, Mapping):
        raise ValueError("paper_report metrics.paper_trades items must be objects")

    return _PaperTrade(
        funding_symbol=_required_string(value, "funding_symbol"),
        funding_timestamp=_parse_timestamp(value.get("funding_timestamp")),
        entry_timestamp=_parse_timestamp(value.get("entry_timestamp")),
        exit_timestamp=_parse_timestamp(value.get("exit_timestamp")),
        entry_price=_required_positive_finite_float(value, "entry_price"),
        exit_price=_required_positive_finite_float(value, "exit_price"),
        raw_return=_required_finite_float(value, "raw_return"),
        direction=_required_string(value, "direction"),
        entry_volume=_optional_non_negative_finite_float(value.get("entry_volume"), "entry_volume"),
        exit_volume=_optional_non_negative_finite_float(value.get("exit_volume"), "exit_volume"),
        next_funding_at=_parse_optional_timestamp(value.get("next_funding_at")),
    )


def _observed_at_from_paper_report(
    paper_report: StrategyPaperReport,
    records: tuple[dict[str, object], ...],
) -> datetime:
    observed_at = paper_report.metrics.get("observed_at")
    if observed_at is not None:
        return _parse_timestamp(observed_at)
    return _latest_observed_at_from_records(records)


def _latest_observed_at_from_records(records: tuple[dict[str, object], ...]) -> datetime:
    observed: list[datetime] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        for value in (record.get("observed_at"), _payload_timestamp(record)):
            if value is None:
                continue
            try:
                observed.append(_parse_timestamp(value))
            except (TypeError, ValueError):
                continue
    return max(observed) if observed else _BLOCKED_TIMESTAMP


def _payload_timestamp(record: Mapping[str, object]) -> object | None:
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        return payload.get("timestamp")
    return None


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("timestamp must be a datetime or ISO string")
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp


def _parse_optional_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    return _parse_timestamp(value)


def _required_string(value: Mapping[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"paper trade {key} must be a non-empty string")
    return raw.strip()


def _required_finite_float(value: Mapping[str, object], key: str) -> float:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ValueError(f"paper trade {key} must be finite")
    numeric_value = float(raw)
    if not math.isfinite(numeric_value):
        raise ValueError(f"paper trade {key} must be finite")
    return numeric_value


def _required_positive_finite_float(value: Mapping[str, object], key: str) -> float:
    numeric_value = _required_finite_float(value, key)
    if numeric_value <= 0:
        raise ValueError(f"paper trade {key} must be finite and greater than 0")
    return numeric_value


def _optional_non_negative_finite_float(raw: object, key: str) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ValueError(f"paper trade {key} must be finite and non-negative")
    numeric_value = float(raw)
    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"paper trade {key} must be finite and non-negative")
    return numeric_value
