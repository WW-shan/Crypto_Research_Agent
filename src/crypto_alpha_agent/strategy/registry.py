from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from crypto_alpha_agent.strategy.models import (
    StrategyFamilySpec,
    StrategyPaperReport,
    StrategyPaperRequest,
    StrategyValidationReport,
    StrategyValidationRequest,
)
from crypto_alpha_agent.validation.funding_price import validate_funding_price_confirmation_from_records

StrategyValidator = Callable[[StrategyValidationRequest], StrategyValidationReport]
StrategyPaperRunner = Callable[[StrategyPaperRequest], StrategyPaperReport]


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
    spec = StrategyFamilySpec(
        strategy_family="funding_extremity_price_confirmation",
        display_name="Funding Extremity With Price Confirmation",
        required_record_types=["market_candle", "funding_rate"],
        required_symbols=["BTC/USDT", "BTC/USDT:USDT"],
        supports_paper_simulation=False,
        min_capital_usd=25.0,
        max_notional_usd=25.0,
        validator_name="funding_price_confirmation",
        blocked_reasons=[],
        configured_capital_usd=max(current_capital_usd, 25.0),
    )
    registry.register(spec, _funding_price_validator)
    return registry


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


def _nonblank_parameter(parameters: dict[str, object], key: str) -> str | None:
    value = parameters.get(key)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


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
