from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import math

from crypto_alpha_agent.strategy.models import (
    StrategyFamilySpec,
    StrategyPaperReport,
    StrategyPaperRequest,
    StrategyValidationReport,
    StrategyValidationRequest,
)
from crypto_alpha_agent.strategy.defi_yield_regime import (
    DEFAULT_MAX_AGE_HOURS,
    DEFAULT_MIN_APY_CHANGE,
    DEFAULT_MIN_OBSERVATIONS,
    DEFAULT_MIN_TVL_USD,
    DEFAULT_SUPPORTED_CHAINS,
    STRATEGY_FAMILY as DEFI_YIELD_REGIME_STRATEGY_FAMILY,
    validate_defi_yield_regime,
)
from crypto_alpha_agent.strategy.dex_liquidity_watchlist import (
    DEFAULT_MAX_AGE_HOURS as DEX_DEFAULT_MAX_AGE_HOURS,
    DEFAULT_MIN_LIQUIDITY_CHANGE_PCT,
    DEFAULT_MIN_LIQUIDITY_USD,
    DEFAULT_MIN_OBSERVATIONS as DEX_DEFAULT_MIN_OBSERVATIONS,
    DEFAULT_MIN_VOLUME_24H_USD,
    DEFAULT_MIN_VOLUME_CHANGE_PCT,
    DEFAULT_SUPPORTED_CHAINS as DEX_DEFAULT_SUPPORTED_CHAINS,
    STRATEGY_FAMILY as DEX_LIQUIDITY_WATCHLIST_STRATEGY_FAMILY,
    validate_dex_liquidity_watchlist,
)
from crypto_alpha_agent.strategy.funding_mean_reversion import (
    STRATEGY_FAMILY as FUNDING_MEAN_REVERSION_STRATEGY_FAMILY,
    validate_funding_mean_reversion_from_records,
)
from crypto_alpha_agent.strategy.funding_oi_crowding import (
    STRATEGY_FAMILY as FUNDING_OI_CROWDING_STRATEGY_FAMILY,
    extract_funding_oi_crowding_trades_from_records,
    validate_funding_oi_crowding_from_records,
)
from crypto_alpha_agent.strategy.volatility_regime_watchlist import (
    DEFAULT_COMPRESSION_WINDOW,
    DEFAULT_EXPANSION_WINDOW,
    DEFAULT_MAX_COMPRESSION_VOLATILITY,
    DEFAULT_MIN_EXPANSION_RETURN_ABS,
    DEFAULT_MIN_OBSERVATIONS as VOLATILITY_DEFAULT_MIN_OBSERVATIONS,
    DEFAULT_MIN_VOLUME_CHANGE_PCT as VOLATILITY_DEFAULT_MIN_VOLUME_CHANGE_PCT,
    DEFAULT_SUPPORTED_SYMBOLS as VOLATILITY_DEFAULT_SUPPORTED_SYMBOLS,
    STRATEGY_FAMILY as VOLATILITY_REGIME_WATCHLIST_STRATEGY_FAMILY,
    validate_volatility_regime_watchlist,
)
from crypto_alpha_agent.validation.funding_price import validate_funding_price_confirmation_from_records
from crypto_alpha_agent.validation.funding_price import (
    FundingPriceTrade,
    extract_funding_price_trades_from_records,
    latest_funding_price_observed_at_from_records,
)

StrategyValidator = Callable[[StrategyValidationRequest], StrategyValidationReport]
StrategyPaperRunner = Callable[[StrategyPaperRequest], StrategyPaperReport]

_PAPER_SENTINEL_OBSERVED_AT = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _StrategyRegistration:
    spec: StrategyFamilySpec
    validator: StrategyValidator
    paper_runner: StrategyPaperRunner | None


