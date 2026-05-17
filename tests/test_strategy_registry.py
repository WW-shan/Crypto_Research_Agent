import pytest
from pydantic import ValidationError

from crypto_alpha_agent.strategy import (
    StrategyFamilySpec,
    StrategyPaperReport,
    StrategyPaperRequest,
    StrategyRegistry,
    StrategyValidationReport,
    StrategyValidationRequest,
    default_strategy_registry,
)


def _spec(**overrides):
    data = {
        "strategy_family": "funding_extremity_price_confirmation",
        "display_name": "Funding Extremity With Price Confirmation",
        "required_record_types": ["market_candle", "funding_rate"],
        "required_symbols": ["BTC/USDT", "BTC/USDT:USDT"],
        "supports_paper_simulation": True,
        "min_capital_usd": 25.0,
        "max_notional_usd": 15.0,
        "validator_name": "funding_price",
        "blocked_reasons": [],
    }
    data.update(overrides)
    return StrategyFamilySpec(**data)


def _validator(request: StrategyValidationRequest) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=request.strategy_family,
        validator_name="funding_price",
        approved=True,
        blocked_reasons=[],
        metrics={"record_count": len(request.records)},
    )


def _paper_runner(request: StrategyPaperRequest) -> StrategyPaperReport:
    return StrategyPaperReport(
        strategy_family=request.strategy_family,
        status="simulated",
        supports_paper_simulation=True,
        blocked_reasons=[],
        metrics={"notional_usd": request.notional_usd},
    )


class RecordingPaperRunner:
    def __init__(self):
        self.calls = 0

    def __call__(self, request: StrategyPaperRequest) -> StrategyPaperReport:
        self.calls += 1
        return _paper_runner(request)


def test_registry_lists_available_strategy_families():
    registry = StrategyRegistry(current_capital_usd=300.0)
    registry.register(_spec(), _validator, paper_runner=_paper_runner)

    assert registry.list_families() == ("funding_extremity_price_confirmation",)
    assert default_strategy_registry(current_capital_usd=300.0).list_families()


def test_registry_rejects_duplicate_strategy_family():
    registry = StrategyRegistry(current_capital_usd=300.0)
    registry.register(_spec(), _validator, paper_runner=_paper_runner)

    with pytest.raises(ValueError, match="strategy family already registered"):
        registry.register(_spec(display_name="Duplicate"), _validator, paper_runner=_paper_runner)


@pytest.mark.parametrize("current_capital_usd", [float("nan"), float("inf"), float("-inf")])
def test_registry_rejects_non_finite_current_capital(current_capital_usd):
    with pytest.raises(ValueError, match="current_capital_usd must be finite"):
        StrategyRegistry(current_capital_usd=current_capital_usd)


def test_unknown_family_fails_closed_with_clear_error():
    registry = StrategyRegistry(current_capital_usd=300.0)

    with pytest.raises(KeyError, match="unknown strategy family: missing_family"):
        registry.get("missing_family")

    report = registry.validate(
        StrategyValidationRequest(
            strategy_family="missing_family",
            records=[],
            current_capital_usd=300.0,
        )
    )

    assert report.approved is False
    assert report.blocked_reasons == ("unknown_strategy_family",)


def test_strategy_spec_declares_safe_data_validation_and_paper_contract():
    spec = _spec()
    registry = StrategyRegistry(current_capital_usd=300.0)
    registry.register(spec, _validator, paper_runner=_paper_runner)

    stored = registry.get("funding_extremity_price_confirmation")
    validation = registry.validate(
        StrategyValidationRequest(
            strategy_family="funding_extremity_price_confirmation",
            records=[{"record_type": "market_candle"}, {"record_type": "funding_rate"}],
            current_capital_usd=300.0,
        )
    )
    paper = registry.run_paper(
        StrategyPaperRequest(
            strategy_family="funding_extremity_price_confirmation",
            records=[],
            current_capital_usd=300.0,
            notional_usd=10.0,
        )
    )

    assert stored.required_record_types == ("market_candle", "funding_rate")
    assert stored.required_symbols == ("BTC/USDT", "BTC/USDT:USDT")
    assert stored.supports_paper_simulation is True
    assert stored.min_capital_usd == 25.0
    assert stored.max_notional_usd == 15.0
    assert stored.validator_name == "funding_price"
    assert stored.blocked_reasons == ()
    assert validation.approved is True
    assert paper.status == "simulated"


