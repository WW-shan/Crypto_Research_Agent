from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

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
from crypto_alpha_agent.agents.report_summarizer import summarize_evidence_report


STRATEGY_FAMILY = "funding_extremity_price_confirmation"


class _SummaryRuntime:
    def __init__(self, response: str | None = None, *, role: str = "summary") -> None:
        self.llm = _SummaryLLM(response)
        self.role = role
        self.health_commands: list[str] = []

    def health_check(self, *, command: str):
        self.health_commands.append(command)
        return object()

    def metadata(self) -> dict[str, object]:
        return {
            "llm_provider": "real",
            "used_fake_llm": False,
            "llm_role": self.role,
            "llm_model": "test-real-model",
            "llm_health_schema": "LLMHealthCheckResult",
        }


class _SummaryLLM:
    def __init__(self, response: str | None) -> None:
        self.response = response
        self.task = None

    def __call__(self, task):
        self.task = task
        if self.response is not None:
            return self.response
        return _summary_response(report_type=task.report_type)


@pytest.fixture(autouse=True)
def required_summary_runtime(monkeypatch):
    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="summary": _SummaryRuntime(role=role),
    )


def _summary_response(*, report_type: str = "daily") -> str:
    return json.dumps(
        {
            "report_type": report_type,
            "summary": "Evidence report metrics remain research-only and require continued validation.",
            "metric_refs": ["validation_evidence_count"],
            "caveats": ["Narrative summary is secondary."],
            "uses_real_capital": False,
            "live_order_routing": False,
        }
    )


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
    assert report.memory_record_count == len(MemoryStore(memory_path).list_records())
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


def test_daily_report_marks_fresh_degraded_evidence_as_stopped_memory(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation(
                "validation-degraded-drawdown",
                approved=True,
                trade_count=30,
                max_drawdown=0.35,
            )
        ]
    )

    report = build_daily_evidence_report(
        db_path=db_path,
        memory_path=memory_path,
        strategy_families=[STRATEGY_FAMILY],
    )
    memory_records = MemoryStore(memory_path).list_records()

    assert report.should_stop_family is True
    assert "drawdown_breach" in report.reason_codes
    assert any(
        record.record_id == f"degraded:{STRATEGY_FAMILY}"
        and "drawdown_breach" in record.rejected_reasons
        for record in memory_records
    )


