from __future__ import annotations

import json
import sqlite3
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore


class FakeCcxtCollector:
    def __init__(
        self,
        *,
        bar_count: int = 72,
        funding_hours: tuple[int, ...] = (24, 32, 40, 48, 56),
    ) -> None:
        self.bar_count = bar_count
        self.funding_hours = funding_hours

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[MarketCandle]:
        del since, params
        start = datetime(2026, 5, 17, tzinfo=UTC)
        candles = []
        for index in range(self.bar_count):
            close = 100.0 + (index % 6)
            if index in self.funding_hours:
                close = 106.0
            if index - 1 in self.funding_hours:
                close = 100.0
            candles.append(
                MarketCandle(
                    source="ccxt",
                    venue="binance",
                    symbol=symbol,
                    timestamp=start + timedelta(hours=index),
                    timeframe=timeframe,
                    open=close,
                    high=close + 1.0,
                    low=close - 1.0,
                    close=close,
                    volume=1000.0 + index,
                )
            )
        return candles[:limit]

    def fetch_funding_rate_history(
        self,
        symbol: str,
        *,
        since: int | None = None,
        limit: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> list[FundingRateRecord]:
        del since, params
        start = datetime(2026, 5, 17, tzinfo=UTC)
        records = [
            FundingRateRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=hour),
                funding_rate=0.0008,
            )
            for hour in self.funding_hours
        ]
        return records[:limit]


def _invoke_json(args: list[str]) -> dict[str, Any]:
    stdout = StringIO()
    with redirect_stdout(stdout):
        exit_code = main(args)
    assert exit_code == 0, stdout.getvalue()
    return json.loads(stdout.getvalue())


def _sqlite_count(db_path: Path, table_name: str) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(f"select count(*) from {table_name}").fetchone()
    return int(row[0])


def _memory_records(memory_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in memory_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _has_memory_tag_or_prefix(
    records: list[dict[str, Any]],
    value: str,
) -> bool:
    return any(
        value in record.get("tags", [])
        or str(record.get("record_id", "")).startswith(value)
        for record in records
    )


def _payload_has_truthy_key(payload: Any, keys: set[str]) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and bool(value):
                return True
            if _payload_has_truthy_key(value, keys):
                return True
    if isinstance(payload, list):
        return any(_payload_has_truthy_key(item, keys) for item in payload)
    return False


def _assert_payload_is_safe(payload: dict[str, Any]) -> None:
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False


def _seed_degraded_family(memory_path: Path, strategy_family: str) -> None:
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id=f"degraded:{strategy_family}",
            opportunity={"strategy_family": strategy_family},
            rejected_reasons=["degraded_expectancy"],
            tags=[strategy_family, "degraded_expectancy"],
        )
    )