class StrategyRegistry:
    def __init__(self, *, current_capital_usd: float) -> None:
        if not math.isfinite(current_capital_usd):
            raise ValueError("current_capital_usd must be finite")
        if current_capital_usd < 0:
            raise ValueError("current_capital_usd must be non-negative")
        self._current_capital_usd = current_capital_usd
        self._registrations: dict[str, _StrategyRegistration] = {}

    def register(
        self,
        spec: StrategyFamilySpec,
        validator: StrategyValidator,
        paper_runner: StrategyPaperRunner | None = None,
    ) -> None:
        if spec.strategy_family in self._registrations:
            raise ValueError(f"strategy family already registered: {spec.strategy_family}")
        self._registrations[spec.strategy_family] = _StrategyRegistration(
            spec=spec,
            validator=validator,
            paper_runner=paper_runner,
        )

    def list_families(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def get(self, strategy_family: str) -> StrategyFamilySpec:
        try:
            return self._registrations[strategy_family].spec
        except KeyError as exc:
            raise KeyError(f"unknown strategy family: {strategy_family}") from exc

    def validate(self, request: StrategyValidationRequest) -> StrategyValidationReport:
        registration = self._registrations.get(request.strategy_family)
        if registration is None:
            return StrategyValidationReport(
                strategy_family=request.strategy_family,
                validator_name="unknown",
                approved=False,
                blocked_reasons=["unknown_strategy_family"],
                metrics={},
            )
        if registration.spec.blocked_reasons:
            return StrategyValidationReport(
                strategy_family=request.strategy_family,
                validator_name=registration.spec.validator_name,
                approved=False,
                blocked_reasons=registration.spec.blocked_reasons,
                metrics={},
            )
        if request.current_capital_usd < registration.spec.min_capital_usd:
            return StrategyValidationReport(
                strategy_family=request.strategy_family,
                validator_name=registration.spec.validator_name,
                approved=False,
                blocked_reasons=["insufficient_current_capital"],
                metrics={"min_capital_usd": registration.spec.min_capital_usd},
            )
        return registration.validator(request)

    def run_paper(self, request: StrategyPaperRequest) -> StrategyPaperReport:
        registration = self._registrations.get(request.strategy_family)
        if registration is None:
            return StrategyPaperReport(
                strategy_family=request.strategy_family,
                status="blocked",
                supports_paper_simulation=False,
                blocked_reasons=["unknown_strategy_family"],
                metrics={},
            )
        if registration.spec.blocked_reasons:
            return StrategyPaperReport(
                strategy_family=request.strategy_family,
                status="blocked",
                supports_paper_simulation=registration.spec.supports_paper_simulation,
                blocked_reasons=registration.spec.blocked_reasons,
                metrics={},
            )
        if request.current_capital_usd < registration.spec.min_capital_usd:
            return StrategyPaperReport(
                strategy_family=request.strategy_family,
                status="blocked",
                supports_paper_simulation=registration.spec.supports_paper_simulation,
                blocked_reasons=["insufficient_current_capital"],
                metrics={"min_capital_usd": registration.spec.min_capital_usd},
            )
        if not registration.spec.supports_paper_simulation:
            return StrategyPaperReport(
                strategy_family=request.strategy_family,
                status="unsupported",
                supports_paper_simulation=False,
                blocked_reasons=["paper_simulation_not_supported"],
                metrics={},
            )
        if registration.paper_runner is None:
            return StrategyPaperReport(
                strategy_family=request.strategy_family,
                status="unsupported",
                supports_paper_simulation=True,
                blocked_reasons=["paper_runner_not_registered"],
                metrics={},
            )
        if request.notional_usd > registration.spec.max_notional_usd:
            return StrategyPaperReport(
                strategy_family=request.strategy_family,
                status="blocked",
                supports_paper_simulation=True,
                blocked_reasons=["notional_exceeds_strategy_limit"],
                metrics={"max_notional_usd": registration.spec.max_notional_usd},
            )
        return registration.paper_runner(request)


def default_strategy_registry(*, current_capital_usd: float = 300.0) -> StrategyRegistry:
    registry = StrategyRegistry(current_capital_usd=current_capital_usd)
    funding_price_spec = StrategyFamilySpec(
        strategy_family=FUNDING_PRICE_STRATEGY_FAMILY,
        display_name="Funding Extremity With Price Confirmation",
        required_record_types=["market_candle", "funding_rate"],
        required_symbols=["BTC/USDT", "BTC/USDT:USDT"],
        supports_paper_simulation=True,
        min_capital_usd=25.0,
        max_notional_usd=25.0,
        validator_name="funding_price_confirmation",
        blocked_reasons=[],
        configured_capital_usd=max(current_capital_usd, 25.0),
    )
    registry.register(
        funding_price_spec,
        _funding_price_validator,
        paper_runner=_funding_price_paper_runner,
    )
    mean_reversion_spec = StrategyFamilySpec(
        strategy_family=FUNDING_MEAN_REVERSION_STRATEGY_FAMILY,
        display_name="Funding Mean Reversion After Extreme",
        required_record_types=["market_candle", "funding_rate"],
        required_symbols=["BTC/USDT", "BTC/USDT:USDT"],
        supports_paper_simulation=True,
        min_capital_usd=25.0,
        max_notional_usd=25.0,
        validator_name="funding_mean_reversion",
        blocked_reasons=[],
        configured_capital_usd=max(current_capital_usd, 25.0),
    )
    registry.register(
        mean_reversion_spec,
        _funding_mean_reversion_validator,
        paper_runner=_funding_mean_reversion_paper_runner,
    )
    funding_oi_crowding_spec = StrategyFamilySpec(
        strategy_family=FUNDING_OI_CROWDING_STRATEGY_FAMILY,
        display_name="Funding Crowding With Open Interest Confirmation",
        required_record_types=["market_candle", "funding_rate", "open_interest"],
        required_symbols=["BTC/USDT", "BTC/USDT:USDT"],
        supports_paper_simulation=True,
        min_capital_usd=25.0,
        max_notional_usd=25.0,
        validator_name="funding_oi_crowding",
        blocked_reasons=[],
        configured_capital_usd=max(current_capital_usd, 25.0),
    )
    registry.register(
        funding_oi_crowding_spec,
        _funding_oi_crowding_validator,
        paper_runner=_funding_oi_crowding_paper_runner,
    )
    defi_yield_regime_spec = StrategyFamilySpec(
        strategy_family=DEFI_YIELD_REGIME_STRATEGY_FAMILY,
        display_name="DefiLlama Yield Regime Watchlist",
        required_record_types=["defi_yield"],
        required_symbols=["*defi_yield"],
        execution_role="research_only",
        supports_paper_simulation=False,
        min_capital_usd=0.0,
        max_notional_usd=0.0,
        validator_name="defi_yield_regime",
        blocked_reasons=[],
        configured_capital_usd=current_capital_usd,
    )
    registry.register(defi_yield_regime_spec, _defi_yield_regime_validator)
    dex_liquidity_watchlist_spec = StrategyFamilySpec(
        strategy_family=DEX_LIQUIDITY_WATCHLIST_STRATEGY_FAMILY,
        display_name="DEX Liquidity And Volume Regime Watchlist",
        required_record_types=["dex_pair"],
        required_symbols=["*dex_pair"],
        execution_role="research_only",
        supports_paper_simulation=False,
        min_capital_usd=0.0,
        max_notional_usd=0.0,
        validator_name="dex_liquidity_watchlist",
        blocked_reasons=[],
        configured_capital_usd=current_capital_usd,
    )
    registry.register(dex_liquidity_watchlist_spec, _dex_liquidity_watchlist_validator)
    volatility_regime_watchlist_spec = StrategyFamilySpec(
        strategy_family=VOLATILITY_REGIME_WATCHLIST_STRATEGY_FAMILY,
        display_name="Volatility Compression And Expansion Watchlist",
        required_record_types=["market_candle"],
        required_symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        execution_role="research_only",
        supports_paper_simulation=False,
        min_capital_usd=0.0,
        max_notional_usd=0.0,
        validator_name="volatility_regime_watchlist",
        blocked_reasons=[],
        configured_capital_usd=current_capital_usd,
    )
    registry.register(
        volatility_regime_watchlist_spec,
        _volatility_regime_watchlist_validator,
    )
    return registry


FUNDING_PRICE_STRATEGY_FAMILY = "funding_extremity_price_confirmation"


def _funding_price_validator(request: StrategyValidationRequest) -> StrategyValidationReport:
    parameters = request.parameters
    price_symbol = _nonblank_parameter(parameters, "price_symbol")
    funding_symbol = _nonblank_parameter(parameters, "funding_symbol")
    timeframe = _nonblank_parameter(parameters, "timeframe")
    missing_parameters = [
        name
        for name, value in (
            ("price_symbol", price_symbol),
            ("funding_symbol", funding_symbol),
            ("timeframe", timeframe),
        )
        if value is None
    ]
    if missing_parameters:
        return _blocked_funding_price_report(
            request,
            blocked_reasons=["missing_strategy_validation_parameters"],
            metrics={"missing_parameters": missing_parameters},
        )
    try:
        result = validate_funding_price_confirmation_from_records(
            request.records,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            threshold_abs=float(parameters.get("threshold_abs", 0.0005)),
            hold_bars=int(parameters.get("hold_bars", 1)),
            fee_rate=float(parameters.get("fee_rate", 0.001)),
            slippage_rate=float(parameters.get("slippage_rate", 0.0005)),
            min_trades=int(parameters.get("min_trades", 3)),
            require_walk_forward=bool(parameters.get("require_walk_forward", True)),
            walk_forward_train_size=int(parameters.get("walk_forward_train_size", 24)),
            walk_forward_test_size=int(parameters.get("walk_forward_test_size", 8)),
            walk_forward_min_splits=int(parameters.get("walk_forward_min_splits", 3)),
            walk_forward_min_pass_rate=float(
                parameters.get("walk_forward_min_pass_rate", 1.0)
            ),
            max_drawdown_limit=_strict_non_negative_float_parameter(
                parameters,
                "max_drawdown_limit",
                0.20,
            ),
            now=_optional_datetime_parameter(parameters, "now"),
            max_age_hours=_optional_positive_float_parameter(
                parameters,
                "max_age_hours",
            ),
            supported_price_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_price_symbols",
                default=("BTC/USDT",),
            ),
            supported_funding_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_funding_symbols",
                default=("BTC/USDT:USDT",),
            ),
        )
    except (OverflowError, TypeError, ValueError) as exc:
        return _blocked_funding_price_report(
            request,
            blocked_reasons=["strategy_validation_error"],
            metrics={
                "symbol": price_symbol,
                "funding_symbol": funding_symbol,
                "timeframe": timeframe,
                "validation_error": str(exc),
            },
        )
    return StrategyValidationReport(
        strategy_family=request.strategy_family,
        validator_name="funding_price_confirmation",
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
            "fee_rate": float(parameters.get("fee_rate", 0.001)),
            "slippage_rate": float(parameters.get("slippage_rate", 0.0005)),
        },
    )


