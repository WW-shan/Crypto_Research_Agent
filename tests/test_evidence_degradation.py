from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from crypto_alpha_agent.cli import build_parser, main
from crypto_alpha_agent.data.models import FundingRateRecord, MarketCandle
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline import evidence_reports
from crypto_alpha_agent.pipeline.evidence_runner import run_daily_evidence_pipeline
from crypto_alpha_agent.pipeline.experiment_planner import plan_next_experiments
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop
from crypto_alpha_agent.scheduler import build_daily_schedule_plan


STRATEGY_FAMILY = "funding_extremity_price_confirmation"


def _planner_llm(_task):
    return json.dumps(
        {
            "strategy_family": STRATEGY_FAMILY,
            "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
            "evidence_refs": ["gap:collect_more_walk_forward_data"],
            "why_it_might_improve_edge": "Higher public funding extremity may survive fees.",
            "expected_edge_mechanism": "More extreme public funding rates may retain fee-adjusted edge.",
            "disconfirmation_tests": ["Reject if deterministic validation remains weak."],
            "stop_conditions": ["Stop after repeated blocked validation runs."],
            "required_data_fields": ["market_candle", "funding_rate"],
            "selected_validator": "funding_price_confirmation",
        }
    )


def test_negative_latest_window_paper_expectancy_triggers_degraded_expectancy():
    positive_history = [
        _paper_outcome(f"old-{index}", net_pnl_usd=2.0, hours=index)
        for index in range(3)
    ]
    recent_losses = [
        _paper_outcome(f"recent-{index}", net_pnl_usd=-0.25, hours=10 + index)
        for index in range(10)
    ]

    result = evidence_reports.detect_strategy_degradation(
        [*positive_history, *recent_losses],
        [],
        window=10,
    )

    assert result.degraded is True
    assert result.strategy_families == [STRATEGY_FAMILY]
    assert result.family_decisions[0].strategy_family == STRATEGY_FAMILY
    assert result.family_decisions[0].rolling_paper_expectancy == -0.25
    assert result.family_decisions[0].paper_outcome_count == 10
    assert result.family_decisions[0].reason_codes == ["degraded_expectancy"]
    assert result.reason_codes == ["degraded_expectancy"]


def test_paper_expectancy_window_uses_latest_closed_and_failed_outcomes():
    positive_history = [
        _paper_outcome(f"old-{index}", net_pnl_usd=2.0, hours=index)
        for index in range(3)
    ]
    recent_losses = [
        _paper_outcome(f"recent-{index}", net_pnl_usd=-0.25, hours=10 + index)
        for index in range(10)
    ]
    later_blocked = [
        _paper_outcome(
            f"blocked-later-{index}",
            status="blocked",
            net_pnl_usd=0.0,
            failure_reasons=("no_valid_public_signal",),
            hours=30 + index,
        )
        for index in range(2)
    ]

    result = evidence_reports.detect_strategy_degradation(
        [*positive_history, *recent_losses, *later_blocked],
        [],
        window=10,
    )

    assert result.family_decisions[0].paper_outcome_count == 10
    assert result.family_decisions[0].rolling_paper_expectancy == -0.25
    assert result.family_decisions[0].reason_codes == ["degraded_expectancy"]


def test_blocked_paper_outcomes_trigger_insufficient_progress_reason():
    outcomes = [
        _paper_outcome(
            f"blocked-{index}",
            status="blocked",
            net_pnl_usd=0.0,
            failure_reasons=("no_valid_public_signal",),
            hours=index,
        )
        for index in range(3)
    ]

    result = evidence_reports.detect_strategy_degradation(outcomes, [], window=10)

    assert result.degraded is True
    assert result.family_decisions[0].blocked_outcome_count == 3
    assert "insufficient_evidence_progress" in result.reason_codes
    assert "too_many_blocked_runs" in result.reason_codes


