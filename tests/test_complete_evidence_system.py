from __future__ import annotations

import json
import re
import socket
import sqlite3
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
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


def _assert_recursive_payload_is_safe(payload: Any, path: str = "payload") -> None:
    forbidden_truthy_keys = {
        "uses_real_capital",
        "live_order_routing",
        "touched_real_capital",
        "requires_speed_edge",
        "requires_low_latency",
        "requires_premium_rpc",
        "premium_rpc_required",
        "private_rpc_required",
    }
    forbidden_string_patterns = [
        r"akia[0-9a-z]{16}",
        r"sk-[0-9a-z_-]{20,}",
        r"-----begin [a-z ]*private key-----",
        r"\bcreate_order\b",
        r"\bsend_transaction\b",
        r"private_key\s*[:=]",
        r"seed_phrase\s*[:=]",
        r"unexpected network",
    ]

    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}"
            if key in forbidden_truthy_keys:
                assert value is False or value in (None, 0), next_path
            if key in {"max_notional_usd", "notional_usd"} and value is not None:
                assert float(value) <= 25.0, next_path
            _assert_recursive_payload_is_safe(value, next_path)
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            _assert_recursive_payload_is_safe(item, f"{path}[{index}]")
        return
    if isinstance(payload, str):
        lowered = payload.lower()
        for pattern in forbidden_string_patterns:
            assert re.search(pattern, lowered) is None, path


def _assert_text_artifact_is_safe(text: str) -> None:
    lowered = text.lower()
    assert "live_execution_enabled: true" not in lowered
    assert "uses_real_capital: true" not in lowered
    assert "live_order_routing: true" not in lowered
    assert "create_order" not in lowered
    assert "send_transaction" not in lowered


def _block_unexpected_network(monkeypatch) -> None:
    def blocked_socket(*_args, **_kwargs):
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(socket, "socket", blocked_socket)


def _seed_degraded_family(memory_path: Path, strategy_family: str) -> None:
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id=f"degraded:{strategy_family}",
            opportunity={"strategy_family": strategy_family},
            rejected_reasons=["degraded_expectancy"],
            tags=[strategy_family, "degraded_expectancy"],
        )
    )


