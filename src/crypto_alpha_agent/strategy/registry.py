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
        if spec.min_capital_usd > self._current_capital_usd:
            raise ValueError("strategy spec is not low-capital paper safe: min_capital_exceeds_configured_capital")
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
    if current_capital_usd < 25.0:
        return registry
    spec = StrategyFamilySpec(
        strategy_family="placeholder_low_capital_research",
        display_name="Placeholder Low-Capital Research Strategy",
        required_record_types=["market_candle"],
        required_symbols=["BTC/USDT"],
        supports_paper_simulation=False,
        min_capital_usd=25.0,
        max_notional_usd=10.0,
        validator_name="placeholder_safe_validator",
        blocked_reasons=["validator_not_integrated"],
        configured_capital_usd=current_capital_usd,
    )
    registry.register(spec, _placeholder_validator)
    return registry


def _placeholder_validator(request: StrategyValidationRequest) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=request.strategy_family,
        validator_name="placeholder_safe_validator",
        approved=False,
        blocked_reasons=["validator_not_integrated"],
        metrics={},
    )