def _funding_mean_reversion_validator(request: StrategyValidationRequest) -> StrategyValidationReport:
    parameters = request.parameters
    price_symbol = _nonblank_parameter(parameters, "price_symbol")
    funding_symbol = _nonblank_parameter(parameters, "funding_symbol")
    timeframe = _nonblank_parameter(parameters, "timeframe")
    missing_parameters = [
        name
        for name, value in (
            ("price_symbol", price_symbol),
            ("funding_symbol", funding_symbol),
            ("timeframe", timeframe),
        )
        if value is None
    ]
    if missing_parameters:
        return _blocked_funding_mean_reversion_report(
            request,
            blocked_reasons=["missing_strategy_validation_parameters"],
            metrics={"missing_parameters": missing_parameters},
        )
    try:
        return validate_funding_mean_reversion_from_records(
            request.records,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            threshold_abs=float(parameters.get("threshold_abs", 0.0005)),
            hold_bars=int(parameters.get("hold_bars", 1)),
            fee_rate=float(parameters.get("fee_rate", 0.001)),
            slippage_rate=float(parameters.get("slippage_rate", 0.0005)),
            min_trades=int(parameters.get("min_trades", 3)),
            require_walk_forward=bool(parameters.get("require_walk_forward", True)),
            walk_forward_train_size=int(parameters.get("walk_forward_train_size", 24)),
            walk_forward_test_size=int(parameters.get("walk_forward_test_size", 8)),
            walk_forward_min_splits=int(parameters.get("walk_forward_min_splits", 3)),
            walk_forward_min_pass_rate=float(
                parameters.get("walk_forward_min_pass_rate", 1.0)
            ),
            max_drawdown_limit=_strict_non_negative_float_parameter(
                parameters,
                "max_drawdown_limit",
                0.20,
            ),
            now=_optional_datetime_parameter(parameters, "now"),
            max_age_hours=_optional_positive_float_parameter(
                parameters,
                "max_age_hours",
            ),
            supported_price_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_price_symbols",
                default=("BTC/USDT",),
            ),
            supported_funding_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_funding_symbols",
                default=("BTC/USDT:USDT",),
            ),
        )
    except (OverflowError, TypeError, ValueError) as exc:
        return _blocked_funding_mean_reversion_report(
            request,
            blocked_reasons=["strategy_validation_error"],
            metrics={
                "symbol": price_symbol,
                "funding_symbol": funding_symbol,
                "timeframe": timeframe,
                "validation_error": str(exc),
            },
        )


