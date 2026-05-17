from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.pipeline.evidence_reports import (
    build_daily_evidence_report,
    build_weekly_evidence_report,
)
from crypto_alpha_agent.pipeline.markdown import (
    render_daily_evidence_report_markdown,
    render_weekly_evidence_report_markdown,
)


STRATEGY_FAMILY = "funding_extremity_price_confirmation"


def test_daily_evidence_report_includes_validation_paper_and_memory_sections(tmp_path):
    report = build_daily_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_families=[STRATEGY_FAMILY],
    )

    assert report.should_continue is True
    assert "validation" in report.reason_codes or report.validation_evidence_count >= 0
    assert report.paper_evidence_count >= 0
    assert report.next_experiments is not None
    assert report.near_paper_eligibility is False
    assert report.near_tiny_live_review is False
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_weekly_evidence_report_aggregates_by_strategy_family(tmp_path):
    report = build_weekly_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
    )

    assert isinstance(report.family_summaries, list)
    assert report.near_tiny_live_review is False
    assert report.uses_real_capital is False
    assert report.live_order_routing is False


def test_daily_report_counts_candidates_outcomes_quality_and_next_experiments(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_daily_fixture(db_path, memory_path)

    report = build_daily_evidence_report(
        db_path=db_path,
        memory_path=memory_path,
        strategy_families=[STRATEGY_FAMILY],
    )
    markdown = render_daily_evidence_report_markdown(report)

    assert report.strategy_families == [STRATEGY_FAMILY]
    assert report.validation_evidence_count == 2
    assert report.paper_outcome_count == 2
    assert report.paper_evidence_count == 1
    assert report.memory_record_count == 3
    assert report.new_candidate_count == 1
    assert report.blocked_candidate_count == 1
    assert report.data_quality_issue_count >= 1
    assert report.should_collect_more_data is True
    assert report.should_stop_family is False
    assert report.next_experiments.proposals
    assert "## New Candidates" in markdown
    assert "## Blocked Candidates" in markdown
    assert "## Paper Outcomes" in markdown
    assert "## Validation Evidence" in markdown
    assert "## Data Quality" in markdown
    assert "## Next Experiments" in markdown
    assert "Close to paper eligibility: true" in markdown
    assert "Close to tiny-live review: false" in markdown


def test_weekly_report_summarizes_rejections_improvement_degradation_and_sample_progress(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_weekly_fixture(db_path, memory_path)

    report = build_weekly_evidence_report(db_path=db_path, memory_path=memory_path)
    markdown = render_weekly_evidence_report_markdown(report)

    summaries = {summary.strategy_family: summary for summary in report.family_summaries}
    assert set(summaries) == {STRATEGY_FAMILY, "dex_liquidity_watchlist"}
    assert summaries[STRATEGY_FAMILY].sample_size == 2
    assert summaries[STRATEGY_FAMILY].validation_count == 2
    assert summaries["dex_liquidity_watchlist"].blocked_count == 1
    assert report.top_rejected_reasons[0] == "insufficient_walk_forward"
    assert report.best_improving_family == STRATEGY_FAMILY
    assert "dex_liquidity_watchlist" in report.degraded_families
    assert report.sample_size_progress[STRATEGY_FAMILY] == 2
    assert report.near_paper_eligibility is True
    assert report.near_tiny_live_review is False
    assert "## Strategy Families" in markdown
    assert "## Top Rejected Reasons" in markdown
    assert "## Sample Size Progress Toward 30" in markdown
    assert "Close to paper eligibility: true" in markdown
    assert "Close to tiny-live review: false" in markdown


def test_evidence_report_cli_writes_daily_and_weekly_markdown(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    daily_out = tmp_path / "daily.md"
    weekly_out = tmp_path / "weekly.md"
    _seed_daily_fixture(db_path, memory_path)

    daily_exit = main(
        [
            "evidence-report",
            "--daily",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--out",
            str(daily_out),
            "--strategy-family",
            STRATEGY_FAMILY,
        ]
    )
    daily_payload = json.loads(capsys.readouterr().out)

    weekly_exit = main(
        [
            "evidence-report",
            "--weekly",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--out",
            str(weekly_out),
        ]
    )
    weekly_payload = json.loads(capsys.readouterr().out)

    assert daily_exit == 0
    assert daily_payload["daily_report_out"] == str(daily_out)
    assert daily_out.read_text(encoding="utf-8").startswith("# Daily Evidence Report")
    assert weekly_exit == 0
    assert weekly_payload["weekly_report_out"] == str(weekly_out)
    assert weekly_out.read_text(encoding="utf-8").startswith("# Weekly Evidence Report")


def _seed_daily_fixture(db_path, memory_path) -> None:
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id="bad-candle",
                source="ccxt",
                record_type="market_candle",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                payload={
                    "venue": "binance",
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                    "timestamp": datetime(2026, 5, 17, tzinfo=UTC).isoformat(),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 0.0,
                },
            )
        ]
    )
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation("validation-1", approved=True, trade_count=28),
            _validation("validation-2", approved=False, trade_count=8, blocked_reasons=("insufficient_walk_forward",)),
        ]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            _paper_outcome("paper-1", status="closed", net_pnl_usd=1.2),
            _paper_outcome("paper-2", status="blocked", net_pnl_usd=0.0, failure_reasons=("no_signal",)),
        ]
    )
    store = MemoryStore(memory_path)
    store.append(
        MemoryRecord(
            record_id="candidate-new",
            opportunity={"strategy_family": STRATEGY_FAMILY, "candidate_id": "cand-1"},
            tags=["candidate", "new_candidate"],
        )
    )
    store.append(
        MemoryRecord(
            record_id="candidate-blocked",
            opportunity={"strategy_family": STRATEGY_FAMILY, "candidate_id": "cand-2"},
            rejected_reasons=["insufficient_walk_forward"],
            tags=["candidate", "blocked_candidate"],
        )
    )
    store.append(
        MemoryRecord(
            record_id="paper-memory",
            paper_trade_outcome={"strategy_family": STRATEGY_FAMILY, "status": "closed"},
            tags=["paper_outcome"],
        )
    )


