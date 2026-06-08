from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import DataSuitability, MarketCandle, SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.memory.store import MemoryStore


START = datetime(2026, 5, 1, tzinfo=UTC)
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]


def test_strategy_feasibility_multi_hypothesis_cli_writes_markdown_and_json(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    out_path = tmp_path / "multi-hypothesis.md"
    json_out = tmp_path / "multi-hypothesis.json"
    _seed_directional_market_candles(db_path, count=120)
    ResearchDataStore(db_path).upsert_records(
        [_source_health("binance_public", "um_futures_ohlcv", START + timedelta(hours=119))]
    )

    before = _record_snapshot(db_path)
    exit_code = main(
        [
            "strategy-feasibility",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--mode",
            "multi-hypothesis-lab",
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--candidate",
            "short_horizon_momentum_volatility_filter",
            "--cost-bps-grid",
            "5",
            "--cost-bps-grid",
            "10",
            "--cost-bps-grid",
            "20",
            "--cost-bps-grid",
            "50",
            "--min-split-count",
            "2",
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
    markdown = out_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["command"] == "strategy-feasibility"
    assert payload["report"] == json_payload["report"]
    assert payload["report"]["mode"] == "multi-hypothesis-lab"
    assert payload["report"]["uses_real_capital"] is False
    assert payload["report"]["live_order_routing"] is False
    assert payload["report"]["cost_bps_grid"] == [5.0, 10.0, 20.0, 50.0]
    assert [metric["candidate"] for metric in payload["report"]["candidate_metrics"]] == [
        "short_horizon_momentum_volatility_filter"
    ]
    metric = payload["report"]["candidate_metrics"][0]
    assert metric["readiness"] == "feasible"
    assert len(metric["cost_sensitivity"]) == 4
    assert len(metric["split_metrics"]) >= 2
    assert "Multi-Hypothesis Feasibility Lab" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown
    assert "short_horizon_momentum_volatility_filter" in markdown
    assert _record_snapshot(db_path) == before
    assert not memory_path.exists()


def test_strategy_feasibility_multi_hypothesis_cli_requires_memory_path(tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "multi-hypothesis.md"
    json_out = tmp_path / "multi-hypothesis.json"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "strategy-feasibility",
                "--db",
                str(db_path),
                "--mode",
                "multi-hypothesis-lab",
                "--symbol",
                "BTC/USDT",
                "--timeframe",
                "1h",
                "--out",
                str(out_path),
                "--json-out",
                str(json_out),
            ]
        )

    assert exc_info.value.code == 2


def test_strategy_feasibility_multi_hypothesis_cli_persists_candidate_state(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-memory.jsonl"
    out_path = tmp_path / "multi-hypothesis.md"
    json_out = tmp_path / "multi-hypothesis.json"
    _seed_directional_market_candles(db_path, count=120)
    ResearchDataStore(db_path).upsert_records(
        [_source_health("binance_public", "um_futures_ohlcv", START + timedelta(hours=119))]
    )

    exit_code = main(
        [
            "strategy-feasibility",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--persist-candidate-state",
            "--mode",
            "multi-hypothesis-lab",
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--candidate",
            "short_horizon_momentum_volatility_filter",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    stored = MemoryStore(memory_path).list_records()
    by_candidate = {
        record.opportunity["candidate_id"]: record for record in stored
    }

    assert exit_code == 0
    assert payload["candidate_state_memory_records"] == 5
    assert by_candidate["short_horizon_momentum_volatility_filter"].opportunity[
        "state"
    ] == "feasibility_passed"
    assert by_candidate["long_short_crowding_contrarian"].rejected_reasons == [
        "non_positive_cost_adjusted_expectancy"
    ]


def test_strategy_feasibility_large_liquid_cli_rejects_candidate_filter(tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "large-liquid.md"
    json_out = tmp_path / "large-liquid.json"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "strategy-feasibility",
                "--db",
                str(db_path),
                "--mode",
                "large-liquid-momentum-regime",
                "--symbol",
                "BTC/USDT",
                "--timeframe",
                "1h",
                "--candidate",
                "short_horizon_momentum_volatility_filter",
                "--out",
                str(out_path),
                "--json-out",
                str(json_out),
            ]
        )

    assert exc_info.value.code == 2


def test_strategy_feasibility_derivatives_cli_rejects_multi_hypothesis_candidate(tmp_path):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "derivatives.md"
    json_out = tmp_path / "derivatives.json"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "strategy-feasibility",
                "--db",
                str(db_path),
                "--mode",
                "derivatives-conditioned-lab",
                "--symbol",
                "BTC/USDT",
                "--timeframe",
                "1h",
                "--candidate",
                "short_horizon_momentum_volatility_filter",
                "--out",
                str(out_path),
                "--json-out",
                str(json_out),
            ]
        )

    assert exc_info.value.code == 2


def _seed_directional_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 2.0
            elif symbol == "ETH/USDT":
                close = 200.0 + index * 5.0
            else:
                close = 80.0 - index * 0.03
            records.append(_market_candle(symbol, index, close=close))
    ResearchDataStore(db_path).upsert_records(records)


def _market_candle(symbol: str, index: int, *, close: float) -> SourceRecord:
    return MarketCandle(
        source="binance_public",
        venue="binance_usdm",
        symbol=symbol,
        timestamp=START + timedelta(hours=index),
        timeframe="1h",
        open=close,
        high=close * 1.001,
        low=close * 0.999,
        close=close,
        volume=10_000.0 + index,
        suitability=DataSuitability(),
    ).to_source_record()


def _source_health(source: str, feed: str, observed_at: datetime) -> SourceRecord:
    return SourceRecord(
        record_id=f"{source}:{feed}:source_health:{observed_at.isoformat()}",
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "success": True,
            "attempts": 1,
            "failure": None,
            "observed_at": observed_at.isoformat(),
            "records_fetched": 1,
            "records_written": 1,
            "network_route": "direct",
        },
    )


def _record_snapshot(db_path) -> dict[str, dict[str, object]]:
    return {
        record.record_id: record.model_dump(mode="json")
        for record in ResearchDataStore(db_path).load_records()
    }
