from __future__ import annotations

import json
from datetime import UTC, datetime

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.expansion_preparation import build_expansion_preparation_report
from crypto_alpha_agent.pipeline.markdown import render_expansion_preparation_markdown


def _source_health_record(
    source: str,
    feed: str,
    *,
    success: bool = True,
    records_written: int = 1,
) -> SourceRecord:
    observed_at = datetime(2026, 5, 23, tzinfo=UTC)
    return SourceRecord(
        record_id=f"{source}:{feed}:source_health:{observed_at.isoformat()}",
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "success": success,
            "attempts": 1,
            "failure": None if success else "provider unavailable",
            "observed_at": observed_at.isoformat(),
            "records_fetched": records_written,
            "records_written": records_written,
            "network_route": "direct",
        },
    )


def test_expansion_preparation_report_prioritizes_sources_and_fails_closed_without_health(tmp_path):
    report = build_expansion_preparation_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )

    source_ids = [source.source_id for source in report.source_candidates]
    assert source_ids[:3] == [
        "binance_usdm_open_interest",
        "binance_usdm_open_interest_history",
        "coinalyze_derivatives_history",
    ]
    assert report.source_candidates[0].readiness == "needs_source_probe"
    assert report.source_candidates[0].blocked_reasons == [
        "source_health_missing",
        "source_probe_required",
    ]
    assert report.source_candidates[2].credential_requirement == "required_api_key"
    assert "credential_required" in report.source_candidates[2].blocked_reasons
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_expansion_preparation_report_uses_registry_weekly_actions_and_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _source_health_record("dexscreener", "pairs"),
            _source_health_record("defillama", "yield_pools"),
        ]
    )

    report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )
    sources = {source.source_id: source for source in report.source_candidates}
    strategies = {strategy.strategy_family: strategy for strategy in report.strategy_candidates}

    assert sources["dexscreener_liquidity_snapshots"].source_health_present is True
    assert sources["dexscreener_liquidity_snapshots"].readiness == "health_recorded"
    assert sources["defillama_yield_pools"].source_health_present is True
    assert strategies["funding_mean_reversion_after_extreme"].adapter_kind == "deterministic_validator"
    assert strategies["funding_mean_reversion_after_extreme"].readiness == "registered"
    assert strategies["funding_mean_reversion_after_extreme"].blocked_reasons == []
    assert strategies["defi_yield_regime_watchlist"].adapter_kind == "watchlist_only_adapter"
    assert strategies["dex_liquidity_volume_watchlist"].adapter_kind == "watchlist_only_adapter"
    assert strategies["funding_open_interest_crowding"].adapter_kind == "deterministic_validator"
    assert strategies["funding_open_interest_crowding"].readiness == "registered"
    assert strategies["funding_open_interest_crowding"].blocked_reasons == []
    assert strategies["volatility_compression_expansion_watchlist"].adapter_kind == "watchlist_only_adapter"
    assert strategies["volatility_compression_expansion_watchlist"].readiness == "registered"
    assert report.reason_codes


def test_expansion_preparation_accepts_research_usable_source_probe_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    observed_at = datetime(2026, 5, 24, tzinfo=UTC)
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"binance_usdm:open_interest_history:source_probe:{observed_at.isoformat()}",
                source="binance_usdm",
                record_type="source_health",
                observed_at=observed_at,
                payload={
                    "source": "binance_usdm",
                    "feed": "open_interest_history",
                    "success": True,
                    "attempts": 1,
                    "failure": None,
                    "observed_at": observed_at.isoformat(),
                    "records_fetched": 1,
                    "records_written": 0,
                    "network_route": "direct",
                    "provider_status": "ResearchUsable",
                    "parse_status": "parsed",
                    "typed_record_count": 1,
                    "blocked_reason": None,
                },
            )
        ]
    )

    report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )
    candidate = {
        source.source_id: source
        for source in report.source_candidates
    }["binance_usdm_open_interest_history"]

    assert candidate.source_health_present is True
    assert candidate.readiness == "health_recorded"
    assert candidate.blocked_reasons == []