def _seed_blocked_parameter_set(
    memory_path: Path,
    strategy_family: str,
    parameters: dict[str, Any],
) -> None:
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id=f"blocked-params:{strategy_family}:baseline",
            opportunity={
                "strategy_family": strategy_family,
                "parameter_changes": parameters,
            },
            rejected_reasons=["blocked", "insufficient_walk_forward_splits"],
            tags=[strategy_family, "blocked"],
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
    governance_path = tmp_path / "governance.md"
    rollout_path = tmp_path / "rollout.json"
    evidence_package_path = tmp_path / "rollout-evidence-package.json"

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda _exchange_id: FakeCcxtCollector(),
    )
    _block_unexpected_network(monkeypatch)

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

    def _configured_optional_failure(*_args, **_kwargs):
        raise RuntimeError("configured optional failure")

    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.ingest_dune_query_result",
        _configured_optional_failure,
    )
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.ingest_thegraph_query_result",
        _configured_optional_failure,
    )
    failure_db_path = tmp_path / "optional-failure.sqlite"
    failure_memory_path = tmp_path / "optional-failure-memory.jsonl"
    failure_daily_path = tmp_path / "optional-failure-daily.md"
    optional_failure_result = _invoke_json(
        [
            "evidence-run",
            "--db",
            str(failure_db_path),
            "--memory",
            str(failure_memory_path),
            "--report-out",
            str(failure_daily_path),
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
            "--dune-query-id",
            "123456",
            "--dune-api-key",
            "[REDACTED]",
            "--include-thegraph",
            "--subgraph-url",
            "https://example.test/subgraph",
            "--graph-query",
            "{ pools { id } }",
            "--strategy-family",
            "funding_extremity_price_confirmation",
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
    blocked_parameters = {"threshold_abs": 0.0005, "hold_bars": 1}
    _seed_blocked_parameter_set(
        memory_path,
        "funding_extremity_price_confirmation",
        blocked_parameters,
    )

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

    governance_result = _invoke_json(
        [
            "governance-report",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--out",
            str(governance_path),
            "--current-capital-usd",
            "300",
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
        governance_result,
        rollout_result,
        optional_failure_result,
    ]:
        _assert_payload_is_safe(payload)
        _assert_recursive_payload_is_safe(payload)

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
    assert source_health["optional_source_skipped"] >= 2
    assert source_health["optional_source_failures"] == 0
    health_by_key = {
        (item["source"], item["feed"]): item for item in source_health["items"]
    }
    for feed in ["ohlcv", "funding_rate_history"]:
        item = health_by_key[("ccxt", feed)]
        assert item["status"] == "success"
        assert item["records_written"] > 0
    for optional_source in ["dune", "thegraph"]:
        feed = "dune_query_result" if optional_source == "dune" else "thegraph_query_result"
        item = health_by_key[(optional_source, feed)]
        assert item["status"] in {
            "skipped",
            "not_configured",
        }
        assert item["reason_code"] in {
            "missing_config",
            "not_configured",
        }

    failure_health = optional_failure_result["report"]["source_health"]
    failure_health_by_key = {
        (item["source"], item["feed"]): item for item in failure_health["items"]
    }
    assert failure_health["optional_source_failures"] == 2
    for key in [("dune", "dune_query_result"), ("thegraph", "thegraph_query_result")]:
        item = failure_health_by_key[key]
        assert item["status"] == "failure"
        assert item["reason_code"] == "optional_source_failed"
        assert "configured optional failure" in item["failure"]

    assert research_result["command"] == "research-loop"
    assert research_result["memory_records_written"] > 0
    assert research_result["validation_memory_records_written"] > 0
    research_report = research_result["report"]
    assert research_report["loaded_records"] > 0
    assert research_report["signal_count"] > 0
    assert research_report["validation_summaries"]
    assert research_report["paper_evidence_packages"]

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
    assert planner_result["accepted"] is True
    assert planner_result["proposals"]
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
        assert proposal["parameter_changes"] != blocked_parameters

    assert daily_path.exists()
    daily_text = daily_path.read_text(encoding="utf-8")
    assert daily_text.startswith("# Daily Evidence Report")
    for section in [
        "## Safety",
        "## Decision",
        "## Strategy Families",
        "## Paper Outcomes",
        "## Validation Evidence",
        "## Next Experiments",
    ]:
        assert section in daily_text
    _assert_text_artifact_is_safe(daily_text)
    assert report_result["weekly_report_out"] == str(weekly_path)
    weekly_report = report_result["report"]
    assert weekly_report["family_summaries"]
    assert weekly_report["sample_size_progress"]
    assert weekly_path.exists()
    weekly_text = weekly_path.read_text(encoding="utf-8")
    assert weekly_text.startswith("# Weekly Evidence Report")
    for section in [
        "## Safety",
        "## Decision",
        "## Strategy Families",
        "## Sample Size Progress Toward 30",
    ]:
        assert section in weekly_text
    _assert_text_artifact_is_safe(weekly_text)

    assert governance_result["command"] == "governance-report"
    assert governance_result["governance_report_out"] == str(governance_path)
    governance_report = governance_result["report"]
    assert governance_report["family_scoreboard"]
    assert governance_report["profit_reviews"]
    assert "monthly_owner_review" in governance_report
    assert governance_report["uses_real_capital"] is False
    assert governance_report["live_order_routing"] is False
    assert governance_path.exists()
    governance_text = governance_path.read_text(encoding="utf-8")
    assert governance_text.startswith("# Profit Governance Report")
    for section in [
        "## Safety",
        "## Weekly Family Scoreboard",
        "## Profit Review",
        "## Stopped-Family Ledger",
        "## Paper-Only Portfolio Selector",
        "## Monthly Owner Review",
    ]:
        assert section in governance_text
    _assert_text_artifact_is_safe(governance_text)

    assert rollout_result["decision"] == "blocked"
    assert "insufficient_sample_size" in rollout_result["blocked_reasons"]
    assert rollout_result["rollout_evaluation"]["observation_count"] < 30
    assert rollout_result["max_observed_loss_usd"] >= 0
    assert rollout_result["evidence_package_out"] == str(evidence_package_path)
    assert rollout_path.exists()
    readiness_artifact = json.loads(rollout_path.read_text(encoding="utf-8"))
    assert readiness_artifact == rollout_result["readiness_artifact"]
    assert readiness_artifact["ready_for_human_review"] is False
    assert readiness_artifact["live_execution_enabled"] is False
    assert readiness_artifact["max_notional_usd"] <= 25.0
    assert readiness_artifact["max_daily_loss_usd"] <= 10.0
    assert evidence_package_path.exists()
    persisted_package = json.loads(
        evidence_package_path.read_text(encoding="utf-8")
    )
    assert persisted_package == rollout_result["evidence_package"]
    assert persisted_package["strategy_family"] == (
        "funding_extremity_price_confirmation"
    )
    assert persisted_package["evidence_package_path"] == str(evidence_package_path)
    assert persisted_package["validation_evidence_ids"]
    assert persisted_package["paper_outcome_ids"]
    assert persisted_package["sample_size"] >= persisted_package["closed_count"]
    assert persisted_package["max_observed_loss_usd"] == rollout_result["max_observed_loss_usd"]

    paper_outcomes = PaperOutcomeLedger(db_path).load_outcomes()
    assert paper_outcomes
    for outcome in paper_outcomes:
        assert outcome.touched_real_capital is False
        assert outcome.live_order_routing is False
        assert outcome.notional_usd <= 25.0

    for artifact in [readiness_artifact, persisted_package, records]:
        _assert_recursive_payload_is_safe(artifact)
