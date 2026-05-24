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
from crypto_alpha_agent.pipeline.governance_reports import build_profit_governance_report
from crypto_alpha_agent.pipeline.markdown import render_profit_governance_report_markdown
from crypto_alpha_agent.strategy import default_strategy_registry


GOOD_FAMILY = "funding_extremity_price_confirmation"
STOPPED_FAMILY = "funding_mean_reversion_after_extreme"


def test_profit_governance_report_scores_families_and_monthly_owner_review(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_governance_fixture(db_path, memory_path)

    report = build_profit_governance_report(
        db_path=db_path,
        memory_path=memory_path,
        current_capital_usd=300.0,
    )
    markdown = render_profit_governance_report_markdown(report)
    rows = {row.strategy_family: row for row in report.family_scoreboard}
    reviews = {row.strategy_family: row for row in report.profit_reviews}

    assert rows[GOOD_FAMILY].sample_size == 30
    assert rows[GOOD_FAMILY].net_pnl_usd == 60.0
    assert rows[GOOD_FAMILY].cost_adjusted_expectancy_usd == 2.0
    assert rows[GOOD_FAMILY].max_drawdown_usd == 0.8
    assert rows[GOOD_FAMILY].hit_rate == 1.0
    assert rows[GOOD_FAMILY].failure_rate == 0.0
    assert rows[GOOD_FAMILY].source_health_quality == 0.5
    assert rows[GOOD_FAMILY].stale_signal_rate == 0.0
    assert rows[GOOD_FAMILY].walk_forward_stability == 0.75
    assert rows[GOOD_FAMILY].governance_action == "owner_decision_review"
    assert "positive_cost_adjusted_expectancy" in rows[GOOD_FAMILY].reason_codes

    assert rows[STOPPED_FAMILY].governance_action == "stop"
    assert "degraded_family" in rows[STOPPED_FAMILY].reason_codes
    assert reviews[GOOD_FAMILY].is_improving is True
    assert reviews[GOOD_FAMILY].worth_more_data is True
    assert reviews[GOOD_FAMILY].should_stop is False
    assert reviews[GOOD_FAMILY].near_owner_decision_point is True
    assert reviews[STOPPED_FAMILY].should_stop is True

    assert report.stopped_family_ledger
    stopped = report.stopped_family_ledger[0]
    assert stopped.strategy_family == STOPPED_FAMILY
    assert stopped.reason_codes == ["degraded_expectancy"]
    assert stopped.evidence_refs == [f"memory:degraded:{STOPPED_FAMILY}"]
    assert stopped.revival_conditions == [
        "fresh_validation_evidence",
        "positive_cost_adjusted_expectancy",
        "operator_review_required",
    ]

    assert [item.strategy_family for item in report.paper_only_portfolio] == [GOOD_FAMILY]
    selection = report.paper_only_portfolio[0]
    assert selection.rank == 1
    assert selection.paper_weight == 1.0
    assert selection.max_paper_notional_usd == 25.0
    assert selection.selection_reason_codes == [
        "positive_cost_adjusted_expectancy",
        "walk_forward_supported",
        "source_health_partial",
    ]

    assert report.monthly_owner_review.best_paper_strategy == GOOD_FAMILY
    assert report.monthly_owner_review.best_strategy_net_pnl_usd == 60.0
    assert report.monthly_owner_review.do_nothing_pnl_usd == 0.0
    assert report.monthly_owner_review.total_fees_usd == 9.0
    assert report.monthly_owner_review.total_slippage_usd == 6.0
    assert report.monthly_owner_review.opportunity_cost_usd == 0.0
    assert report.monthly_owner_review.owner_capital_constraint_usd == 300.0
    assert report.monthly_owner_review.decision == "owner_decision_review"
    assert report.uses_real_capital is False
    assert report.live_order_routing is False

    assert markdown.startswith("# Profit Governance Report")
    assert "## Weekly Family Scoreboard" in markdown
    assert "## Profit Review" in markdown
    assert "## Stopped-Family Ledger" in markdown
    assert "## Paper-Only Portfolio Selector" in markdown
    assert "## Monthly Owner Review" in markdown
    assert "Real capital: false" in markdown
    assert "Live order routing: false" in markdown


def test_governance_report_cli_writes_markdown_and_json(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    out = tmp_path / "governance.md"
    _seed_governance_fixture(db_path, memory_path)

    exit_code = main(
        [
            "governance-report",
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
    assert payload["command"] == "governance-report"
    assert payload["governance_report_out"] == str(out)
    assert payload["report"]["uses_real_capital"] is False
    assert payload["report"]["live_order_routing"] is False
    assert payload["llm_provider"] == "real"
    assert payload["llm_judgement"]["schema_name"] == "RuntimeCommandJudgement"
    assert payload["report"]["monthly_owner_review"]["best_paper_strategy"] == GOOD_FAMILY
    assert markdown.startswith("# Profit Governance Report")
    assert "paper-only portfolio selector" in markdown.lower()
    assert "monthly owner review" in markdown.lower()


def test_governance_report_marks_registered_no_evidence_families_add_data(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    report = build_profit_governance_report(
        db_path=db_path,
        memory_path=memory_path,
        current_capital_usd=300.0,
    )
    rows = {row.strategy_family: row for row in report.family_scoreboard}

    assert set(rows) == set(default_strategy_registry().list_families())
    assert rows["funding_open_interest_crowding"].governance_action == "add_data"
    assert "missing_evidence" in rows["funding_open_interest_crowding"].reason_codes
    assert rows["volatility_compression_expansion_watchlist"].governance_action == "add_data"


def test_fresh_stop_decision_writes_stopped_ledger_without_memory_marker(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    observed_at = datetime(2026, 5, 24, tzinfo=UTC)
    ResearchDataStore(db_path).upsert_records(
        [
            _source_health(
                "source-health-success",
                source="ccxt",
                feed="ohlcv",
                success=True,
                observed_at=observed_at,
                records_written=100,
                typed_record_count=100,
            )
        ]
    )
    _seed_positive_family_evidence(
        db_path,
        GOOD_FAMILY,
        observed_at=observed_at,
        net_pnl_usd=-1.0,
        gross_pnl_usd=0.1,
        fees_usd=0.6,
        slippage_usd=0.5,
        sample_size=1,
    )

    report = build_profit_governance_report(
        db_path=db_path,
        memory_path=memory_path,
        current_capital_usd=300.0,
    )
    rows = {row.strategy_family: row for row in report.family_scoreboard}
    stopped = {row.strategy_family: row for row in report.stopped_family_ledger}

    assert rows[GOOD_FAMILY].governance_action == "stop"
    assert GOOD_FAMILY in stopped
    assert "negative_cost_adjusted_expectancy" in stopped[GOOD_FAMILY].reason_codes
    assert any(ref.startswith("paper:paper-good") for ref in stopped[GOOD_FAMILY].evidence_refs)
    assert stopped[GOOD_FAMILY].stopped_at == "2026-05-24T00:00:00+00:00"


def test_paper_portfolio_notional_is_split_inside_owner_cap(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    observed_at = datetime(2026, 5, 24, tzinfo=UTC)
    ResearchDataStore(db_path).upsert_records(
        [
            _source_health(
                "source-health-success",
                source="ccxt",
                feed="ohlcv",
                success=True,
                observed_at=observed_at,
                records_written=100,
                typed_record_count=100,
            )
        ]
    )
    _seed_positive_family_evidence(
        db_path,
        GOOD_FAMILY,
        observed_at=observed_at,
        sample_size=30,
    )
    _seed_positive_family_evidence(
        db_path,
        "funding_open_interest_crowding",
        observed_at=observed_at + timedelta(days=1),
        sample_size=30,
    )

    report = build_profit_governance_report(
        db_path=db_path,
        memory_path=memory_path,
        current_capital_usd=30.0,
    )

    assert len(report.paper_only_portfolio) == 2
    assert sum(item.max_paper_notional_usd for item in report.paper_only_portfolio) == 25.0
    assert [item.max_paper_notional_usd for item in report.paper_only_portfolio] == [12.5, 12.5]
    assert all(item.paper_weight == 0.5 for item in report.paper_only_portfolio)


def _seed_governance_fixture(db_path, memory_path) -> None:
    observed_at = datetime(2026, 5, 24, tzinfo=UTC)
    ResearchDataStore(db_path).upsert_records(
        [
            _source_health(
                "source-health-success",
                source="ccxt",
                feed="ohlcv",
                success=True,
                observed_at=observed_at,
                records_written=100,
                typed_record_count=100,
            ),
            _source_health(
                "source-health-failure",
                source="ccxt",
                feed="funding",
                success=False,
                observed_at=observed_at,
                records_written=0,
                typed_record_count=0,
                failure="timeout",
            ),
        ]
    )
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation(
                GOOD_FAMILY,
                run_id="validation-good",
                trade_count=32,
                fee_adjusted_expectancy=0.012,
                slippage_adjusted_expectancy=0.009,
                max_drawdown=0.08,
                walk_forward_split_count=4,
                walk_forward_pass_rate=0.75,
                approved=True,
            ),
            _validation(
                STOPPED_FAMILY,
                run_id="validation-weak",
                trade_count=12,
                fee_adjusted_expectancy=-0.003,
                slippage_adjusted_expectancy=-0.004,
                max_drawdown=0.24,
                walk_forward_split_count=2,
                walk_forward_pass_rate=0.25,
                approved=False,
                blocked_reasons=("insufficient_walk_forward",),
            ),
        ]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            *[
                _paper(
                    GOOD_FAMILY,
                    f"paper-good-{index}",
                    status="closed",
                    observed_at=observed_at + timedelta(hours=index),
                    net_pnl_usd=2.0,
                    gross_pnl_usd=2.5,
                    fees_usd=0.3,
                    slippage_usd=0.2,
                    max_drawdown_usd=0.8 if index == 0 else 0.4,
                )
                for index in range(30)
            ],
            _paper(
                STOPPED_FAMILY,
                "paper-weak-1",
                status="blocked",
                observed_at=observed_at + timedelta(hours=2),
                net_pnl_usd=0.0,
                failure_reasons=("stale_signal",),
                stale_signal_status="stale",
                fill_status="blocked",
            ),
        ]
    )
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id=f"degraded:{STOPPED_FAMILY}",
            created_at=observed_at.isoformat(),
            opportunity={"strategy_family": STOPPED_FAMILY},
            rejected_reasons=["degraded_expectancy"],
            tags=[STOPPED_FAMILY, "degraded_expectancy"],
        )
    )


def _seed_positive_family_evidence(
    db_path,
    strategy_family: str,
    *,
    observed_at: datetime,
    net_pnl_usd: float = 2.0,
    gross_pnl_usd: float = 2.5,
    fees_usd: float = 0.3,
    slippage_usd: float = 0.2,
    sample_size: int,
) -> None:
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation(
                strategy_family,
                run_id=f"validation-{strategy_family}",
                trade_count=max(sample_size, 30),
                fee_adjusted_expectancy=0.012,
                slippage_adjusted_expectancy=0.009,
                max_drawdown=0.08,
                walk_forward_split_count=4,
                walk_forward_pass_rate=0.75,
                approved=True,
            )
        ]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            _paper(
                strategy_family,
                f"paper-good-{strategy_family}-{index}",
                status="closed",
                observed_at=observed_at + timedelta(hours=index),
                net_pnl_usd=net_pnl_usd,
                gross_pnl_usd=gross_pnl_usd,
                fees_usd=fees_usd,
                slippage_usd=slippage_usd,
                max_drawdown_usd=0.4,
            )
            for index in range(sample_size)
        ]
    )


