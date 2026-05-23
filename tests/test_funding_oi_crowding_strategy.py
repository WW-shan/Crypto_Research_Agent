from __future__ import annotations

from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import (
    FundingRateRecord,
    MarketCandle,
    OpenInterestRecord,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=max(0.0, close - 1.0),
        close=close,
        volume=1000.0,
    )


def _funding(hour: int, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        funding_rate=rate,
    )


def _open_interest(
    hour: int,
    value: float,
    *,
    symbol: str = "BTC/USDT:USDT",
) -> OpenInterestRecord:
    return OpenInterestRecord(
        source="ccxt",
        venue="binance",
        symbol=symbol,
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open_interest=value,
    )


def _funding_record(funding: FundingRateRecord) -> SourceRecord:
    safe_symbol = funding.symbol.replace("/", "").replace(":", "-")
    return SourceRecord(
        record_id=f"{funding.source}:{safe_symbol}:funding:{funding.timestamp.isoformat()}",
        source=funding.source,
        record_type="funding_rate",
        observed_at=funding.timestamp,
        payload=funding.model_dump(mode="json"),
    )


def _write_fixture(
    tmp_path,
    *,
    open_interest: list[OpenInterestRecord] | None = None,
) -> object:
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    candles = [_candle(i, close) for i, close in enumerate([100, 110, 106, 104, 103])]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([_funding_record(_funding(1, 0.0009))])
    if open_interest is not None:
        store.upsert_records([item.to_source_record() for item in open_interest])
    return db_path


def test_funding_oi_crowding_approves_confirmed_extreme_and_paper_simulates(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
    from crypto_alpha_agent.strategy.funding_oi_crowding import (
        STRATEGY_FAMILY,
        validate_funding_oi_crowding,
    )

    db_path = _write_fixture(
        tmp_path,
        open_interest=[_open_interest(0, 1000.0), _open_interest(1, 1120.0)],
    )

    validation = validate_funding_oi_crowding(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        open_interest_symbol="BTC/USDT:USDT",
        timeframe="1h",
        open_interest_timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_open_interest_change_pct=0.05,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
        require_walk_forward=False,
    )
    paper = run_paper_sim_loop(
        db_path,
        run_id="funding-oi-crowding",
        strategy_family=STRATEGY_FAMILY,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        current_capital_usd=100.0,
        notional_usd=25.0,
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
        require_walk_forward=False,
    )

    assert validation.strategy_family == STRATEGY_FAMILY
    assert validation.validator_name == "funding_oi_crowding"
    assert validation.approved is True
    assert validation.metrics["trade_count"] == 1
    assert validation.metrics["open_interest_confirmed_trade_count"] == 1
    assert validation.metrics["open_interest_sample_count"] == 2
    assert validation.metrics["slippage_adjusted_expectancy"] > 0.0
    assert paper.validation.approved is True
    assert paper.outcome_count == 1
    outcome = paper.outcomes[0]
    assert outcome.strategy_family == STRATEGY_FAMILY
    assert outcome.status == "closed"
    assert outcome.signal_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert outcome.entry_price == 110.0
    assert outcome.exit_price == 104.0
    assert outcome.touched_real_capital is False
    assert outcome.live_order_routing is False


def test_funding_oi_crowding_fails_closed_when_open_interest_is_missing(tmp_path):
    from crypto_alpha_agent.strategy.funding_oi_crowding import validate_funding_oi_crowding

    db_path = _write_fixture(tmp_path, open_interest=None)

    result = validate_funding_oi_crowding(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "missing_open_interest_records" in result.blocked_reasons


def test_funding_oi_crowding_fails_closed_without_open_interest_expansion(tmp_path):
    from crypto_alpha_agent.strategy.funding_oi_crowding import validate_funding_oi_crowding

    db_path = _write_fixture(
        tmp_path,
        open_interest=[_open_interest(0, 1000.0), _open_interest(1, 1001.0)],
    )

    result = validate_funding_oi_crowding(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_open_interest_change_pct=0.05,
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert result.metrics["open_interest_confirmed_trade_count"] == 0
    assert "no_open_interest_expansion" in result.blocked_reasons


def test_funding_oi_crowding_fails_closed_on_stale_source_data(tmp_path):
    from crypto_alpha_agent.strategy.funding_oi_crowding import validate_funding_oi_crowding

    db_path = _write_fixture(
        tmp_path,
        open_interest=[_open_interest(0, 1000.0), _open_interest(1, 1120.0)],
    )

    result = validate_funding_oi_crowding(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=1,
        require_walk_forward=False,
        now=datetime(2026, 5, 24, tzinfo=UTC),
        max_age_hours=24.0,
    )

    assert result.approved is False
    assert "stale_source" in result.blocked_reasons


def test_funding_oi_crowding_fails_closed_on_unsupported_symbol(tmp_path):
    from crypto_alpha_agent.strategy.funding_oi_crowding import validate_funding_oi_crowding

    db_path = _write_fixture(
        tmp_path,
        open_interest=[_open_interest(0, 1000.0), _open_interest(1, 1120.0)],
    )

    result = validate_funding_oi_crowding(
        db_path,
        price_symbol="DOGE/USDT",
        funding_symbol="DOGE/USDT:USDT",
        timeframe="1h",
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "unsupported_symbol" in result.blocked_reasons


def test_funding_oi_crowding_fails_closed_on_unsupported_open_interest_symbol(tmp_path):
    from crypto_alpha_agent.strategy.funding_oi_crowding import validate_funding_oi_crowding

    db_path = _write_fixture(
        tmp_path,
        open_interest=[
            _open_interest(0, 1000.0, symbol="ETH/USDT:USDT"),
            _open_interest(1, 1120.0, symbol="ETH/USDT:USDT"),
        ],
    )

    result = validate_funding_oi_crowding(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        open_interest_symbol="ETH/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "unsupported_symbol" in result.blocked_reasons


def test_funding_oi_crowding_rejects_invalid_min_trades(tmp_path):
    from crypto_alpha_agent.strategy import StrategyValidationRequest, default_strategy_registry
    from crypto_alpha_agent.strategy.funding_oi_crowding import (
        STRATEGY_FAMILY,
        validate_funding_oi_crowding,
    )

    db_path = _write_fixture(
        tmp_path,
        open_interest=[_open_interest(0, 1000.0), _open_interest(1, 1120.0)],
    )
    records = tuple(
        record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records()
    )

    with pytest.raises(ValueError, match="min_trades"):
        validate_funding_oi_crowding(
            db_path,
            price_symbol="BTC/USDT",
            funding_symbol="BTC/USDT:USDT",
            timeframe="1h",
            min_trades=-1,
            require_walk_forward=False,
        )

    report = default_strategy_registry(current_capital_usd=300.0).validate(
        StrategyValidationRequest(
            strategy_family=STRATEGY_FAMILY,
            records=records,
            current_capital_usd=300.0,
            parameters={
                "price_symbol": "BTC/USDT",
                "funding_symbol": "BTC/USDT:USDT",
                "timeframe": "1h",
                "min_trades": -1,
                "require_walk_forward": False,
            },
        )
    )

    assert report.approved is False
    assert report.blocked_reasons == ("strategy_validation_error",)