def _funding_oi_crowding_validator(
    request: StrategyValidationRequest,
) -> StrategyValidationReport:
    parameters = request.parameters
    price_symbol = _nonblank_parameter(parameters, "price_symbol")
    funding_symbol = _nonblank_parameter(parameters, "funding_symbol")
    timeframe = _nonblank_parameter(parameters, "timeframe")
    missing_parameters = [
        name
        for name, value in (
            ("price_symbol", price_symbol),
            ("funding_symbol", funding_symbol),
            ("timeframe", timeframe),
        )
        if value is None
    ]
    if missing_parameters:
        return _blocked_funding_oi_crowding_report(
            request,
            blocked_reasons=["missing_strategy_validation_parameters"],
            metrics={"missing_parameters": missing_parameters},
        )
    try:
        return validate_funding_oi_crowding_from_records(
            request.records,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            open_interest_symbol=_nonblank_parameter(
                parameters,
                "open_interest_symbol",
            ),
            open_interest_timeframe=_nonblank_parameter(
                parameters,
                "open_interest_timeframe",
            ),
            threshold_abs=float(parameters.get("threshold_abs", 0.0005)),
            hold_bars=int(parameters.get("hold_bars", 1)),
            min_open_interest_change_pct=float(
                parameters.get("min_open_interest_change_pct", 0.05)
            ),
            open_interest_lookback_bars=int(
                parameters.get("open_interest_lookback_bars", 1)
            ),
            fee_rate=float(parameters.get("fee_rate", 0.001)),
            slippage_rate=float(parameters.get("slippage_rate", 0.0005)),
            min_trades=int(parameters.get("min_trades", 3)),
            require_walk_forward=bool(parameters.get("require_walk_forward", True)),
            walk_forward_train_size=int(parameters.get("walk_forward_train_size", 24)),
            walk_forward_test_size=int(parameters.get("walk_forward_test_size", 8)),
            walk_forward_min_splits=int(parameters.get("walk_forward_min_splits", 3)),
            walk_forward_min_pass_rate=float(
                parameters.get("walk_forward_min_pass_rate", 1.0)
            ),
            max_drawdown_limit=_strict_non_negative_float_parameter(
                parameters,
                "max_drawdown_limit",
                0.20,
            ),
            now=_optional_datetime_parameter(parameters, "now"),
            max_age_hours=_optional_positive_float_parameter(
                parameters,
                "max_age_hours",
            ),
            supported_price_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_price_symbols",
                default=("BTC/USDT",),
            ),
            supported_funding_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_funding_symbols",
                default=("BTC/USDT:USDT",),
            ),
            supported_open_interest_symbols=_supported_symbol_list_parameter(
                parameters,
                "supported_open_interest_symbols",
                default=("BTC/USDT:USDT",),
            ),
        )
    except (OverflowError, TypeError, ValueError) as exc:
        return _blocked_funding_oi_crowding_report(
            request,
            blocked_reasons=["strategy_validation_error"],
            metrics={
                "symbol": price_symbol,
                "funding_symbol": funding_symbol,
                "timeframe": timeframe,
                "validation_error": str(exc),
            },
        )


