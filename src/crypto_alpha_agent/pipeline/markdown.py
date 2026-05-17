from __future__ import annotations

from crypto_alpha_agent.pipeline.evidence_reports import DailyEvidenceReport, WeeklyEvidenceReport
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport


def render_research_loop_markdown(report: ResearchLoopReport) -> str:
    lines = [
        "# Crypto Alpha Research Loop",
        "",
        "## Safety",
        f"Current capital: {report.current_capital_usd:g} USD",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Counts",
        f"Records: {report.loaded_records}",
        f"Signals: {report.signal_count}",
        f"Anomalies: {report.anomaly_count}",
        f"Hypotheses: {report.hypothesis_count}",
        f"Weak signals: {report.weak_signal_count}",
        f"Blocked hypotheses: {report.blocked_hypothesis_count}",
        "",
        "## Top Anomalies",
        "| Asset | Metric | Value | Classification | Score | Executable |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    if report.anomalies:
        for anomaly in report.anomalies[:10]:
            signal = anomaly.signal
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(signal.asset),
                        _escape_table_cell(signal.metric),
                        f"{signal.value:g}",
                        _escape_table_cell(anomaly.classification),
                        f"{anomaly.score:g}",
                        _bool_text(anomaly.executable),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| None | None | 0 | None | 0 | false |")

    lines.extend(
        [
            "",
            "## Hypotheses",
        ]
    )
    if report.hypotheses:
        for index, hypothesis in enumerate(report.hypotheses, start=1):
            lines.extend(
                [
                    f"### {index}. {_escape_text(hypothesis.asset)}",
                    f"Asset: {_escape_text(hypothesis.asset)}",
                    f"What changed: {_escape_text(hypothesis.what_changed)}",
                    f"Why it might be edge: {_escape_text(hypothesis.why_it_might_be_edge)}",
                    f"Actionability: {_escape_text(hypothesis.actionability)}",
                    "Disconfirmation tests:",
                ]
            )
            lines.extend(
                f"- {_escape_text(test)}" for test in hypothesis.disconfirmation_tests
            )
    else:
        lines.append("No hypotheses generated.")

    lines.extend(
        [
            "",
            "## Historical Validation",
        ]
    )
    if report.validation_summaries:
        lines.extend(
            [
                "| Strategy | Asset | Funding symbol | Timeframe | Status | Trade count | Net return | Max drawdown | Gross expectancy | Fee-adjusted expectancy | Slippage-adjusted expectancy | Walk-forward splits | Walk-forward pass rate | Blocked reasons |",
                "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for summary in report.validation_summaries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(summary.strategy_family),
                        _escape_table_cell(summary.asset),
                        _escape_table_cell(summary.funding_symbol or "n/a"),
                        _escape_table_cell(summary.timeframe),
                        _escape_table_cell(summary.status),
                        f"{summary.trade_count:g}",
                        _optional_number(summary.net_return),
                        _optional_number(summary.max_drawdown),
                        _optional_number(summary.gross_expectancy),
                        _optional_number(summary.fee_adjusted_expectancy),
                        _optional_number(summary.slippage_adjusted_expectancy),
                        _optional_number(summary.walk_forward_split_count),
                        _optional_number(summary.walk_forward_pass_rate),
                        _escape_table_cell(", ".join(summary.blocked_reasons) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("No historical validation summaries generated.")

    lines.extend(
        [
            "",
            "## Paper Evidence",
        ]
    )
    if report.paper_evidence_packages:
        lines.extend(
            [
                "| Strategy | Sample size | Closed count | Failed count | Net PnL USD | Hit rate | Max drawdown USD | Failure reasons |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for package in report.paper_evidence_packages:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(package.strategy_family),
                        f"{package.sample_size:g}",
                        f"{package.closed_count:g}",
                        f"{package.failed_count:g}",
                        f"{package.net_pnl_usd:g}",
                        f"{package.hit_rate:g}",
                        f"{package.max_drawdown_usd:g}",
                        _escape_table_cell(", ".join(package.failure_reasons) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("No paper evidence packages attached.")

    lines.extend(
        [
            "",
            "## Data Quality",
        ]
    )
    quality_reports = report.data_quality_reports
    if quality_reports:
        lines.extend(
            [
                "| Reason | Severity | Source | Record type | Semantic key | Observed at | Message |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        issue_count = 0
        for quality_report in quality_reports:
            for issue in quality_report.issues:
                issue_count += 1
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _escape_table_cell(issue.reason_code),
                            _escape_table_cell(issue.severity),
                            _escape_table_cell(issue.source),
                            _escape_table_cell(issue.record_type),
                            _escape_table_cell(issue.semantic_key),
                            _escape_table_cell(
                                "n/a"
                                if issue.observed_at is None
                                else issue.observed_at.isoformat()
                            ),
                            _escape_table_cell(issue.message),
                        ]
                    )
                    + " |"
                )
        if issue_count == 0:
            lines.append("| none | none | none | none | none | n/a | No data quality issues. |")
    else:
        lines.append("No data quality report attached.")

    lines.extend(
        [
            "",
            "## Notes",
        ]
    )
    if report.notes:
        lines.extend(f"- {_escape_text(note)}" for note in report.notes)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def render_daily_evidence_report_markdown(report: DailyEvidenceReport) -> str:
    lines = [
        "# Daily Evidence Report",
        "",
        "## Safety",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Decision",
        f"Continue: {_bool_text(report.should_continue)}",
        f"Stop family: {_bool_text(report.should_stop_family)}",
        f"Collect more data: {_bool_text(report.should_collect_more_data)}",
        f"Close to paper eligibility: {_bool_text(report.near_paper_eligibility)}",
        f"Close to tiny-live review: {_bool_text(report.near_tiny_live_review)}",
        f"Reason codes: {_escape_text(', '.join(report.reason_codes) or 'none')}",
        "",
        "## Strategy Families",
    ]
    lines.extend(_bullet_lines(report.strategy_families))
    lines.extend(
        [
            "",
            "## Counts",
            f"Validation evidence: {report.validation_evidence_count}",
            f"Paper evidence packages: {report.paper_evidence_count}",
            f"Paper outcomes: {report.paper_outcome_count}",
            f"Memory records: {report.memory_record_count}",
            f"Data quality issues: {report.data_quality_issue_count}",
            "",
            "## New Candidates",
            f"New candidate count: {report.new_candidate_count}",
            "",
            "## Blocked Candidates",
            f"Blocked candidate count: {report.blocked_candidate_count}",
            "",
            "## Paper Outcomes",
            f"Paper outcome count: {report.paper_outcome_count}",
            "",
            "## Validation Evidence",
            f"Validation evidence count: {report.validation_evidence_count}",
            "",
            "## Data Quality",
            f"Issue count: {report.data_quality_issue_count}",
            "",
            "## Next Experiments",
        ]
    )
    if report.next_experiments.proposals:
        for proposal in report.next_experiments.proposals:
            lines.append(
                f"- {_escape_text(proposal.strategy_family)}: "
                f"{_escape_text(proposal.why_it_might_improve_edge)}"
            )
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def render_weekly_evidence_report_markdown(report: WeeklyEvidenceReport) -> str:
    lines = [
        "# Weekly Evidence Report",
        "",
        "## Safety",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Decision",
        f"Continue: {_bool_text(report.should_continue)}",
        f"Stop family: {_bool_text(report.should_stop_family)}",
        f"Collect more data: {_bool_text(report.should_collect_more_data)}",
        f"Close to paper eligibility: {_bool_text(report.near_paper_eligibility)}",
        f"Close to tiny-live review: {_bool_text(report.near_tiny_live_review)}",
        f"Reason codes: {_escape_text(', '.join(report.reason_codes) or 'none')}",
        "",
        "## Strategy Families",
        "| Strategy | Sample size | Closed | Failed | Blocked | Net PnL USD | Validation | Near tiny-live review | Rejected reasons |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    if report.family_summaries:
        for summary in report.family_summaries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(summary.strategy_family),
                        f"{summary.sample_size:g}",
                        f"{summary.closed_count:g}",
                        f"{summary.failed_count:g}",
                        f"{summary.blocked_count:g}",
                        f"{summary.net_pnl_usd:g}",
                        f"{summary.validation_count:g}",
                        _bool_text(summary.near_tiny_live_review),
                        _escape_table_cell(", ".join(summary.rejected_reasons) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | false | none |")

    lines.extend(
        [
            "",
            "## Top Rejected Reasons",
        ]
    )
    lines.extend(_bullet_lines(report.top_rejected_reasons))
    lines.extend(
        [
            "",
            "## Best Improving Family",
            _escape_text(report.best_improving_family or "none"),
            "",
            "## Degraded Families",
        ]
    )
    lines.extend(_bullet_lines(report.degraded_families))
    lines.extend(
        [
            "",
            "## Sample Size Progress Toward 30",
            "| Strategy | Progress |",
            "| --- | ---: |",
        ]
    )
    if report.sample_size_progress:
        for family, progress in sorted(report.sample_size_progress.items()):
            lines.append(f"| {_escape_table_cell(family)} | {progress:g}/30 |")
    else:
        lines.append("| none | 0/30 |")
    return "\n".join(lines) + "\n"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _bullet_lines(values: list[str]) -> list[str]:
    if not values:
        return ["- none"]
    return [f"- {_escape_text(value)}" for value in values]


def _escape_table_cell(value: object) -> str:
    return _escape_text(str(value)).replace("|", "\\|")


def _escape_text(value: object) -> str:
    return str(value).replace("\n", " ").strip()


def _optional_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:g}"