def test_fee_and_slippage_killed_validation_edge_are_reported_per_family():
    result = evidence_reports.detect_strategy_degradation(
        [],
        [
            _validation_evidence(
                strategy_family=STRATEGY_FAMILY,
                gross_expectancy=0.003,
                fee_adjusted_expectancy=0.0,
                slippage_adjusted_expectancy=-0.001,
            ),
            _validation_evidence(
                strategy_family="funding_mean_reversion_after_extreme",
                gross_expectancy=0.004,
                fee_adjusted_expectancy=0.002,
                slippage_adjusted_expectancy=0.0,
            ),
        ],
    )

    decisions = {
        decision.strategy_family: decision
        for decision in result.family_decisions
    }
    assert result.degraded is True
    assert result.strategy_families == [
        "funding_extremity_price_confirmation",
        "funding_mean_reversion_after_extreme",
    ]
    assert decisions[STRATEGY_FAMILY].reason_codes == [
        "fee_killed_edge",
        "slippage_killed_edge",
    ]
    assert decisions["funding_mean_reversion_after_extreme"].reason_codes == [
        "slippage_killed_edge"
    ]


def test_validation_drawdown_breach_marks_family_degraded():
    result = evidence_reports.detect_strategy_degradation(
        [],
        [
            _validation_evidence(
                gross_expectancy=0.004,
                fee_adjusted_expectancy=0.003,
                slippage_adjusted_expectancy=0.002,
                max_drawdown=0.35,
                approved=True,
                blocked_reasons=(),
            )
        ],
    )

    assert result.degraded is True
    assert result.strategy_families == [STRATEGY_FAMILY]
    assert result.family_decisions[0].reason_codes == ["drawdown_breach"]
    assert result.reason_codes == ["drawdown_breach"]


def test_non_degraded_families_return_empty_reasons():
    result = evidence_reports.detect_strategy_degradation(
        [
            _paper_outcome("closed-1", net_pnl_usd=0.25, hours=1),
            _paper_outcome("closed-2", net_pnl_usd=0.15, hours=2),
        ],
        [
            _validation_evidence(
                gross_expectancy=0.003,
                fee_adjusted_expectancy=0.002,
                slippage_adjusted_expectancy=0.001,
                approved=True,
                blocked_reasons=(),
            )
        ],
    )

    assert result.degraded is False
    assert result.strategy_families == []
    assert result.reason_codes == []
    assert result.family_decisions[0].reason_codes == []


def test_mark_family_degraded_persists_memory_record_planner_can_read(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    record = evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy", "fee_killed_edge", "degraded_expectancy"],
        memory_path=memory_path,
    )
    stopped = evidence_reports.load_stopped_strategy_families(memory_path)
    planner_result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family=STRATEGY_FAMILY,
        max_proposals=1,
        llm=_planner_llm,
    )
    persisted = MemoryStore(memory_path).get(f"degraded:{STRATEGY_FAMILY}")

    assert record.record_id == f"degraded:{STRATEGY_FAMILY}"
    assert persisted is not None
    assert persisted.rejected_reasons == ["degraded_expectancy", "fee_killed_edge"]
    assert set(persisted.tags) >= {
        STRATEGY_FAMILY,
        "degraded",
        "degraded_expectancy",
        "fee_killed_edge",
    }
    assert persisted.opportunity["strategy_family"] == STRATEGY_FAMILY
    assert stopped == [STRATEGY_FAMILY]
    assert planner_result.proposals == []
    assert planner_result.degraded_strategy_families == [STRATEGY_FAMILY]


def test_planner_excludes_stopped_family_from_memory_by_default(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family=STRATEGY_FAMILY,
        max_proposals=1,
        llm=_planner_llm,
    )

    assert evidence_reports.load_stopped_strategy_families(memory_path) == [STRATEGY_FAMILY]
    assert result.proposals == []
    assert result.degraded_strategy_families == [STRATEGY_FAMILY]
    assert result.stopped_family_override_used is False