def _validation(
    strategy_family: str,
    *,
    run_id: str,
    trade_count: int,
    fee_adjusted_expectancy: float,
    slippage_adjusted_expectancy: float,
    max_drawdown: float,
    walk_forward_split_count: int,
    walk_forward_pass_rate: float,
    approved: bool,
    blocked_reasons: tuple[str, ...] = (),
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id=run_id,
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name=f"{strategy_family}_validator",
        trade_count=trade_count,
        net_return=0.05 if fee_adjusted_expectancy > 0 else -0.02,
        gross_expectancy=fee_adjusted_expectancy + 0.002,
        fee_adjusted_expectancy=fee_adjusted_expectancy,
        slippage_adjusted_expectancy=slippage_adjusted_expectancy,
        max_drawdown=max_drawdown,
        walk_forward_split_count=walk_forward_split_count,
        walk_forward_pass_rate=walk_forward_pass_rate,
        approved=approved,
        blocked_reasons=blocked_reasons,
    )


def _paper(
    strategy_family: str,
    outcome_id: str,
    *,
    status: str,
    observed_at: datetime,
    net_pnl_usd: float,
    gross_pnl_usd: float = 0.0,
    fees_usd: float = 0.0,
    slippage_usd: float = 0.0,
    max_drawdown_usd: float = 0.0,
    failure_reasons: tuple[str, ...] = (),
    stale_signal_status: str = "fresh",
    fill_status: str = "full",
) -> PaperSimulationOutcome:
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id=f"run-{outcome_id}",
        candidate_id=f"candidate-{outcome_id}",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status=status,
        signal_timestamp=observed_at - timedelta(minutes=5),
        entry_price=100.0,
        exit_price=101.0,
        quantity=0.1,
        notional_usd=25.0,
        gross_pnl_usd=gross_pnl_usd,
        fees_usd=fees_usd,
        slippage_usd=slippage_usd,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=max_drawdown_usd,
        failure_reasons=failure_reasons,
        cost_model_mode="pessimistic",
        stale_signal_status=stale_signal_status,
        fill_status=fill_status,
        fill_ratio=1.0 if fill_status == "full" else 0.0,
    )


def _source_health(
    record_id: str,
    *,
    source: str,
    feed: str,
    success: bool,
    observed_at: datetime,
    records_written: int,
    typed_record_count: int,
    failure: str | None = None,
) -> SourceRecord:
    return SourceRecord(
        record_id=record_id,
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "success": success,
            "attempts": 1,
            "failure": failure,
            "observed_at": observed_at.isoformat(),
            "records_fetched": records_written,
            "records_written": records_written,
            "network_route": "direct",
            "provider_status": "ok" if success else "timeout",
            "http_status": 200 if success else 504,
            "parse_status": "parsed" if success else "failed",
            "typed_record_count": typed_record_count,
        },
    )
