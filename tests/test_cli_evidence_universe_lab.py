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


def test_evidence_universe_lab_cli_runs_data_depth_and_feasibility_v2(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-state.jsonl"
    out_dir = tmp_path / "lab"
    json_out = tmp_path / "lab-summary.json"
    _seed_directional_market_candles(db_path, count=120)
    ResearchDataStore(db_path).upsert_records(
        [_source_health("binance_public", "um_futures_ohlcv", START + timedelta(hours=119))]
    )

    exit_code = main(
        [
            "evidence-universe-lab",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--symbol",
            "BTC/USDT",
            "--symbol",
            "ETH/USDT",
            "--symbol",
            "SOL/USDT",
            "--timeframe",
            "1h",
            "--start-year",
            "2026",
            "--start-month",
            "5",
            "--end-year",
            "2026",
            "--end-month",
            "5",
            "--min-unique-months",
            "1",
            "--min-asset-count",
            "1",
            "--min-split-count",
            "2",
            "--purge-gap-bars",
            "2",
            "--candidate",
            "short_horizon_momentum_volatility_filter",
            "--out-dir",
            str(out_dir),
            "--json-out",
            str(json_out),
            "--persist-candidate-state",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = (out_dir / "evidence-universe-lab.md").read_text(encoding="utf-8")
    memory_records = MemoryStore(memory_path).list_records()

    assert exit_code == 0
    assert payload == json_payload
    assert payload["command"] == "evidence-universe-lab"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["report"]["data_depth_readiness"] == "ready"
    assert payload["report"]["feasibility_version"] == "v2"
    assert payload["report"]["purge_gap_bars"] == 2
    assert payload["report"]["candidate_count"] == 1
    assert payload["report"]["candidate_state_memory_records"] == 5
    assert payload["artifacts"]["data_depth_markdown"].endswith("data-depth-campaign.md")
    assert payload["artifacts"]["feasibility_markdown"].endswith("multi-hypothesis-feasibility.md")
    assert (out_dir / "data-depth-campaign.md").exists()
    assert (out_dir / "data-depth-campaign.json").exists()
    assert (out_dir / "multi-hypothesis-feasibility.md").exists()
    assert (out_dir / "multi-hypothesis-feasibility.json").exists()
    assert "Evidence Universe Lab" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown
    assert len(memory_records) == 5


def test_evidence_universe_lab_cli_rejects_collect_without_allow_network(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "evidence-universe-lab",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--memory",
                str(tmp_path / "candidate-state.jsonl"),
                "--symbol",
                "BTC/USDT",
                "--timeframe",
                "1h",
                "--start-year",
                "2026",
                "--start-month",
                "5",
                "--end-year",
                "2026",
                "--end-month",
                "5",
                "--collect",
                "--out-dir",
                str(tmp_path / "lab"),
                "--json-out",
                str(tmp_path / "lab-summary.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_evidence_universe_lab_cli_threads_cost_aware_universe_options(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "candidate-state.jsonl"
    out_dir = tmp_path / "lab-cost-aware"
    json_out = tmp_path / "lab-cost-aware-summary.json"
    _seed_directional_market_candles(db_path, count=120)
    ResearchDataStore(db_path).upsert_records(
        [_source_health("binance_public", "um_futures_ohlcv", START + timedelta(hours=119))]
    )

    exit_code = main(
        [
            "evidence-universe-lab",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--universe-preset",
            "liquid-usdm-top20",
            "--max-symbols",
            "3",
            "--timeframe",
            "1h",
            "--start-year",
            "2026",
            "--start-month",
            "5",
            "--end-year",
            "2026",
            "--end-month",
            "5",
            "--min-unique-months",
            "1",
            "--min-asset-count",
            "1",
            "--min-split-count",
            "2",
            "--candidate",
            "short_horizon_momentum_volatility_filter",
            "--cost-aware-execution",
            "--min-edge-over-cost-multiplier",
            "2",
            "--max-turnover",
            "0.5",
            "--out-dir",
            str(out_dir),
            "--json-out",
            str(json_out),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    feasibility_payload = json.loads(
        (out_dir / "multi-hypothesis-feasibility.json").read_text(encoding="utf-8")
    )
    data_depth_payload = json.loads(
        (out_dir / "data-depth-campaign.json").read_text(encoding="utf-8")
    )
    policy = feasibility_payload["report"]["validation_policy"]
    assert exit_code == 0
    assert payload["report"]["candidate_count"] == 1
    assert data_depth_payload["report"]["spec"]["symbols"] == [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
    ]
    assert feasibility_payload["report"]["symbols"] == [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
    ]
    assert policy["cost_aware_execution"] is True
    assert policy["min_edge_over_cost_multiplier"] == 2.0
    assert policy["max_turnover"] == 0.5


def _seed_directional_market_candles(db_path, *, count: int) -> None:
    records = []
    for symbol in SYMBOLS:
        for index in range(count):
            if symbol == "BTC/USDT":
                close = 100.0 + index * 2.0
            elif symbol == "ETH/USDT":
                close = 100.0 + index * 1.0
            else:
                close = 100.0 - index * 0.1
            records.append(
                MarketCandle(
                    source="binance_public",
                    venue="binance_usdm",
                    symbol=symbol,
                    timestamp=START + timedelta(hours=index),
                    timeframe="1h",
                    open=close - 0.5,
                    high=close + 1.0,
                    low=close - 1.0,
                    close=close,
                    volume=1000.0 + index,
                    suitability=DataSuitability(
                        min_capital_usd=25.0,
                        latency_dependency="low",
                        rpc_dependency="none",
                        execution_role="research_and_paper",
                    ),
                ).to_source_record()
            )
    ResearchDataStore(db_path).upsert_records(records)


def _source_health(source: str, feed: str, observed_at: datetime) -> SourceRecord:
    return SourceRecord(
        record_id=f"health:{source}:{feed}",
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "status": "success",
            "records_written": 1,
            "network_route": "direct",
            "uses_real_capital": False,
            "live_order_routing": False,
        },
    )