def test_planner_allow_stopped_family_returns_override_metadata(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    result = plan_next_experiments(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        strategy_family=STRATEGY_FAMILY,
        max_proposals=1,
        allow_stopped_family=True,
        llm=_planner_llm,
    )

    assert [proposal.strategy_family for proposal in result.proposals] == [STRATEGY_FAMILY]
    assert result.degraded_strategy_families == [STRATEGY_FAMILY]
    assert result.stopped_family_override_used is True
    assert "stopped_family_override_used" in result.decision_reason_codes


def test_daily_evidence_pipeline_skips_stopped_family_validation_and_paper_by_default(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    report = run_daily_evidence_pipeline(
        db_path=db_path,
        memory_path=memory_path,
        report_out=tmp_path / "daily.md",
        allow_network=True,
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        timeframe="1h",
        run_id="stopped-family-run",
        strategy_families=[STRATEGY_FAMILY],
        ccxt_collector=_DeterministicCcxtCollector(),
    )

    assert "stopped_family_skipped" in report.decision_reason_codes
    assert report.validation_evidence_written == 0
    assert report.paper_outcomes_written == 0
    assert ValidationEvidenceLedger(db_path).load_evidence(strategy_family=STRATEGY_FAMILY) == []
    assert PaperOutcomeLedger(db_path).load_outcomes(strategy_family=STRATEGY_FAMILY) == []


def test_research_loop_blocks_stopped_family_validation_by_default(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ResearchDataStore(db_path)
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    report = run_stored_research_loop(
        db_path,
        include_validation=True,
        strategy_family=STRATEGY_FAMILY,
        price_symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        validation_timeframe="1h",
        memory_path=memory_path,
    )

    assert report.validation_summaries[0].status == "blocked"
    assert report.validation_summaries[0].blocked_reasons == ["stopped_family_blocked"]
    assert "stopped_family_blocked" in report.decision_reason_codes


def test_daily_schedule_plan_skips_stopped_family_unless_override_requested(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    plan = build_daily_schedule_plan(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "daily.md",
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        strategy_families=[STRATEGY_FAMILY],
    )
    evidence_argv = plan.planned_commands[-1].argv

    assert plan.skipped_strategy_families == [STRATEGY_FAMILY]
    assert "stopped_family_skipped" in plan.decision_reason_codes
    assert evidence_argv[evidence_argv.index("--strategy-family") + 1] == STRATEGY_FAMILY
    assert "--allow-stopped-family" not in evidence_argv

    override_plan = build_daily_schedule_plan(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "daily.md",
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        strategy_families=[STRATEGY_FAMILY],
        allow_stopped_family=True,
    )
    override_argv = override_plan.planned_commands[-1].argv

    assert override_plan.skipped_strategy_families == []
    assert override_plan.stopped_family_override_used is True
    assert override_argv[override_argv.index("--strategy-family") + 1] == STRATEGY_FAMILY
    assert "--allow-stopped-family" in override_argv


def test_daily_schedule_plan_does_not_fall_back_to_default_when_non_default_family_is_stopped(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    stopped_family = "funding_mean_reversion_after_extreme"
    evidence_reports.mark_family_degraded(
        stopped_family,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    plan = build_daily_schedule_plan(
        db_path=tmp_path / "research.sqlite",
        memory_path=memory_path,
        report_out=tmp_path / "daily.md",
        symbol="BTC/USDT",
        funding_symbol="BTC/USDT:USDT",
        strategy_families=[stopped_family],
    )
    evidence_argv = plan.planned_commands[-1].argv

    assert plan.skipped_strategy_families == [stopped_family]
    assert evidence_argv[evidence_argv.index("--strategy-family") + 1] == stopped_family
    assert "funding_extremity_price_confirmation" not in evidence_argv


def test_cli_allow_stopped_family_flags_and_research_loop_json(tmp_path, capsys):
    parser = build_parser()
    for command, extra in (
        (
            "evidence-run",
            [
                "--report-out",
                str(tmp_path / "daily.md"),
                "--symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
                "--timeframe",
                "1h",
            ],
        ),
        ("research-loop", []),
        (
            "schedule",
            [
                "--dry-run",
                "--report-out",
                str(tmp_path / "schedule.md"),
                "--symbol",
                "BTC/USDT",
                "--funding-symbol",
                "BTC/USDT:USDT",
            ],
        ),
    ):
        args = parser.parse_args(
            [
                command,
                "--db",
                str(tmp_path / f"{command}.sqlite"),
                "--memory",
                str(tmp_path / f"{command}.jsonl"),
                *extra,
                "--allow-stopped-family",
            ]
        )
        assert args.allow_stopped_family is True

    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ResearchDataStore(db_path)
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--include-validation",
            "--strategy-family",
            STRATEGY_FAMILY,
            "--price-symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--validation-timeframe",
            "1h",
            "--allow-stopped-family",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["stopped_family_override_used"] is True
    assert payload["report"]["decision_reason_codes"] == ["stopped_family_override_used"]


def test_evidence_run_override_is_visible_in_daily_report_and_memory(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        "crypto_alpha_agent.pipeline.evidence_runner.build_ccxt_collector",
        lambda _exchange_id: _DeterministicCcxtCollector(),
    )
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    report_path = tmp_path / "daily.md"
    evidence_reports.mark_family_degraded(
        STRATEGY_FAMILY,
        ["degraded_expectancy"],
        memory_path=memory_path,
    )

    exit_code = main(
        [
            "evidence-run",
            "--db",
            str(db_path),
            "--memory",
            str(memory_path),
            "--report-out",
            str(report_path),
            "--allow-network",
            "--symbol",
            "BTC/USDT",
            "--funding-symbol",
            "BTC/USDT:USDT",
            "--timeframe",
            "1h",
            "--strategy-family",
            STRATEGY_FAMILY,
            "--allow-stopped-family",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    memory_records = MemoryStore(memory_path).list_records()

    assert exit_code == 0
    assert payload["stopped_family_override_used"] is True
    assert "stopped_family_override_used" in payload["report"]["decision_reason_codes"]
    assert "stopped_family_override_used" in report_path.read_text(encoding="utf-8")
    assert any("stopped_family_override_used" in record.tags for record in memory_records)


class _DeterministicCcxtCollector:
    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
        start = datetime(2026, 5, 17, tzinfo=UTC)
        return [
            MarketCandle(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=index),
                timeframe=timeframe,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0 + (index % 5),
                volume=1000.0,
            )
            for index in range(24)
        ]

    def fetch_funding_rate_history(self, symbol, since=None, limit=None, params=None):
        start = datetime(2026, 5, 17, tzinfo=UTC)
        return [
            FundingRateRecord(
                source="ccxt",
                venue="binance",
                symbol=symbol,
                timestamp=start + timedelta(hours=hour),
                funding_rate=0.0008,
            )
            for hour in (8, 16)
        ]


def _paper_outcome(
    outcome_id: str,
    *,
    strategy_family: str = STRATEGY_FAMILY,
    status: str = "closed",
    net_pnl_usd: float,
    gross_pnl_usd: float = 0.05,
    fees_usd: float = 0.01,
    slippage_usd: float = 0.01,
    failure_reasons: tuple[str, ...] = (),
    hours: int = 0,
) -> PaperSimulationOutcome:
    observed_at = datetime(2026, 5, 17, tzinfo=UTC) + timedelta(hours=hours)
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="paper-degradation-run",
        candidate_id=f"candidate-{outcome_id}",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status=status,
        signal_timestamp=observed_at,
        entry_price=100.0,
        exit_price=99.0,
        quantity=0.1,
        notional_usd=10.0,
        gross_pnl_usd=gross_pnl_usd,
        fees_usd=fees_usd,
        slippage_usd=slippage_usd,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=abs(net_pnl_usd),
        failure_reasons=failure_reasons,
    )


def _validation_evidence(
    *,
    strategy_family: str = STRATEGY_FAMILY,
    gross_expectancy: float,
    fee_adjusted_expectancy: float,
    slippage_adjusted_expectancy: float,
    max_drawdown: float = 0.02,
    approved: bool = False,
    blocked_reasons: tuple[str, ...] = ("non_positive_expectancy",),
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id="validation-degradation-run",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price_confirmation",
        trade_count=8,
        net_return=slippage_adjusted_expectancy,
        gross_expectancy=gross_expectancy,
        fee_adjusted_expectancy=fee_adjusted_expectancy,
        slippage_adjusted_expectancy=slippage_adjusted_expectancy,
        max_drawdown=max_drawdown,
        walk_forward_split_count=3,
        walk_forward_pass_rate=1.0 if approved else 0.0,
        approved=approved,
        blocked_reasons=blocked_reasons,
    )