def _defi_yield_regime_validator(request: StrategyValidationRequest) -> StrategyValidationReport:
    parameters = request.parameters
    try:
        return validate_defi_yield_regime(
            request.records,
            min_tvl_usd=_strict_non_negative_float_parameter(
                parameters,
                "min_tvl_usd",
                DEFAULT_MIN_TVL_USD,
            ),
            min_apy_change=_strict_non_negative_float_parameter(
                parameters,
                "min_apy_change",
                DEFAULT_MIN_APY_CHANGE,
            ),
            min_observations=_strict_min_observations_parameter(
                parameters,
                "min_observations",
                DEFAULT_MIN_OBSERVATIONS,
            ),
            supported_chains=_supported_chains_parameter(parameters),
            now=_optional_datetime_parameter(parameters, "now"),
            max_age_hours=_strict_positive_float_parameter(
                parameters,
                "max_age_hours",
                DEFAULT_MAX_AGE_HOURS,
            ),
        )
    except (OverflowError, TypeError, ValueError) as exc:
        return StrategyValidationReport(
            strategy_family=request.strategy_family,
            validator_name="defi_yield_regime",
            approved=False,
            blocked_reasons=["strategy_validation_error"],
            metrics={
                "execution_role": "research_only",
                "paper_watchlist_only": True,
                "validation_error": str(exc),
            },
        )


