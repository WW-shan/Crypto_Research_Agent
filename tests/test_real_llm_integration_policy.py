from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import (
    FundingRateRecord,
    MarketCandle,
    OpenInterestRecord,
    SourceRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryStore
from llm_integration_policy import (
    assert_no_raw_response_payload,
    assert_no_secret_leaks,
    assert_research_only_payload,
    configured_llm_settings_or_fail,
    run_real_llm_cli_or_fail,
)


STRATEGY_FAMILY = "funding_extremity_price_confirmation"


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_plan_experiments_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("planning")
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ValidationEvidenceLedger(db_path).upsert_evidence([_validation()])

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(
            [
                "plan-experiments",
                "--db",
                str(db_path),
                "--memory",
                str(memory_path),
                "--strategy-family",
                STRATEGY_FAMILY,
                "--max-proposals",
                "1",
                "--current-capital-usd",
                "90",
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    memory_text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""

    assert exit_code == 0
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_role"] == "planning"
    assert payload["accepted"] is True, payload["rejected_reason_codes"]
    assert payload["proposals"]
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
            "memory_jsonl": memory_text,
        },
        path_surfaces=[memory_path],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_research_loop_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("research")
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ResearchDataStore(db_path).upsert_records([_market_candle().to_source_record()])

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(
            [
                "research-loop",
                "--db",
                str(db_path),
                "--memory",
                str(memory_path),
                "--run-id",
                "real-llm-policy-research",
                "--current-capital-usd",
                "300",
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    memory_records = [record.model_dump(mode="json") for record in MemoryStore(memory_path).list_records()]

    assert exit_code == 0
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_role"] == "research"
    assert payload["llm_research_result"]["accepted"] is True, payload["llm_research_result"]
    assert payload["llm_research_result"]["raw_response_metadata"]["raw_response_omitted"] is True
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_raw_response_payload(memory_records)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
            "memory_jsonl": memory_path.read_text(encoding="utf-8"),
        },
        path_surfaces=[memory_path],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_evidence_report_cli_uses_fast_summary_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("summary")
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_path = tmp_path / "daily.md"
    ValidationEvidenceLedger(db_path).upsert_evidence([_validation()])

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(
            [
                "evidence-report",
                "--daily",
                "--db",
                str(db_path),
                "--memory",
                str(memory_path),
                "--out",
                str(report_path),
                "--strategy-family",
                STRATEGY_FAMILY,
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    markdown = report_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_role"] == "summary"
    assert payload["llm_summary_accepted"] is True, payload["llm_summary_rejected_reason_codes"]
    assert payload["report"]["validation_evidence_count"] == 1
    assert "## LLM Narrative Summary" in markdown
    assert "Validation evidence: 1" in markdown
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
            "report_markdown": markdown,
        },
        path_surfaces=[report_path],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_llm_health_check_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = configured_llm_settings_or_fail("research")

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(["llm-health-check"]),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    _assert_real_llm_payload(payload, role="research")
    assert payload["health"]["schema_name"] == "LLMHealthCheckResult"
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
        },
        path_surfaces=[],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_source_probe_list_targets_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = configured_llm_settings_or_fail("research")

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(["source-probe", "--list-targets"]),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    _assert_real_llm_payload(payload, role="research")
    assert payload["llm_judgement"]["schema_name"] == "SourceResearchJudgement"
    assert payload["targets"]
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
        },
        path_surfaces=[],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_ingest_offline_check_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("research")
    db_path = tmp_path / "research.sqlite"

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(["ingest", "--offline-check", "--db", str(db_path)]),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    _assert_real_llm_payload(payload, role="research")
    assert payload["llm_judgement"]["schema_name"] == "DataReadinessJudgement"
    assert payload["mode"] == "offline_check"
    assert db_path.exists()
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
        },
        path_surfaces=[db_path],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_governance_report_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("summary")
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    out = tmp_path / "governance.md"
    ResearchDataStore(db_path)

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(
            [
                "governance-report",
                "--db",
                str(db_path),
                "--memory",
                str(memory_path),
                "--out",
                str(out),
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    markdown = out.read_text(encoding="utf-8")

    assert exit_code == 0
    _assert_real_llm_payload(payload, role="summary")
    assert payload["llm_judgement"]["schema_name"] == "RuntimeCommandJudgement"
    assert markdown.startswith("# Profit Governance Report")
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
            "report_markdown": markdown,
        },
        path_surfaces=[out, memory_path],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_historical_bootstrap_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("summary")
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    out = tmp_path / "bootstrap.md"
    json_out = tmp_path / "bootstrap.json"
    manifest_out = tmp_path / "bootstrap.manifest.json"
    _seed_bootstrap_fixture(db_path)

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(
            [
                "historical-bootstrap",
                "--db",
                str(db_path),
                "--memory",
                str(memory_path),
                "--out",
                str(out),
                "--json-out",
                str(json_out),
                "--manifest-out",
                str(manifest_out),
                "--run-id",
                "real-llm-policy-bootstrap",
                "--price-symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
                "--timeframe",
                "1h",
                "--bootstrap-window",
                "2026-03-01/2026-04-01",
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    markdown = out.read_text(encoding="utf-8")
    json_payload = json.loads(json_out.read_text(encoding="utf-8"))

    assert exit_code == 0
    _assert_real_llm_payload(payload, role="summary")
    assert payload["llm_judgement"]["schema_name"] == "BootstrapInterpretation"
    assert json_payload["llm_judgement"]["schema_name"] == "BootstrapInterpretation"
    assert markdown.startswith("# Phase 7 Historical Bootstrap Report")
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
            "json_artifact": json.dumps(json_payload, sort_keys=True),
            "report_markdown": markdown,
        },
        path_surfaces=[out, json_out, manifest_out, memory_path],
        settings=settings,
    )


@pytest.mark.integration
@pytest.mark.llm_integration
@pytest.mark.core_acceptance
def test_real_rollout_review_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_fail("summary")
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)

    exit_code = run_real_llm_cli_or_fail(
        lambda: main(
            [
                "rollout-review",
                "--db",
                str(db_path),
                "--strategy-family",
                STRATEGY_FAMILY,
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    _assert_real_llm_payload(payload, role="summary")
    assert payload["llm_judgement"]["schema_name"] == "RolloutReadinessNarrative"
    assert payload["decision"] == "blocked"
    assert_research_only_payload(payload)
    assert_no_raw_response_payload(payload)
    assert_no_secret_leaks(
        text_surfaces={
            "stdout": captured.out,
            "stderr": captured.err,
            "payload_json": json.dumps(payload, sort_keys=True),
        },
        path_surfaces=[db_path],
        settings=settings,
    )


def _assert_real_llm_payload(payload: dict[str, object], *, role: str) -> None:
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_role"] == role


def _validation() -> ValidationEvidence:
    return ValidationEvidence(
        run_id="real-llm-policy-validation",
        strategy_family=STRATEGY_FAMILY,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price_confirmation",
        trade_count=12,
        net_return=0.03,
        gross_expectancy=0.003,
        fee_adjusted_expectancy=0.001,
        slippage_adjusted_expectancy=0.0005,
        max_drawdown=0.01,
        walk_forward_split_count=3,
        walk_forward_pass_rate=0.67,
        approved=True,
        blocked_reasons=[],
    )


def _market_candle() -> MarketCandle:
    return MarketCandle(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=datetime(2026, 5, 16, tzinfo=UTC),
        timeframe="1h",
        open=100.0,
        high=110.0,
        low=99.0,
        close=108.0,
        volume=1000.0,
    )


def _seed_bootstrap_fixture(db_path) -> None:
    store = ResearchDataStore(db_path)
    start = datetime(2026, 3, 1, tzinfo=UTC)
    closes = [100, 103, 101, 99, 102, 104, 101, 100, 98, 101]
    candles = [
        _candle_at(start + timedelta(hours=index), close)
        for index, close in enumerate(closes)
    ]
    fundings = [
        _funding_at(start + timedelta(hours=1), 0.0008),
        _funding_at(start + timedelta(hours=4), -0.0009),
        _funding_at(start + timedelta(hours=6), 0.0007),
    ]
    open_interest = [
        _open_interest_at(start + timedelta(hours=hour), 1000.0 + 100.0 * index)
        for index, hour in enumerate((0, 1, 4, 6))
    ]
    store.upsert_records([item.to_source_record() for item in candles])
    store.upsert_records([_funding_record(item) for item in fundings])
    store.upsert_records([item.to_source_record() for item in open_interest])


def _candle_at(timestamp: datetime, close: float) -> MarketCandle:
    return MarketCandle(
        source="binance_public",
        venue="binance",
        symbol="BTC/USDT",
        timestamp=timestamp,
        timeframe="1h",
        open=close,
        high=close + 1.0,
        low=max(close - 1.0, 0.0),
        close=close,
        volume=1000.0,
    )


def _funding_at(timestamp: datetime, rate: float) -> FundingRateRecord:
    return FundingRateRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=timestamp,
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


def _open_interest_at(timestamp: datetime, value: float) -> OpenInterestRecord:
    return OpenInterestRecord(
        source="ccxt",
        venue="binance",
        symbol="BTC/USDT:USDT",
        timestamp=timestamp,
        timeframe="1h",
        open_interest=value,
        open_interest_value=value * 100.0,
    )