def _seed_weekly_fixture(db_path, memory_path) -> None:
    _seed_daily_fixture(db_path, memory_path)
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [_validation("validation-3", strategy_family="dex_liquidity_watchlist", approved=False, trade_count=3)]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            _paper_outcome(
                "paper-3",
                strategy_family="dex_liquidity_watchlist",
                status="blocked",
                net_pnl_usd=0.0,
                failure_reasons=("illiquid_pool",),
            )
        ]
    )
    MemoryStore(memory_path).append(
        MemoryRecord(
            record_id="dex-degraded",
            opportunity={"strategy_family": "dex_liquidity_watchlist"},
            rejected_reasons=["insufficient_walk_forward"],
            tags=["degraded", "blocked_candidate"],
        )
    )


def _validation(
    suffix: str,
    *,
    strategy_family: str = STRATEGY_FAMILY,
    approved: bool,
    trade_count: int,
    blocked_reasons: tuple[str, ...] = (),
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id="report-fixture",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price_confirmation",
        trade_count=trade_count,
        net_return=0.03 if approved else -0.01,
        gross_expectancy=0.02 if approved else -0.02,
        fee_adjusted_expectancy=0.015 if approved else -0.03,
        slippage_adjusted_expectancy=0.01 if approved else -0.04,
        max_drawdown=0.05,
        walk_forward_split_count=3 if approved else 0,
        walk_forward_pass_rate=0.67 if approved else 0.0,
        approved=approved,
        blocked_reasons=blocked_reasons,
    )


def _paper_outcome(
    outcome_id: str,
    *,
    strategy_family: str = STRATEGY_FAMILY,
    status: str,
    net_pnl_usd: float,
    failure_reasons: tuple[str, ...] = (),
) -> PaperSimulationOutcome:
    observed_at = datetime(2026, 5, 17, tzinfo=UTC) + timedelta(minutes=len(outcome_id))
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="report-fixture",
        candidate_id=f"candidate-{outcome_id}",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status=status,
        signal_timestamp=observed_at,
        entry_price=100.0,
        exit_price=101.0 if net_pnl_usd > 0 else 100.0,
        quantity=0.1 if status != "blocked" else 0.0,
        notional_usd=10.0 if status != "blocked" else 0.0,
        gross_pnl_usd=net_pnl_usd,
        fees_usd=0.01 if status != "blocked" else 0.0,
        slippage_usd=0.01 if status != "blocked" else 0.0,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=0.1 if status != "blocked" else 0.0,
        failure_reasons=failure_reasons,
    )
