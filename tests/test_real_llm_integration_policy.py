from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryStore
from llm_integration_policy import (
    assert_no_raw_response_payload,
    assert_no_secret_leaks,
    assert_research_only_payload,
    configured_llm_settings_or_skip,
    enable_real_llm_cli_for_pytest,
    run_real_llm_cli_or_fail,
)


STRATEGY_FAMILY = "funding_extremity_price_confirmation"


@pytest.mark.integration
@pytest.mark.llm_integration
def test_real_plan_experiments_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_skip("planning")
    enable_real_llm_cli_for_pytest(monkeypatch)
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
                "--no-offline-only",
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    memory_text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""

    assert exit_code == 0
    assert payload["llm_used"] is True
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
def test_real_research_loop_cli_uses_configured_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_skip("research")
    enable_real_llm_cli_for_pytest(monkeypatch)
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
                "--no-offline-only",
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    memory_records = [record.model_dump(mode="json") for record in MemoryStore(memory_path).list_records()]

    assert exit_code == 0
    assert payload["llm_used"] is True
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
def test_real_evidence_report_cli_uses_fast_summary_llm_without_secret_leaks(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    settings = configured_llm_settings_or_skip("summary")
    enable_real_llm_cli_for_pytest(monkeypatch)
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
                "--no-offline-only",
            ]
        ),
        capsys=capsys,
        settings=settings,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    markdown = report_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["llm_used"] is True
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