def _dex_liquidity_watchlist_validator(
    request: StrategyValidationRequest,
) -> StrategyValidationReport:
    parameters = request.parameters
    try:
        return validate_dex_liquidity_watchlist(
            request.records,
            min_liquidity_usd=_strict_non_negative_float_parameter(
                parameters,
                "min_liquidity_usd",
                DEFAULT_MIN_LIQUIDITY_USD,
            ),
            min_volume_24h_usd=_strict_non_negative_float_parameter(
                parameters,
                "min_volume_24h_usd",
                DEFAULT_MIN_VOLUME_24H_USD,
            ),
            min_liquidity_change_pct=_strict_non_negative_float_parameter(
                parameters,
                "min_liquidity_change_pct",
                DEFAULT_MIN_LIQUIDITY_CHANGE_PCT,
            ),
            min_volume_change_pct=_strict_non_negative_float_parameter(
                parameters,
                "min_volume_change_pct",
                VOLATILITY_DEFAULT_MIN_VOLUME_CHANGE_PCT,
            ),
            min_observations=_strict_min_observations_parameter(
                parameters,
                "min_observations",
                DEX_DEFAULT_MIN_OBSERVATIONS,
            ),
            supported_chains=_supported_chains_parameter(
                parameters,
                default=DEX_DEFAULT_SUPPORTED_CHAINS,
            ),
            now=_optional_datetime_parameter(parameters, "now"),
            max_age_hours=_strict_positive_float_parameter(
                parameters,
                "max_age_hours",
                DEX_DEFAULT_MAX_AGE_HOURS,
            ),
            require_research_only=_strict_bool_parameter(
                parameters,
                "require_research_only",
                True,
            ),
        )
    except (OverflowError, TypeError, ValueError) as exc:
        return StrategyValidationReport(
            strategy_family=request.strategy_family,
            validator_name="dex_liquidity_watchlist",
            approved=False,
            blocked_reasons=["strategy_validation_error"],
            metrics={
                "execution_role": "research_only",
                "paper_watchlist_only": True,
                "validation_error": str(exc),
            },
        )


def _volatility_regime_watchlist_validator(
    request: StrategyValidationRequest,
) -> StrategyValidationReport:
    parameters = request.parameters
    try:
        return validate_volatility_regime_watchlist(
            request.records,
            compression_window=_strict_positive_integer_parameter(
                parameters,
                "compression_window",
                DEFAULT_COMPRESSION_WINDOW,
            ),
            expansion_window=_strict_positive_integer_parameter(
                parameters,
                "expansion_window",
                DEFAULT_EXPANSION_WINDOW,
            ),
            min_observations=_strict_positive_integer_parameter(
                parameters,
                "min_observations",
                VOLATILITY_DEFAULT_MIN_OBSERVATIONS,
            ),
            max_compression_volatility=_strict_non_negative_float_parameter(
                parameters,
                "max_compression_volatility",
                DEFAULT_MAX_COMPRESSION_VOLATILITY,
            ),
            min_expansion_return_abs=_strict_non_negative_float_parameter(
                parameters,
                "min_expansion_return_abs",
                DEFAULT_MIN_EXPANSION_RETURN_ABS,
            ),
            min_volume_change_pct=_strict_non_negative_float_parameter(
                parameters,
                "min_volume_change_pct",
                DEFAULT_MIN_VOLUME_CHANGE_PCT,
            ),
            supported_symbols=_supported_symbols_parameter(
                parameters,
                default=VOLATILITY_DEFAULT_SUPPORTED_SYMBOLS,
            ),
            now=_optional_datetime_parameter(parameters, "now"),
            max_age_hours=_optional_positive_float_parameter(
                parameters,
                "max_age_hours",
            ),
        )
    except (OverflowError, TypeError, ValueError) as exc:
        return StrategyValidationReport(
            strategy_family=request.strategy_family,
            validator_name="volatility_regime_watchlist",
            approved=False,
            blocked_reasons=["strategy_validation_error"],
            metrics={
                "execution_role": "research_only",
                "paper_watchlist_only": True,
                "validation_error": str(exc),
            },
        )


def _funding_price_paper_runner(request: StrategyPaperRequest) -> StrategyPaperReport:
    validation = _funding_price_validator(_paper_validation_request(request))
    return _paper_report_from_validation(request, validation)


def _funding_mean_reversion_paper_runner(
    request: StrategyPaperRequest,
) -> StrategyPaperReport:
    validation = _funding_mean_reversion_validator(_paper_validation_request(request))
    return _paper_report_from_validation(request, validation)


def _funding_oi_crowding_paper_runner(
    request: StrategyPaperRequest,
) -> StrategyPaperReport:
    validation = _funding_oi_crowding_validator(_paper_validation_request(request))
    return _paper_report_from_validation(
        request,
        validation,
        trade_extractor=_extract_funding_oi_crowding_paper_trades,
    )


def _paper_validation_request(request: StrategyPaperRequest) -> StrategyValidationRequest:
    return StrategyValidationRequest(
        strategy_family=request.strategy_family,
        records=request.records,
        current_capital_usd=request.current_capital_usd,
        parameters=request.parameters,
    )


