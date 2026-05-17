from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from crypto_alpha_agent.strategy.models import StrategyValidationReport
from crypto_alpha_agent.validation.funding_price import (
    FundingPriceValidationResult,
    validate_funding_price_confirmation,
    validate_funding_price_confirmation_from_records,
)

STRATEGY_FAMILY = "funding_mean_reversion_after_extreme"
VALIDATOR_NAME = "funding_mean_reversion"
MISSING_OI_NOTE = "missing_open_interest_confirmation"


def validate_funding_mean_reversion(
    db_path: str | Path,
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
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
) -> StrategyValidationReport:
    result = validate_funding_price_confirmation(
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
    return funding_mean_reversion_report_from_result(
        result,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )


def validate_funding_mean_reversion_from_records(
    records: Sequence[Mapping[str, object]],
    *,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
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
) -> StrategyValidationReport:
    result = validate_funding_price_confirmation_from_records(
        records,
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
    return funding_mean_reversion_report_from_result(
        result,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )


def funding_mean_reversion_report_from_result(
    result: FundingPriceValidationResult,
    *,
    fee_rate: float,
    slippage_rate: float,
) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=STRATEGY_FAMILY,
        validator_name=VALIDATOR_NAME,
        approved=result.approved,
        blocked_reasons=result.blocked_reasons,
        metrics={
            "symbol": result.symbol,
            "funding_symbol": result.funding_symbol,
            "timeframe": result.timeframe,
            "bar_count": result.bar_count,
            "funding_sample_count": result.funding_sample_count,
            "extreme_count": result.extreme_count,
            "trade_count": result.trade_count,
            "gross_expectancy": result.gross_expectancy,
            "net_return": result.net_return,
            "max_drawdown": result.max_drawdown,
            "fee_adjusted_expectancy": result.fee_adjusted_expectancy,
            "slippage_adjusted_expectancy": result.slippage_adjusted_expectancy,
            "walk_forward_split_count": result.walk_forward_split_count,
            "walk_forward_pass_rate": result.walk_forward_pass_rate,
            "fee_rate": float(fee_rate),
            "slippage_rate": float(slippage_rate),
            "notes": [MISSING_OI_NOTE],
        },
    )
