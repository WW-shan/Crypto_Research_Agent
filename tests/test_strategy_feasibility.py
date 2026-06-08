from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore


SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
START = datetime(2026, 1, 1, tzinfo=UTC)


def test_large_liquid_momentum_feasibility_produces_walk_forward_metrics(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=430)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    before = _record_ids(db_path)
    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.command == "strategy-feasibility"
    assert report.mode == "large-liquid-momentum-regime"
    assert report.readiness == "feasible"
    assert len(report.split_metrics) >= 3
    assert all(metric.test_observations > 0 for metric in report.split_metrics)
    assert all(metric.cost_adjusted_return_mean > 0 for metric in report.split_metrics)
    assert report.derivatives_record_counts == {
        "basis": 0,
        "long_short_account_ratio": 0,
        "premium_index_kline": 0,
        "taker_buy_sell_volume": 0,
    }
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert _record_ids(db_path) == before


def test_large_liquid_momentum_feasibility_blocks_insufficient_aligned_history(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=60)

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.readiness == "blocked"
    assert "insufficient_aligned_history" in report.reason_codes
    assert report.split_metrics == []


def test_large_liquid_momentum_feasibility_blocks_duplicate_timestamps(tmp_path):
    db_path = tmp_path / "research.sqlite"
    _seed_market_candles(db_path, count=430)
    duplicate = _candle("BTC/USDT", 10, close=110.0).to_source_record()
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"{duplicate.record_id}:duplicate",
                source=duplicate.source,
                record_type=duplicate.record_type,
                observed_at=duplicate.observed_at,
                payload=duplicate.payload,
            )
        ]
    )

    from crypto_alpha_agent.pipeline.strategy_feasibility import (
        build_large_liquid_momentum_feasibility_report,
    )

    report = build_large_liquid_momentum_feasibility_report(
        db_path,
        symbols=SYMBOLS,
        timeframe="1h",
        current_capital_usd=300,
    )

    assert report.readiness == "blocked"
    assert "duplicate_timestamps" in report.reason_codes
    assert any("duplicate_timestamps" in item.blocked_reasons for item in report.symbol_reports)


def test_strategy_feasibility_cli_writes_markdown_and_json(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "feasibility.md"
    json_out = tmp_path / "feasibility.json"
    _seed_market_candles(db_path, count=430)

    exit_code = main(
        [
            "strategy-feasibility",
            "--db",
            str(db_path),
            "--mode",
            "large-liquid-momentum-regime",
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["command"] == "strategy-feasibility"
    assert payload["report"]["readiness"] == "feasible"
    assert json_payload["report"]["uses_real_capital"] is False
    assert json_payload["report"]["live_order_routing"] is False
    assert "Large Liquid Momentum" in out_path.read_text(encoding="utf-8")


def _seed_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol_index, symbol in enumerate(SYMBOLS):
        base = 100.0 + symbol_index * 50.0
        drift = 0.35 - symbol_index * 0.08
        for index in range(count):
            close = base + index * drift
            records.append(_candle(symbol, index, close=close).to_source_record())
    ResearchDataStore(db_path).upsert_records(records)


def _candle(symbol: str, index: int, *, close: float) -> MarketCandle:
    return MarketCandle(
        source="unit_test",
        venue="binance",
        symbol=symbol,
        timestamp=START + timedelta(hours=index),
        timeframe="1h",
        open=close * 0.999,
        high=close * 1.001,
        low=close * 0.998,
        close=close,
        volume=10_000.0 + index,
    )


def _record_ids(db_path) -> set[str]:
    return {record.record_id for record in ResearchDataStore(db_path).load_records()}