def _paper_report_from_validation(
    request: StrategyPaperRequest,
    validation: StrategyValidationReport,
    *,
    trade_extractor: Callable[
        [StrategyPaperRequest, str, str, str],
        list[FundingPriceTrade],
    ] = None,
) -> StrategyPaperReport:
    resolved_trade_extractor = trade_extractor or _extract_funding_price_paper_trades
    paper_blocked_reasons = [] if validation.approved else list(validation.blocked_reasons)
    paper_trades: list[dict[str, object]] = []
    observed_at = _PAPER_SENTINEL_OBSERVED_AT
    try:
        price_symbol = _required_nonblank_parameter(request.parameters, "price_symbol")
        funding_symbol = _required_nonblank_parameter(request.parameters, "funding_symbol")
        timeframe = _required_nonblank_parameter(request.parameters, "timeframe")
        observed_at = latest_funding_price_observed_at_from_records(
            request.records,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
        ) or _PAPER_SENTINEL_OBSERVED_AT
    except (OverflowError, TypeError, ValueError) as exc:
        if not paper_blocked_reasons:
            paper_blocked_reasons = ["paper_trade_extraction_error"]
            validation = StrategyValidationReport(
                strategy_family=validation.strategy_family,
                validator_name=validation.validator_name,
                approved=False,
                blocked_reasons=["paper_trade_extraction_error"],
                metrics={
                    **validation.metrics,
                    "paper_trade_extraction_error": str(exc),
                },
            )
    if not paper_blocked_reasons:
        try:
            paper_trades = [
                _paper_trade_metrics(trade)
                for trade in resolved_trade_extractor(
                    request,
                    price_symbol,
                    funding_symbol,
                    timeframe,
                )
            ]
        except (OverflowError, TypeError, ValueError) as exc:
            paper_blocked_reasons = ["paper_trade_extraction_error"]
            validation = StrategyValidationReport(
                strategy_family=validation.strategy_family,
                validator_name=validation.validator_name,
                approved=False,
                blocked_reasons=["paper_trade_extraction_error"],
                metrics={
                    **validation.metrics,
                    "paper_trade_extraction_error": str(exc),
                },
            )
    return StrategyPaperReport(
        strategy_family=request.strategy_family,
        status="blocked" if paper_blocked_reasons else "simulated",
        supports_paper_simulation=True,
        blocked_reasons=paper_blocked_reasons,
        metrics={
            "notional_usd": request.notional_usd,
            "validation": validation.model_dump(mode="json"),
            "paper_trades": paper_trades,
            "observed_at": observed_at.isoformat(),
        },
    )


