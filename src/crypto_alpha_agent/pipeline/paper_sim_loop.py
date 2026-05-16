from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import FundingRateRecord
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.validation.funding_price import (
    FundingPriceTrade,
    FundingPriceValidationResult,
    _has_duplicate_timestamps,
    _has_non_positive_trade_price,
    _load_funding_history,
    extract_funding_price_trades,
    validate_funding_price_confirmation,
)
from crypto_alpha_agent.validation.market_history import CandleBar, load_candle_history

SUPPORTED_STRATEGY_FAMILY = "funding_extremity_price_confirmation"
_BLOCKED_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)


class PaperSimLoopReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    run_id: str = Field(min_length=1)
    db_path: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    price_symbol: str = Field(min_length=1)
    funding_symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    current_capital_usd: float = Field(ge=0)
    notional_usd: float = Field(ge=0)
    validation: FundingPriceValidationResult
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
) -> PaperSimLoopReport:
    if strategy_family != SUPPORTED_STRATEGY_FAMILY:
        raise ValueError(f"unsupported strategy_family: {strategy_family}")

    capital = _require_non_negative_finite("current_capital_usd", current_capital_usd)
    requested_notional = _require_non_negative_finite("notional_usd", notional_usd)
    capped_notional = min(requested_notional, capital, 25.0)
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
        min_trades=min_trades,
        require_walk_forward=require_walk_forward,
    )

    validation = validate_funding_price_confirmation(
        db_path,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
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
    )

    bars = load_candle_history(db_path, symbol=price_symbol, timeframe=timeframe)
    funding_rates = _load_funding_history(db_path, funding_symbol=funding_symbol)
    extremes = [
        funding
        for funding in funding_rates
        if abs(float(funding.funding_rate)) >= threshold_abs
    ]
    duplicate_price_timestamp = _has_duplicate_timestamps(bars)
    duplicate_funding_timestamp = _has_duplicate_timestamps(funding_rates)
    non_positive_price = False
    if not duplicate_price_timestamp and not duplicate_funding_timestamp:
        non_positive_price = _has_non_positive_trade_price(
            bars,
            extremes,
            hold_bars=hold_bars,
        )

    trades: list[FundingPriceTrade] = []
    if (
        not duplicate_price_timestamp
        and not duplicate_funding_timestamp
        and not non_positive_price
    ):
        trades = extract_funding_price_trades(
            bars,
            funding_rates,
            threshold_abs=threshold_abs,
            hold_bars=hold_bars,
        )

    outcomes = _closed_outcomes(
        run_id=resolved_run_id,
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
    )
    if not outcomes:
        outcomes = [
            _blocked_no_signal_outcome(
                run_id=resolved_run_id,
                strategy_family=strategy_family,
                symbol=price_symbol,
                observed_at=_latest_observed_at(bars, funding_rates),
                failure_reasons=("no_signal", *validation.blocked_reasons),
            )
        ]

    PaperOutcomeLedger(db_path).upsert_outcomes(outcomes)
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
        current_capital_usd=capital,
        notional_usd=capped_notional,
        validation=validation,
        outcome_count=len(outcomes),
        outcomes=outcomes,
        paper_evidence_packages=evidence_packages,
        notes=_report_notes(
            validation=validation,
            requested_notional=requested_notional,
            capped_notional=capped_notional,
            outcomes=outcomes,
        ),
    )


def _closed_outcomes(
    *,
    run_id: str,
    strategy_family: str,
    symbol: str,
    funding_symbol: str,
    timeframe: str,
    trades: list[FundingPriceTrade],
    notional_usd: float,
    threshold_abs: float,
    hold_bars: int,
    fee_rate: float,
    slippage_rate: float,
) -> list[PaperSimulationOutcome]:
    outcomes: list[PaperSimulationOutcome] = []
    for trade in trades:
        entry_price = trade.entry_price
        exit_price = trade.exit_price
        candidate_id = _stable_candidate_id(
            strategy_family,
            trade,
            price_symbol=symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            threshold_abs=threshold_abs,
            hold_bars=hold_bars,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
        )
        gross_pnl = notional_usd * trade.raw_return
        fees = notional_usd * float(fee_rate) * 2.0
        slippage = notional_usd * float(slippage_rate) * 2.0
        net_pnl = gross_pnl - fees - slippage
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
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=notional_usd / entry_price if entry_price > 0 else 0.0,
                notional_usd=notional_usd,
                gross_pnl_usd=float(gross_pnl),
                fees_usd=float(fees),
                slippage_usd=float(slippage),
                net_pnl_usd=float(net_pnl),
                max_drawdown_usd=max(0.0, -float(net_pnl)),
            )
        )
    return outcomes


def _blocked_no_signal_outcome(
    *,
    run_id: str,
    strategy_family: str,
    symbol: str,
    observed_at: datetime,
    failure_reasons: Iterable[str],
) -> PaperSimulationOutcome:
    return PaperSimulationOutcome(
        outcome_id=f"{run_id}:blocked:no_signal",
        run_id=run_id,
        candidate_id="no_signal",
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
    )


def _paper_evidence_mapping(outcome: PaperSimulationOutcome) -> dict[str, object]:
    return {
        "strategy_family": outcome.strategy_family,
        "trade_id": outcome.outcome_id,
        "symbol": outcome.symbol,
        "status": outcome.status,
        "realized_net_pnl": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _stable_run_id(**values: object) -> str:
    digest = _stable_digest(values)
    return f"paper-sim-{digest}"


def _stable_candidate_id(
    strategy_family: str,
    trade: FundingPriceTrade,
    *,
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


def _latest_observed_at(
    bars: list[CandleBar],
    funding_rates: list[FundingRateRecord],
) -> datetime:
    observed = [bar.timestamp for bar in bars]
    observed.extend(funding.timestamp for funding in funding_rates)
    return max(observed) if observed else _BLOCKED_TIMESTAMP


def _require_non_negative_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be finite and non-negative")
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric_value


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
    validation: FundingPriceValidationResult,
    requested_notional: float,
    capped_notional: float,
    outcomes: list[PaperSimulationOutcome],
) -> list[str]:
    notes = [
        "paper_simulation_only",
        "no_real_capital_touched",
        "no_live_order_routing",
    ]
    if capped_notional < requested_notional:
        notes.append("notional_capped")
    if not validation.approved:
        notes.append("validation_not_approved")
    if any(outcome.status == "blocked" for outcome in outcomes):
        notes.append("blocked_no_signal")
    return notes
