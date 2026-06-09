from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import DataSuitability, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore


class FakePublicSummary:
    def __init__(self, *, symbol: str, year: int, month: int, records_written: int) -> None:
        self.symbol = symbol
        self.year = year
        self.month = month
        self.records_written = records_written

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {
            "source": "binance_public",
            "db_path": "test.sqlite",
            "symbols": [self.symbol],
            "timeframe": "1h",
            "year": self.year,
            "month": self.month,
            "records_fetched": self.records_written,
            "records_written": self.records_written,
            "network_allowed": True,
            "uses_real_capital": False,
            "live_order_routing": False,
            "notes": ["research_and_paper_validation_only", "market=um_futures"],
        }


def test_data_depth_campaign_cli_writes_plan_markdown_and_json(
    capsys,
    tmp_path,
):
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "data-depth.md"
    json_out = tmp_path / "data-depth.json"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", datetime(2026, 1, 1, tzinfo=UTC)),
            _market_candle("BTC/USDT", datetime(2026, 3, 1, tzinfo=UTC)),
        ]
    )

    exit_code = main(
        [
            "data-depth-campaign",
            "--db",
            str(db_path),
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--start-year",
            "2026",
            "--start-month",
            "1",
            "--end-year",
            "2026",
            "--end-month",
            "3",
            "--min-unique-months",
            "3",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = out_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["command"] == "data-depth-campaign"
    assert payload["report"] == json_payload["report"]
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["report"]["readiness"] == "blocked"
    assert payload["report"]["reason_codes"] == ["insufficient_month_coverage"]
    assert payload["report"]["coverage"][0]["unique_months"] == 2
    assert len(payload["report"]["missing_collection_jobs"]) == 1
    assert "Data Depth Campaign" in markdown
    assert "BTC/USDT" in markdown
    assert "insufficient_month_coverage" in markdown


def test_data_depth_campaign_cli_rejects_collect_without_allow_network(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "data-depth-campaign",
                "--db",
                str(tmp_path / "research.sqlite"),
                "--symbol",
                "BTCUSDT",
                "--timeframe",
                "1h",
                "--start-year",
                "2026",
                "--start-month",
                "1",
                "--end-year",
                "2026",
                "--end-month",
                "1",
                "--collect",
                "--out",
                str(tmp_path / "data-depth.md"),
                "--json-out",
                str(tmp_path / "data-depth.json"),
            ]
        )

    assert exc_info.value.code == 2


def test_data_depth_campaign_cli_collects_missing_jobs_and_records_failures(
    capsys,
    monkeypatch,
    tmp_path,
):
    calls = []

    def fake_ingest(db_path, **kwargs):
        calls.append((db_path, kwargs))
        if kwargs["month"] == 2:
            raise RuntimeError("source timeout")
        return FakePublicSummary(
            symbol=kwargs["symbol"],
            year=kwargs["year"],
            month=kwargs["month"],
            records_written=744,
        )

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.ingest_binance_public_um_futures_month",
        fake_ingest,
        raising=False,
    )
    db_path = tmp_path / "research.sqlite"
    out_path = tmp_path / "data-depth.md"
    json_out = tmp_path / "data-depth.json"

    exit_code = main(
        [
            "data-depth-campaign",
            "--db",
            str(db_path),
            "--symbol",
            "BTCUSDT",
            "--timeframe",
            "1h",
            "--start-year",
            "2026",
            "--start-month",
            "1",
            "--end-year",
            "2026",
            "--end-month",
            "2",
            "--min-unique-months",
            "1",
            "--collect",
            "--allow-network",
            "--out",
            str(out_path),
            "--json-out",
            str(json_out),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    jobs = payload["report"]["collection_results"]
    assert exit_code == 0
    assert len(calls) == 2
    assert calls[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "year": 2026,
        "month": 1,
        "allow_network": True,
    }
    assert [job["status"] for job in jobs] == ["succeeded", "failed"]
    assert jobs[0]["records_written"] == 744
    assert jobs[1]["error"] == "source timeout"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert "source timeout" in out_path.read_text(encoding="utf-8")


def _market_candle(symbol: str, timestamp: datetime):
    return MarketCandle(
        source="binance_public",
        venue="binance_usdm",
        symbol=symbol,
        timestamp=timestamp,
        timeframe="1h",
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
        suitability=DataSuitability(
            min_capital_usd=25.0,
            latency_dependency="low",
            rpc_dependency="none",
            execution_role="research_and_paper",
        ),
    ).to_source_record()