def _extract_funding_price_paper_trades(
    request: StrategyPaperRequest,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> list[FundingPriceTrade]:
    return extract_funding_price_trades_from_records(
        request.records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        threshold_abs=float(request.parameters.get("threshold_abs", 0.0005)),
        hold_bars=int(request.parameters.get("hold_bars", 1)),
    )


def _extract_funding_oi_crowding_paper_trades(
    request: StrategyPaperRequest,
    price_symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> list[FundingPriceTrade]:
    return extract_funding_oi_crowding_trades_from_records(
        request.records,
        price_symbol=price_symbol,
        funding_symbol=funding_symbol,
        timeframe=timeframe,
        open_interest_symbol=_nonblank_parameter(
            request.parameters,
            "open_interest_symbol",
        ),
        open_interest_timeframe=_nonblank_parameter(
            request.parameters,
            "open_interest_timeframe",
        ),
        threshold_abs=float(request.parameters.get("threshold_abs", 0.0005)),
        hold_bars=int(request.parameters.get("hold_bars", 1)),
        min_open_interest_change_pct=float(
            request.parameters.get("min_open_interest_change_pct", 0.05)
        ),
        open_interest_lookback_bars=int(
            request.parameters.get("open_interest_lookback_bars", 1)
        ),
    )


def _paper_trade_metrics(trade: FundingPriceTrade) -> dict[str, object]:
    return {
        "funding_symbol": trade.funding_symbol,
        "funding_timestamp": trade.funding_timestamp.isoformat(),
        "entry_timestamp": trade.entry_timestamp.isoformat(),
        "exit_timestamp": trade.exit_timestamp.isoformat(),
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "raw_return": trade.raw_return,
        "direction": trade.direction,
        "entry_volume": float(trade.entry_bar.volume),
        "exit_volume": float(trade.exit_bar.volume),
        "next_funding_at": (
            trade.funding.next_funding_at.isoformat()
            if trade.funding.next_funding_at is not None
            else None
        ),
    }


def _supported_chains_parameter(
    parameters: dict[str, object],
    *,
    default: Sequence[str] = DEFAULT_SUPPORTED_CHAINS,
) -> tuple[str, ...]:
    if "supported_chains" not in parameters:
        return tuple(default)

    value = parameters["supported_chains"]
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("supported_chains must be a sequence of chain names")

    supported_chains: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("supported_chains must contain strings")
        stripped = item.strip()
        if not stripped:
            raise ValueError("supported_chains must contain non-empty strings")
        if stripped in seen:
            continue
        supported_chains.append(stripped)
        seen.add(stripped)
    if not supported_chains:
        raise ValueError("supported_chains must not be empty")
    return tuple(supported_chains)


def _strict_non_negative_float_parameter(
    parameters: dict[str, object],
    key: str,
    default: float,
) -> float:
    value = parameters.get(key, default)
    parsed = _strict_float(value, key)
    if parsed < 0:
        raise ValueError(f"{key} must be non-negative")
    return parsed


def _strict_positive_float_parameter(
    parameters: dict[str, object],
    key: str,
    default: float,
) -> float:
    value = parameters.get(key, default)
    parsed = _strict_float(value, key)
    if parsed <= 0:
        raise ValueError(f"{key} must be positive")
    return parsed


def _strict_float(value: object, key: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be numeric, not boolean")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{key} must be finite")
    return parsed


def _strict_min_observations_parameter(
    parameters: dict[str, object],
    key: str,
    default: int,
) -> int:
    value = parameters.get(key, default)
    parsed = _strict_integer(value, key)
    if parsed < 2:
        raise ValueError(f"{key} must be at least 2")
    return parsed


def _strict_positive_integer_parameter(
    parameters: dict[str, object],
    key: str,
    default: int,
) -> int:
    value = parameters.get(key, default)
    parsed = _strict_integer(value, key)
    if parsed <= 0:
        raise ValueError(f"{key} must be positive")
    return parsed


def _strict_integer(value: object, key: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer, not boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError(f"{key} must be an integer")
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{key} must be an integer")
        signless = stripped[1:] if stripped[0] in {"+", "-"} else stripped
        if not signless.isdigit():
            raise ValueError(f"{key} must be an integer")
        return int(stripped)
    raise ValueError(f"{key} must be an integer")


def _strict_bool_parameter(
    parameters: dict[str, object],
    key: str,
    default: bool,
) -> bool:
    value = parameters.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _optional_datetime_parameter(
    parameters: dict[str, object],
    key: str,
) -> datetime | None:
    value = parameters.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"{key} must be a datetime or ISO datetime string")


def _optional_positive_float_parameter(
    parameters: dict[str, object],
    key: str,
) -> float | None:
    if key not in parameters:
        return None
    return _strict_positive_float_parameter(parameters, key, 1.0)


def _supported_symbols_parameter(
    parameters: dict[str, object],
    *,
    default: Sequence[str],
) -> tuple[str, ...]:
    return _supported_symbol_list_parameter(
        parameters,
        "supported_symbols",
        default=default,
    )


def _supported_symbol_list_parameter(
    parameters: dict[str, object],
    key: str,
    *,
    default: Sequence[str],
) -> tuple[str, ...]:
    if key not in parameters:
        return tuple(default)
    value = parameters[key]
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{key} must be a sequence of symbols")
    supported_symbols: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{key} must contain strings")
        stripped = item.strip()
        if not stripped:
            raise ValueError(f"{key} must contain non-empty strings")
        if stripped in seen:
            continue
        supported_symbols.append(stripped)
        seen.add(stripped)
    if not supported_symbols:
        raise ValueError(f"{key} must not be empty")
    return tuple(supported_symbols)


def _nonblank_parameter(parameters: dict[str, object], key: str) -> str | None:
    value = parameters.get(key)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _required_nonblank_parameter(parameters: dict[str, object], key: str) -> str:
    value = _nonblank_parameter(parameters, key)
    if value is None:
        raise ValueError(f"missing paper trade extraction parameter: {key}")
    return value


def _blocked_funding_price_report(
    request: StrategyValidationRequest,
    *,
    blocked_reasons: list[str],
    metrics: dict[str, object],
) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=request.strategy_family,
        validator_name="funding_price_confirmation",
        approved=False,
        blocked_reasons=blocked_reasons,
        metrics=metrics,
    )


def _blocked_funding_mean_reversion_report(
    request: StrategyValidationRequest,
    *,
    blocked_reasons: list[str],
    metrics: dict[str, object],
) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=request.strategy_family,
        validator_name="funding_mean_reversion",
        approved=False,
        blocked_reasons=blocked_reasons,
        metrics=metrics,
    )


def _blocked_funding_oi_crowding_report(
    request: StrategyValidationRequest,
    *,
    blocked_reasons: list[str],
    metrics: dict[str, object],
) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=request.strategy_family,
        validator_name="funding_oi_crowding",
        approved=False,
        blocked_reasons=blocked_reasons,
        metrics=metrics,
    )