def test_complete_safe_autonomous_evidence_system(tmp_path, monkeypatch):
    """Proves full local acceptance plus focused source-test coverage.

    Focused source support remains covered by:
    test_binance_public_ingestion.py, test_ccxt_ingestion_service.py,
    test_defillama_dex_ingestion_service.py, and
    test_onchain_ingestion_service.py for Binance Public Data, CCXT,
    DexScreener, DefiLlama, Dune, and TheGraph.
    """
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    daily_path = tmp_path / "daily.md"
    weekly_path = tmp_path / "weekly.md"
    rollout_path = tmp_path / "rollout.json"
    evidence_package_path = tmp_path / "rollout-evidence-package.json"

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda _exchange_id: FakeCcxtCollector(),
    )

    run_result = _invoke_json(
        [
            "evidence-run",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--report-out",
            str(daily_path),
            "--current-capital-usd",
            "300",
            "--allow-network",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--limit",
            "200",
            "--include-dune",
            "--include-thegraph",
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--strategy-family",
            "funding_mean_reversion_after_extreme",
        ]
    )

    research_result = _invoke_json(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--include-validation",
            "--include-paper-evidence",
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

    degraded_family = "funding_mean_reversion_after_extreme"
    _seed_degraded_family(memory_path, degraded_family)

    planner_result = _invoke_json(
        [
            "plan-experiments",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--current-capital-usd",
            "300",
            "--max-proposals",
            "3",
        ]
    )

    report_result = _invoke_json(
        [
            "evidence-report",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--weekly",
            "--out",
            str(weekly_path),
        ]
    )

    rollout_result = _invoke_json(
        [
            "rollout-review",
            "--db",
            str(db_path),
            "--strategy-family",
            "funding_extremity_price_confirmation",
            "--artifact-out",
            str(rollout_path),
            "--evidence-package-out",
            str(evidence_package_path),
        ]
    )

    for payload in [
        run_result,
        research_result,
        planner_result,
        report_result,
        rollout_result,
    ]:
        _assert_payload_is_safe(payload)

    assert run_result["command"] == "evidence-run"
    assert run_result["memory_records_written"] > 0
    assert run_result["daily_report_out"] == str(daily_path)
    assert isinstance(run_result["steps"], list)
    assert "research_milestone" not in run_result
    assert "source_health" not in run_result

    runner_report = run_result["report"]
    assert runner_report["uses_real_capital"] is False
    assert runner_report["live_order_routing"] is False
    for key in [
        "signal_count",
        "anomaly_count",
        "hypothesis_count",
        "reflection_count",
        "accept_reject_reason_count",
    ]:
        assert runner_report["research_milestone"][key] > 0

    source_health = runner_report["source_health"]
    assert source_health["optional_source_skipped"] >= 0
    assert source_health["optional_source_failures"] >= 0
    health_by_source = {item["source"]: item for item in source_health["items"]}
    for optional_source in ["dune", "thegraph"]:
        assert optional_source in health_by_source
        assert health_by_source[optional_source]["status"] in {
            "skipped",
            "not_configured",
        }
        assert health_by_source[optional_source]["reason_code"] in {
            "missing_config",
            "not_configured",
        }

    assert _sqlite_count(db_path, "source_records") > 0
    assert _sqlite_count(db_path, "validation_evidence") > 0
    assert _sqlite_count(db_path, "paper_outcomes") > 0

    records = _memory_records(memory_path)
    assert _has_memory_tag_or_prefix(records, "research-loop")
    assert _has_memory_tag_or_prefix(records, "validation-evidence")
    assert any(
        "validation-evidence" in record.get("tags", [])
        and (record.get("hypothesis") or {}).get("lesson")
        for record in records
    )
    assert _has_memory_tag_or_prefix(records, "paper-evidence")
    assert _has_memory_tag_or_prefix(records, "experiment-proposal")

    assert planner_result["current_capital_usd"] == 300.0
    assert degraded_family in planner_result["degraded_strategy_families"]
    proposed_families = {
        proposal["strategy_family"] for proposal in planner_result["proposals"]
    }
    assert degraded_family not in proposed_families
    for proposal in planner_result["proposals"]:
        assert proposal["uses_real_capital"] is False
        assert proposal["live_order_routing"] is False
        assert proposal["max_notional_usd"] <= 25.0
        assert not _payload_has_truthy_key(
            proposal,
            {
                "requires_speed_edge",
                "speed_edge",
                "requires_low_latency",
                "requires_premium_rpc",
            },
        )

    assert daily_path.exists()
    assert daily_path.read_text(encoding="utf-8").startswith(
        "# Daily Evidence Report"
    )
    assert report_result["weekly_report_out"] == str(weekly_path)
    assert weekly_path.exists()
    assert weekly_path.read_text(encoding="utf-8").startswith(
        "# Weekly Evidence Report"
    )

    assert rollout_result["decision"] == "blocked"
    assert "insufficient_sample_size" in rollout_result["blocked_reasons"]
    assert rollout_result["rollout_evaluation"]["observation_count"] < 30
    assert rollout_result["max_observed_loss_usd"] >= 0
    assert rollout_result["evidence_package_out"] == str(evidence_package_path)
    assert evidence_package_path.exists()
    persisted_package = json.loads(
        evidence_package_path.read_text(encoding="utf-8")
    )
    assert persisted_package["strategy_family"] == (
        "funding_extremity_price_confirmation"
    )
    assert persisted_package["evidence_package_path"] == str(evidence_package_path)