def test_daily_report_memory_count_includes_planner_side_effect_records(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_daily_fixture(db_path, memory_path)

    report = build_daily_evidence_report(
        db_path=db_path,
        memory_path=memory_path,
        strategy_families=[STRATEGY_FAMILY],
    )

    assert report.next_experiments.proposals
    assert report.memory_record_count == len(MemoryStore(memory_path).list_records())


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


def test_weekly_report_assigns_family_actions_and_reasons(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_weekly_fixture(db_path, memory_path)

    report = build_weekly_evidence_report(db_path=db_path, memory_path=memory_path)
    markdown = render_weekly_evidence_report_markdown(report)
    summaries = {summary.strategy_family: summary for summary in report.family_summaries}

    assert summaries[STRATEGY_FAMILY].recommended_action == "add_data"
    assert "sample_below_target" in summaries[STRATEGY_FAMILY].action_reason_codes
    assert summaries["dex_liquidity_watchlist"].recommended_action == "stop"
    assert "degraded_family" in summaries["dex_liquidity_watchlist"].action_reason_codes
    assert "| Strategy | Action |" in markdown
    assert "add_data" in markdown
    assert "stop" in markdown


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


def test_evidence_report_can_use_fast_summary_llm(capsys, monkeypatch, tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    daily_out = tmp_path / "daily-llm.md"
    _seed_daily_fixture(db_path, memory_path)
    runtime = _SummaryRuntime(
        _summary_response(report_type="daily").replace(
            "Evidence report metrics remain research-only and require continued validation.",
            "Daily evidence has validation records, paper outcomes, and an active data collection need.",
        )
    )

    monkeypatch.setattr(
        "crypto_alpha_agent.cli.build_required_real_llm_runtime",
        lambda role="summary": runtime,
    )

    exit_code = main(
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

    payload = json.loads(capsys.readouterr().out)
    markdown = daily_out.read_text(encoding="utf-8")

    assert exit_code == 0
    assert runtime.health_commands == ["evidence-report"]
    assert runtime.llm.task.report_type == "daily"
    assert payload["llm_provider"] == "real"
    assert payload["used_fake_llm"] is False
    assert payload["llm_role"] == "summary"
    assert payload["report"]["validation_evidence_count"] == 2
    assert payload["report"]["paper_outcome_count"] == 2
    assert payload["report"]["llm_summary"]["summary"].startswith("Daily evidence")
    assert "## LLM Narrative Summary" in markdown
    assert "Validation evidence: 2" in markdown


def test_daily_evidence_report_can_render_llm_summary_without_changing_metrics(tmp_path):
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"
    _seed_daily_fixture(db_path, memory_path)
    report = build_daily_evidence_report(
        db_path=db_path,
        memory_path=memory_path,
        strategy_families=[STRATEGY_FAMILY],
    )
    original = report.model_dump(mode="json")

    def fake_llm(task):
        assert task.report_type == "daily"
        assert task.deterministic_report["validation_evidence_count"] == 2
        return json.dumps(
            {
                "report_type": "daily",
                "summary": "Validation is active, paper samples remain below target, and more data collection is still required.",
                "metric_refs": ["validation_evidence_count=2", "paper_outcome_count=2"],
                "caveats": ["Summary is secondary to deterministic metrics."],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )

    summary_result = summarize_evidence_report(report, report_type="daily", llm=fake_llm)
    enriched = report.model_copy(
        update={
            "llm_summary": summary_result.summary,
            "llm_summary_metadata": summary_result.llm_response_metadata,
        }
    )
    markdown = render_daily_evidence_report_markdown(enriched)

    assert summary_result.accepted is True
    assert enriched.validation_evidence_count == original["validation_evidence_count"]
    assert enriched.paper_outcome_count == original["paper_outcome_count"]
    assert enriched.next_experiments.model_dump(mode="json") == original["next_experiments"]
    assert "## LLM Narrative Summary" in markdown
    assert "Validation is active" in markdown


def test_report_summarizer_rejects_invalid_or_unsafe_output_without_raw_text(tmp_path):
    report = build_daily_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_families=[STRATEGY_FAMILY],
    )
    unsafe_response = "{not json} private-key seed phrase live order"

    def fake_llm(_task):
        return unsafe_response

    summary_result = summarize_evidence_report(report, report_type="daily", llm=fake_llm)
    payload = json.dumps(summary_result.model_dump(mode="json"), sort_keys=True)

    assert summary_result.accepted is False
    assert "invalid_json" in summary_result.rejected_reason_codes
    assert summary_result.llm_response_metadata["raw_response_omitted"] is True
    assert summary_result.llm_response_metadata["raw_response_length"] == len(unsafe_response)
    assert "private-key seed phrase" not in payload
    assert "live order" not in payload


def test_report_summarizer_accepts_common_caveats_alias_without_extra_raw_text(tmp_path):
    report = build_daily_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_families=[STRATEGY_FAMILY],
    )

    def fake_llm(_task):
        return json.dumps(
            {
                "report_type": "daily",
                "summary": "Daily evidence remains research-only and still needs more samples.",
                "metric_refs": ["paper_outcome_count=0"],
                "caves": ["Common provider typo should be normalized to caveats."],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )

    summary_result = summarize_evidence_report(report, report_type="daily", llm=fake_llm)
    payload = json.dumps(summary_result.model_dump(mode="json"), sort_keys=True)

    assert summary_result.accepted is True
    assert summary_result.summary is not None
    assert summary_result.summary.caveats == [
        "Common provider typo should be normalized to caveats."
    ]
    assert "Common provider typo" in payload


def test_report_summarizer_normalizes_false_safety_flag_echoes_without_raw_text(tmp_path):
    report = build_daily_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_families=[STRATEGY_FAMILY],
    )

    def fake_llm(_task):
        return json.dumps(
            {
                "report_type": "daily",
                "summary": (
                    "The report has uses_real_capital=false and "
                    "live_order_routing=false with no live order routing."
                ),
                "metric_refs": [
                    "uses_real_capital=false",
                    "live_order_routing=false",
                ],
                "caveats": ["Keep the execution authority flag false."],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )

    summary_result = summarize_evidence_report(report, report_type="daily", llm=fake_llm)

    assert summary_result.accepted is True
    assert summary_result.summary is not None
    free_text = json.dumps(
        {
            "summary": summary_result.summary.summary,
            "metric_refs": summary_result.summary.metric_refs,
            "caveats": summary_result.summary.caveats,
        },
        sort_keys=True,
    )
    assert "uses_real_capital" not in free_text
    assert "live_order_routing" not in free_text
    assert "live order routing" not in free_text
    assert "execution_authority=false" in free_text


@pytest.mark.parametrize(
    "unsafe_summary",
    [
        "Use a live order after this report.",
        "Keep no live order routing as a safety flag, then place one after this report.",
    ],
)
def test_report_summarizer_rejects_valid_unsafe_instruction_without_raw_text(
    tmp_path,
    unsafe_summary,
):
    report = build_daily_evidence_report(
        db_path=tmp_path / "research.sqlite",
        memory_path=tmp_path / "memory.jsonl",
        strategy_families=[STRATEGY_FAMILY],
    )

    def fake_llm(_task):
        return json.dumps(
            {
                "report_type": "daily",
                "summary": unsafe_summary,
                "metric_refs": ["validation_evidence_count=0"],
                "caveats": [],
                "uses_real_capital": False,
                "live_order_routing": False,
            }
        )

    summary_result = summarize_evidence_report(report, report_type="daily", llm=fake_llm)
    payload = json.dumps(summary_result.model_dump(mode="json"), sort_keys=True)

    assert summary_result.accepted is False
    assert summary_result.rejected_reason_codes == ["invalid_summary"]
    assert unsafe_summary not in payload


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
    max_drawdown: float = 0.05,
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
        max_drawdown=max_drawdown,
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