def test_credential_required_source_remains_blocked_even_with_successful_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [_source_health_record("coinalyze", "derivatives_history")]
    )

    report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )
    coinalyze = {
        source.source_id: source
        for source in report.source_candidates
    }["coinalyze_derivatives_history"]

    assert coinalyze.source_health_present is True
    assert coinalyze.readiness == "blocked"
    assert "credential_required" in coinalyze.blocked_reasons


def test_expansion_preparation_blocks_registered_strategy_below_min_capital(tmp_path):
    report = build_expansion_preparation_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=0.0,
    )
    strategies = {strategy.strategy_family: strategy for strategy in report.strategy_candidates}
    candidate = strategies["funding_mean_reversion_after_extreme"]

    assert candidate.readiness == "blocked"
    assert "insufficient_current_capital" in candidate.blocked_reasons
    assert "capital_below_strategy_minimum" in candidate.action_reason_codes


def test_malformed_source_health_fails_closed_without_crashing(tmp_path):
    db_path = tmp_path / "research.sqlite"
    observed_at = datetime(2026, 5, 23, tzinfo=UTC)
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"dexscreener:pairs:source_health:{observed_at.isoformat()}",
                source="dexscreener",
                record_type="source_health",
                observed_at=observed_at,
                payload={
                    "source": "dexscreener",
                    "feed": "pairs",
                    "success": "false",
                    "records_written": "n/a",
                    "network_route": "direct",
                },
            )
        ]
    )

    report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )
    candidate = {
        source.source_id: source
        for source in report.source_candidates
    }["dexscreener_liquidity_snapshots"]

    assert candidate.readiness == "blocked"
    assert "source_health_malformed" in candidate.blocked_reasons


def test_coercible_non_integer_source_health_count_is_malformed(tmp_path):
    db_path = tmp_path / "research.sqlite"
    observed_at = datetime(2026, 5, 23, tzinfo=UTC)
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id=f"dexscreener:pairs:source_health:{observed_at.isoformat()}",
                source="dexscreener",
                record_type="source_health",
                observed_at=observed_at,
                payload={
                    "source": "dexscreener",
                    "feed": "pairs",
                    "success": True,
                    "records_written": "1",
                    "network_route": "direct",
                },
            )
        ]
    )

    report = build_expansion_preparation_report(
        db_path=db_path,
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )
    candidate = {
        source.source_id: source
        for source in report.source_candidates
    }["dexscreener_liquidity_snapshots"]

    assert candidate.readiness == "blocked"
    assert "source_health_malformed" in candidate.blocked_reasons


def test_expansion_preparation_markdown_lists_sources_strategies_and_blockers(tmp_path):
    report = build_expansion_preparation_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        current_capital_usd=300.0,
    )

    markdown = render_expansion_preparation_markdown(report)

    assert markdown.startswith("# Phase 5 Expansion Preparation Report")
    assert "## Source Candidates" in markdown
    assert "binance_usdm_open_interest" in markdown
    assert "source_health_missing" in markdown
    assert "## Strategy Candidates" in markdown
    assert "funding_open_interest_crowding" in markdown
    assert "volatility_compression_expansion_watchlist" in markdown
    assert "cross_exchange_funding_dispersion_candidate" in markdown
    assert "validator_or_watchlist_not_registered" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown


def test_expansion_preparation_cli_writes_markdown_without_live_authority(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    out = tmp_path / "phase5.md"

    exit_code = main(
        [
            "expansion-prep-report",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--out",
            str(out),
            "--current-capital-usd",
            "300",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    markdown = out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["command"] == "expansion-prep-report"
    assert payload["uses_real_capital"] is False
    assert payload["live_order_routing"] is False
    assert payload["llm_provider"] == "real"
    assert payload["llm_judgement"]["schema_name"] == "RuntimeCommandJudgement"
    assert payload["report"]["source_candidates"][0]["source_id"] == "binance_usdm_open_interest"
    assert payload["expansion_prep_report_out"] == str(out)
    assert "Phase 5 Expansion Preparation Report" in markdown
