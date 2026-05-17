from __future__ import annotations

from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
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


def _funding_record(funding: FundingRateRecord) -> SourceRecord:
    safe_symbol = funding.symbol.replace("/", "").replace(":", "-")
    return SourceRecord(
        record_id=f"{funding.source}:{safe_symbol}:funding:{funding.timestamp.isoformat()}",
        source=funding.source,
        record_type="funding_rate",
        observed_at=funding.timestamp,
        payload=funding.model_dump(mode="json"),
    )


def _write_fixture(tmp_path, closes: list[float], fundings: list[FundingRateRecord]):
    db_path = tmp_path / "research.sqlite"
    store = ResearchDataStore(db_path)
    store.upsert_records([_candle(i, close).to_source_record() for i, close in enumerate(closes)])
    store.upsert_records([_funding_record(item) for item in fundings])
    return db_path


def test_positive_extreme_funding_after_price_drop_creates_short_mean_reversion_trade(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
    from crypto_alpha_agent.strategy.funding_mean_reversion import validate_funding_mean_reversion

    db_path = _write_fixture(tmp_path, [100, 110, 106, 104, 103], [_funding(1, 0.0009)])

    validation = validate_funding_mean_reversion(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
        require_walk_forward=False,
    )
    report = run_paper_sim_loop(
        db_path,
        run_id="mean-reversion-short",
        strategy_family="funding_mean_reversion_after_extreme",
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

    assert validation.strategy_family == "funding_mean_reversion_after_extreme"
    assert validation.approved is True
    assert validation.metrics["trade_count"] == 1
    assert validation.metrics["slippage_adjusted_expectancy"] > 0.0
    assert "missing_open_interest_confirmation" in validation.metrics["notes"]
    outcome = report.outcomes[0]
    assert outcome.strategy_family == "funding_mean_reversion_after_extreme"
    assert outcome.status == "closed"
    assert outcome.signal_timestamp == datetime(2026, 5, 17, 1, tzinfo=UTC)
    assert outcome.entry_price == 110.0
    assert outcome.exit_price == 104.0
    assert outcome.gross_pnl_usd == pytest.approx(25.0 * (6.0 / 110.0))

    legacy_family_report = run_paper_sim_loop(
        db_path,
        run_id="legacy-family-short",
        strategy_family="funding_extremity_price_confirmation",
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
    assert outcome.candidate_id != legacy_family_report.outcomes[0].candidate_id


def test_negative_extreme_funding_after_price_bounce_creates_long_mean_reversion_trade(tmp_path):
    from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop

    db_path = _write_fixture(tmp_path, [100, 90, 94, 96, 97], [_funding(1, -0.0009)])

    report = run_paper_sim_loop(
        db_path,
        run_id="mean-reversion-long",
        strategy_family="funding_mean_reversion_after_extreme",
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

    outcome = report.outcomes[0]
    assert report.validation.approved is True
    assert report.validation.metrics["trade_count"] == 1
    assert outcome.status == "closed"
    assert outcome.entry_price == 90.0
    assert outcome.exit_price == 96.0
    assert outcome.gross_pnl_usd == pytest.approx(25.0 * (6.0 / 90.0))


def test_mean_reversion_requires_positive_fee_and_slippage_adjusted_expectancy(tmp_path):
    from crypto_alpha_agent.strategy.funding_mean_reversion import validate_funding_mean_reversion

    db_path = _write_fixture(tmp_path, [100, 100, 100.2, 100.3], [_funding(1, -0.0009)])

    result = validate_funding_mean_reversion(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.001,
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert result.metrics["slippage_adjusted_expectancy"] <= 0.0
    assert "non_positive_expectancy" in result.blocked_reasons


def test_mean_reversion_requires_walk_forward_by_default(tmp_path):
    from crypto_alpha_agent.strategy.funding_mean_reversion import validate_funding_mean_reversion

    db_path = _write_fixture(tmp_path, [100, 110, 106, 104, 103], [_funding(1, 0.0009)])

    result = validate_funding_mean_reversion(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
    )

    assert result.approved is False
    assert "insufficient_walk_forward_splits" in result.blocked_reasons


def test_mean_reversion_fails_closed_on_duplicate_timestamps(tmp_path):
    from crypto_alpha_agent.strategy.funding_mean_reversion import validate_funding_mean_reversion

    db_path = _write_fixture(tmp_path, [100, 110, 106, 104, 103], [_funding(1, 0.0009)])
    duplicate_candle = _candle(1, 111.0).model_copy(
        update={"source": "coinbase_public", "venue": "coinbase"}
    )
    ResearchDataStore(db_path).upsert_records([duplicate_candle.to_source_record()])

    result = validate_funding_mean_reversion(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "duplicate_price_timestamp" in result.blocked_reasons


def test_mean_reversion_fails_closed_on_non_positive_trade_prices(tmp_path):
    from crypto_alpha_agent.strategy.funding_mean_reversion import validate_funding_mean_reversion

    db_path = _write_fixture(tmp_path, [100, 110, 106, 0, 103], [_funding(1, 0.0009)])

    result = validate_funding_mean_reversion(
        db_path,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        threshold_abs=0.0005,
        hold_bars=2,
        fee_rate=0.001,
        slippage_rate=0.0005,
        min_trades=1,
        require_walk_forward=False,
    )

    assert result.approved is False
    assert "non_positive_price" in result.blocked_reasons
