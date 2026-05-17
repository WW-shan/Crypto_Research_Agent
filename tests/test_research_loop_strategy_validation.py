from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def _candle(hour: int, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 17, hour, tzinfo=UTC),
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=close - 1.0,
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


def _write_funding_price_fixture(db_path, *, include_funding: bool = True) -> None:
    store = ResearchDataStore(db_path)
    candles = [
        _candle(i, close)
        for i, close in enumerate([100, 103, 101, 99, 102, 104, 101, 100, 98, 101])
    ]
    store.upsert_records([item.to_source_record() for item in candles])
    if include_funding:
        store.upsert_records(
            [
                _funding_record(item)
                for item in [_funding(1, 0.0008), _funding(4, -0.0009), _funding(6, 0.0007)]
            ]
        )


def test_research_loop_cli_uses_registered_funding_price_strategy(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-validation",
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--validation-timeframe",
            "1h",
            "--hold-bars",
            "2",
            "--min-trades",
            "2",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    summary = payload["report"]["validation_summaries"][0]
    assert exit_code == 0
    assert summary["strategy_family"] == "funding_extremity_price_confirmation"
    assert summary["asset"] == "BTC/USDT"
    assert summary["funding_symbol"] == "BTC/USDT:USDT"
    assert summary["timeframe"] == "1h"
    assert summary["walk_forward_split_count"] == 0
    assert summary["walk_forward_pass_rate"] == pytest.approx(0.0)
    assert "insufficient_walk_forward_splits" in summary["blocked_reasons"]
    assert summary["fees"] == pytest.approx(0.001)
    assert summary["slippage"] == pytest.approx(0.0005)
    assert summary["gross_expectancy"] is not None
    assert summary["fee_adjusted_expectancy"] is not None
    assert summary["slippage_adjusted_expectancy"] is not None
    assert summary["net_return"] is not None
    assert summary["max_drawdown"] is not None


def test_research_loop_strategy_validation_blocks_missing_funding(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path, include_funding=False)

    main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-validation",
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--validation-timeframe",
            "1h",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    summary = payload["report"]["validation_summaries"][0]
    assert "insufficient_funding_samples" in summary["blocked_reasons"]


def test_research_loop_strategy_markdown_names_family_and_blockers(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    report_path = tmp_path / "report.md"
    _write_funding_price_fixture(db_path, include_funding=False)

    main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-validation",
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--validation-timeframe",
            "1h",
            "--report-out",
            str(report_path),
        ]
    )
    capsys.readouterr()

    text = report_path.read_text(encoding="utf-8")
    assert "funding_extremity_price_confirmation" in text
    assert "insufficient_funding_samples" in text


def test_direct_research_loop_strategy_validation_missing_params_blocks(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
    )

    summary = report.validation_summaries[0]
    dumped = summary.model_dump(mode="json")
    assert summary.status == "blocked"
    assert "missing_strategy_validation_parameters" in summary.blocked_reasons
    assert summary.asset != "None"
    assert summary.funding_symbol != "None"
    assert summary.timeframe != "None"
    assert "None" not in {
        value for value in dumped.values() if isinstance(value, str)
    }


def test_direct_research_loop_strategy_validation_error_blocks(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        threshold_abs=0.0,
    )

    summary = report.validation_summaries[0]
    assert summary.status == "blocked"
    assert "strategy_validation_error" in summary.blocked_reasons
    assert summary.asset == "BTC/USDT"
    assert summary.funding_symbol == "BTC/USDT:USDT"
    assert summary.timeframe == "1h"


def test_direct_research_loop_strategy_validation_uses_limited_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
        limit=1,
    )

    summary = report.validation_summaries[0]
    assert report.loaded_records == 1
    assert summary.status == "blocked"
    assert summary.trade_count == 0
    assert "insufficient_price_bars" in summary.blocked_reasons
    assert "insufficient_trades" in summary.blocked_reasons


def test_direct_research_loop_strategy_validation_uses_record_type_scope(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
        record_type="funding_rate",
    )

    summary = report.validation_summaries[0]
    assert report.loaded_records == 3
    assert summary.status == "blocked"
    assert summary.trade_count == 0
    assert "insufficient_price_bars" in summary.blocked_reasons
    assert "insufficient_trades" in summary.blocked_reasons


def test_direct_research_loop_strategy_validation_returns_funding_summary(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _write_funding_price_fixture(db_path)

    report = run_stored_research_loop(
        db_path,
        include_validation=True,
        strategy_family="funding_extremity_price_confirmation",
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        hold_bars=2,
        min_trades=2,
    )

    summary = report.validation_summaries[0]
    assert summary.strategy_family == "funding_extremity_price_confirmation"
    assert summary.asset == "BTC/USDT"
    assert summary.funding_symbol == "BTC/USDT:USDT"
    assert summary.timeframe == "1h"
    assert summary.walk_forward_split_count == 0
    assert summary.walk_forward_pass_rate == pytest.approx(0.0)
    assert summary.gross_expectancy is not None