def test_blocked_spec_prevents_validation_and_paper_runner():
    runner = RecordingPaperRunner()
    registry = StrategyRegistry(current_capital_usd=300.0)
    registry.register(_spec(blocked_reasons=["manual_review_required"]), _validator, paper_runner=runner)

    validation = registry.validate(
        StrategyValidationRequest(
            strategy_family="funding_extremity_price_confirmation",
            records=[],
            current_capital_usd=300.0,
        )
    )
    paper = registry.run_paper(
        StrategyPaperRequest(
            strategy_family="funding_extremity_price_confirmation",
            records=[],
            current_capital_usd=300.0,
            notional_usd=10.0,
        )
    )

    assert validation.approved is False
    assert validation.blocked_reasons == ("manual_review_required",)
    assert paper.status == "blocked"
    assert paper.blocked_reasons == ("manual_review_required",)
    assert runner.calls == 0


def test_request_capital_below_strategy_minimum_fails_closed():
    runner = RecordingPaperRunner()
    registry = StrategyRegistry(current_capital_usd=300.0)
    registry.register(_spec(min_capital_usd=25.0), _validator, paper_runner=runner)

    validation = registry.validate(
        StrategyValidationRequest(
            strategy_family="funding_extremity_price_confirmation",
            records=[],
            current_capital_usd=24.99,
        )
    )
    paper = registry.run_paper(
        StrategyPaperRequest(
            strategy_family="funding_extremity_price_confirmation",
            records=[],
            current_capital_usd=24.99,
            notional_usd=10.0,
        )
    )

    assert validation.approved is False
    assert validation.blocked_reasons == ("insufficient_current_capital",)
    assert paper.status == "blocked"
    assert paper.blocked_reasons == ("insufficient_current_capital",)
    assert runner.calls == 0


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("requires_speed_edge", True, "requires_speed_edge"),
        ("requires_premium_rpc", True, "requires_premium_rpc"),
        ("live_order_routing", True, "live_order_routing"),
        ("min_capital_usd", 301.0, "min_capital_exceeds_configured_capital"),
    ],
)
def test_strategy_specs_reject_unsafe_or_too_expensive_requirements(field, value, reason):
    with pytest.raises(ValidationError, match=reason):
        _spec(**{field: value}, configured_capital_usd=300.0)


@pytest.mark.parametrize("bad_symbol", [object(), 123])
def test_strategy_spec_rejects_non_string_required_symbols_as_validation_error(bad_symbol):
    with pytest.raises(ValidationError):
        _spec(required_symbols=[bad_symbol])


@pytest.mark.parametrize(
    "approved,blocked_reasons",
    [
        (True, ["should_not_be_present"]),
        (False, []),
    ],
)
def test_validation_report_requires_status_consistent_blocked_reasons(approved, blocked_reasons):
    with pytest.raises(ValidationError):
        StrategyValidationReport(
            strategy_family="funding_extremity_price_confirmation",
            validator_name="funding_price",
            approved=approved,
            blocked_reasons=blocked_reasons,
        )


@pytest.mark.parametrize("bad_reason", [object(), 123])
def test_validation_report_rejects_non_string_blocked_reasons_as_validation_error(bad_reason):
    with pytest.raises(ValidationError):
        StrategyValidationReport(
            strategy_family="funding_extremity_price_confirmation",
            validator_name="funding_price",
            approved=False,
            blocked_reasons=[bad_reason],
        )


@pytest.mark.parametrize(
    "status,blocked_reasons",
    [
        ("simulated", ["should_not_be_present"]),
        ("blocked", []),
        ("unsupported", []),
    ],
)
def test_paper_report_requires_status_consistent_blocked_reasons(status, blocked_reasons):
    with pytest.raises(ValidationError):
        StrategyPaperReport(
            strategy_family="funding_extremity_price_confirmation",
            status=status,
            supports_paper_simulation=True,
            blocked_reasons=blocked_reasons,
        )


@pytest.mark.parametrize("bad_reason", [object(), 123])
def test_paper_report_rejects_non_string_blocked_reasons_as_validation_error(bad_reason):
    with pytest.raises(ValidationError):
        StrategyPaperReport(
            strategy_family="funding_extremity_price_confirmation",
            status="blocked",
            supports_paper_simulation=True,
            blocked_reasons=[bad_reason],
        )
