from __future__ import annotations

import html

from crypto_alpha_agent.autonomy.models import CreationCycleReport
from crypto_alpha_agent.pipeline.ai_research_memo import AIResearchMemo
from crypto_alpha_agent.pipeline.expansion_preparation import ExpansionPreparationReport
from crypto_alpha_agent.pipeline.evidence_reports import DailyEvidenceReport, WeeklyEvidenceReport
from crypto_alpha_agent.pipeline.governance_reports import ProfitGovernanceReport
from crypto_alpha_agent.pipeline.historical_bootstrap import HistoricalBootstrapReport
from crypto_alpha_agent.pipeline.iteration_controller import IterationCycleReport
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
    lines.extend(_llm_summary_lines(report))
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
        "| Strategy | Action | Action reasons | Sample size | Closed | Failed | Blocked | Net PnL USD | Validation | Near tiny-live review | Rejected reasons |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    if report.family_summaries:
        for summary in report.family_summaries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(summary.strategy_family),
                        _escape_table_cell(summary.recommended_action),
                        _escape_table_cell(", ".join(summary.action_reason_codes) or "none"),
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
        lines.append("| none | add_data | no_family_evidence | 0 | 0 | 0 | 0 | 0 | 0 | false | none |")

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
    lines.extend(_llm_summary_lines(report))
    return "\n".join(lines) + "\n"


def render_profit_governance_report_markdown(report: ProfitGovernanceReport) -> str:
    lines = [
        "# Profit Governance Report",
        "",
        "## Safety",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        f"Current capital USD: {report.current_capital_usd:g}",
        "",
        "## Weekly Family Scoreboard",
        "| Strategy | Action | Sample | Net PnL USD | Expectancy USD | Max drawdown USD | Hit rate | Failure rate | Source health | Stale rate | Walk-forward | Reasons |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    if report.family_scoreboard:
        for row in report.family_scoreboard:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(row.strategy_family),
                        _escape_table_cell(row.governance_action),
                        f"{row.sample_size:g}",
                        f"{row.net_pnl_usd:g}",
                        f"{row.cost_adjusted_expectancy_usd:g}",
                        f"{row.max_drawdown_usd:g}",
                        f"{row.hit_rate:g}",
                        f"{row.failure_rate:g}",
                        f"{row.source_health_quality:g}",
                        f"{row.stale_signal_rate:g}",
                        f"{row.walk_forward_stability:g}",
                        _escape_table_cell(", ".join(row.reason_codes) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | add_data | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | no_family_evidence |")

    lines.extend(
        [
            "",
            "## Profit Review",
            "| Strategy | Improving | Worth more data | Stop | Owner decision point | Action | Evidence refs |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if report.profit_reviews:
        for review in report.profit_reviews:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(review.strategy_family),
                        _bool_text(review.is_improving),
                        _bool_text(review.worth_more_data),
                        _bool_text(review.should_stop),
                        _bool_text(review.near_owner_decision_point),
                        _escape_table_cell(review.governance_action),
                        _escape_table_cell(", ".join(review.evidence_refs) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | false | false | false | false | add_data | none |")

    lines.extend(
        [
            "",
            "## Stopped-Family Ledger",
            "| Strategy | Stopped at | Reasons | Evidence refs | Revival conditions |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if report.stopped_family_ledger:
        for row in report.stopped_family_ledger:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(row.strategy_family),
                        _escape_table_cell(row.stopped_at),
                        _escape_table_cell(", ".join(row.reason_codes) or "none"),
                        _escape_table_cell(", ".join(row.evidence_refs) or "none"),
                        _escape_table_cell(", ".join(row.revival_conditions) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | n/a | none | none | none |")

    lines.extend(
        [
            "",
            "## Paper-Only Portfolio Selector",
            "| Rank | Strategy | Paper weight | Max paper notional USD | Score | Reasons | Exclusions |",
            "| ---: | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    if report.paper_only_portfolio:
        for item in report.paper_only_portfolio:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"{item.rank:g}",
                        _escape_table_cell(item.strategy_family),
                        f"{item.paper_weight:g}",
                        f"{item.max_paper_notional_usd:g}",
                        f"{item.score:g}",
                        _escape_table_cell(", ".join(item.selection_reason_codes) or "none"),
                        _escape_table_cell(", ".join(item.exclusion_reason_codes) or "none"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| 0 | none | 0 | 0 | 0 | no_paper_candidate | none |")

    owner = report.monthly_owner_review
    lines.extend(
        [
            "",
            "## Monthly Owner Review",
            f"Best paper strategy: {_escape_text(owner.best_paper_strategy or 'none')}",
            f"Best strategy net PnL USD: {owner.best_strategy_net_pnl_usd:g}",
            f"Doing nothing PnL USD: {owner.do_nothing_pnl_usd:g}",
            f"Fees USD: {owner.total_fees_usd:g}",
            f"Slippage USD: {owner.total_slippage_usd:g}",
            f"Opportunity cost USD: {owner.opportunity_cost_usd:g}",
            f"Owner capital constraint USD: {owner.owner_capital_constraint_usd:g}",
            f"Decision: {_escape_text(owner.decision)}",
            f"Reason codes: {_escape_text(', '.join(owner.reason_codes) or 'none')}",
            "",
            "Comparison notes:",
        ]
    )
    lines.extend(_bullet_lines(owner.comparison_notes))
    return "\n".join(lines) + "\n"


def render_ai_research_memo_markdown(memo: AIResearchMemo) -> str:
    lines = [
        "# Weekly AI Research Memo",
        "",
        "## Safety",
        f"Real capital: {_bool_text(memo.uses_real_capital)}",
        f"Live order routing: {_bool_text(memo.live_order_routing)}",
        "",
        "## What Changed",
    ]
    lines.extend(_bullet_lines(memo.what_changed))
    lines.extend(["", "## What Failed"])
    lines.extend(_bullet_lines(memo.what_failed))
    lines.extend(["", "## What Should Stop"])
    lines.extend(_bullet_lines(memo.what_should_stop))
    lines.extend(["", "## Next Experiment"])
    lines.extend(_bullet_lines(memo.next_experiment))
    lines.extend(["", "## Evidence Refs"])
    lines.extend(_bullet_lines(memo.evidence_refs))
    if memo.rejected_reason_codes:
        lines.extend(["", "## Rejected Reason Codes"])
        lines.extend(_bullet_lines(memo.rejected_reason_codes))
    return "\n".join(lines) + "\n"


def render_expansion_preparation_markdown(report: ExpansionPreparationReport) -> str:
    lines = [
        "# Phase 5 Expansion Preparation Report",
        "",
        "## Safety",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Decision",
        f"Reason codes: {_escape_text(', '.join(report.reason_codes) or 'none')}",
        "",
        "## Source Readiness",
        "| Readiness | Count |",
        "| --- | ---: |",
    ]
    if report.source_readiness_counts:
        for readiness, count in sorted(report.source_readiness_counts.items()):
            lines.append(f"| {_escape_table_cell(readiness)} | {count:g} |")
    else:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "## Source Candidates",
            "| Priority | Source | Provider | Feed | Credentials | Health | Route | Readiness | Blocked reasons | Next phase |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for source in report.source_candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{source.priority:g}",
                    _escape_table_cell(source.source_id),
                    _escape_table_cell(source.provider),
                    _escape_table_cell(source.feed),
                    _escape_table_cell(source.credential_requirement),
                    _bool_text(source.source_health_present),
                    _escape_table_cell(source.latest_source_health_route),
                    _escape_table_cell(source.readiness),
                    _escape_table_cell(", ".join(source.blocked_reasons) or "none"),
                    _escape_table_cell(source.next_phase),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Strategy Actions",
            "| Action | Count |",
            "| --- | ---: |",
        ]
    )
    if report.strategy_action_counts:
        for action, count in sorted(report.strategy_action_counts.items()):
            lines.append(f"| {_escape_table_cell(action)} | {count:g} |")
    else:
        lines.append("| none | 0 |")
    lines.extend(
        [
            "",
            "## Strategy Candidates",
            "| Priority | Strategy | Adapter | Readiness | Action | Action reasons | Blocked reasons | Next phase |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for strategy in report.strategy_candidates:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{strategy.priority:g}",
                    _escape_table_cell(strategy.strategy_family),
                    _escape_table_cell(strategy.adapter_kind),
                    _escape_table_cell(strategy.readiness),
                    _escape_table_cell(strategy.recommended_action),
                    _escape_table_cell(", ".join(strategy.action_reason_codes) or "none"),
                    _escape_table_cell(", ".join(strategy.blocked_reasons) or "none"),
                    _escape_table_cell(strategy.next_phase),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_historical_bootstrap_markdown(report: HistoricalBootstrapReport) -> str:
    lines = [
        "# Phase 7 Historical Bootstrap Report",
        "",
        "## Safety",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        f"Network route: {_escape_text(report.network_route)}",
        "",
        "## Bootstrap Windows",
        "| Window | Start | End | Price symbol | Funding symbol | Timeframe | Records |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for window in report.bootstrap_windows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(window.window_id),
                    _escape_table_cell(window.start_at.isoformat()),
                    _escape_table_cell(window.end_at.isoformat()),
                    _escape_table_cell(window.price_symbol),
                    _escape_table_cell(window.funding_symbol),
                    _escape_table_cell(window.timeframe),
                    f"{window.record_count:g}",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Source Collection",
            "| Source | Feed | Window | Status | Route | Records written | Reason |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for step in report.source_steps:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(step.source_id),
                    _escape_table_cell(step.feed),
                    _escape_table_cell(step.window_id or "all"),
                    _escape_table_cell(step.status),
                    _escape_table_cell(step.network_route),
                    f"{step.records_written:g}",
                    _escape_table_cell(step.reason_code or "none"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Strategy Results",
            "| Window | Strategy | Classification | Governance | Validation | Trades | Paper outcomes | Paper statuses | Cost modes | Blocked reasons |",
            "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for result in report.strategy_results:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(result.window_id),
                    _escape_table_cell(result.strategy_family),
                    _escape_table_cell(result.classification),
                    _escape_table_cell(result.governance_action),
                    _escape_table_cell(result.validation_status),
                    f"{result.validation_trade_count:g}",
                    f"{result.paper_outcome_count:g}",
                    _escape_table_cell(", ".join(result.paper_statuses) or "none"),
                    _escape_table_cell(", ".join(result.cost_model_modes) or "none"),
                    _escape_table_cell(
                        ", ".join(
                            [
                                *result.validation_blocked_reasons,
                                *result.paper_blocked_reasons,
                            ]
                        )
                        or "none"
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Forward Sample Progress",
            "| Strategy | Progress toward 30 |",
            "| --- | ---: |",
        ]
    )
    if report.weekly_sample_progress:
        for family, progress in sorted(report.weekly_sample_progress.items()):
            lines.append(f"| {_escape_table_cell(family)} | {progress:g}/30 |")
    else:
        lines.append("| none | 0/30 |")
    lines.extend(
        [
            "",
            "## Governance Classification",
            "| Strategy | Action |",
            "| --- | --- |",
        ]
    )
    if report.governance_actions:
        for family, action in sorted(report.governance_actions.items()):
            lines.append(f"| {_escape_table_cell(family)} | {_escape_table_cell(action)} |")
    else:
        lines.append("| none | add_data |")
    lines.extend(
        [
            "",
            "## Forward 30/60/90 Evidence Targets",
            f"Paper observation targets: {', '.join(str(value) for value in report.sample_targets.paper_observation_targets)}",
            f"Calendar day target: {report.sample_targets.calendar_day_target:g}",
            "",
            "| Strategy | Observations | Calendar days |",
            "| --- | ---: | ---: |",
        ]
    )
    families = sorted(
        {
            *report.sample_targets.current_observations_by_family.keys(),
            *report.sample_targets.current_calendar_days_by_family.keys(),
        }
    )
    if families:
        for family in families:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(family),
                        f"{report.sample_targets.current_observations_by_family.get(family, 0):g}",
                        f"{report.sample_targets.current_calendar_days_by_family.get(family, 0):g}",
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | 0 | 0 |")
    lines.extend(
        [
            "",
            "## Out-of-Sample Policy",
            _escape_text(report.out_of_sample_policy),
            "",
            "## Manifest",
            f"Run id: {_escape_text(report.manifest.run_id)}",
            f"Status: {_escape_text(report.manifest.status)}",
            f"Memory path: {_escape_text(report.manifest.memory_path)}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_iteration_cycle_markdown(report: IterationCycleReport) -> str:
    lines = [
        "# Iteration Cycle Report",
        "",
        "## Safety",
        f"LLM required: {_bool_text(report.llm_required)}",
        f"Auto executes changes: {_bool_text(report.auto_executes_changes)}",
        f"Scheduler executes commands: {_bool_text(report.scheduler_executes_commands)}",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Decision",
        f"Accepted: {_bool_text(report.accepted)}",
        f"Cycle id: {_escape_text(report.cycle_id)}",
        f"Current capital: {report.current_capital_usd:g} USD",
        f"Strategy family: {_escape_text(report.strategy_family or 'all')}",
        f"Rejected reason codes: {_escape_text(', '.join(report.rejected_reason_codes) or 'none')}",
        "",
        "## Context Counts",
        f"Research evidence refs: {report.research_evidence_ref_count:g}",
        f"Source candidates: {report.source_candidate_count:g}",
        f"Strategy candidates: {report.strategy_candidate_count:g}",
        f"Governance families: {report.governance_family_count:g}",
        "",
        "## Evidence Refs",
    ]
    lines.extend(_bullet_lines(report.evidence_refs))
    lines.extend(["", "## Candidates"])
    if not report.candidates:
        lines.append("No safe iteration candidates accepted.")
        return "\n".join(lines) + "\n"

    for index, candidate in enumerate(report.candidates, start=1):
        lines.extend(
            [
                f"### {index}. {_escape_text(candidate.title)}",
                f"Kind: {_escape_text(candidate.kind)}",
                f"Risk: {_escape_text(candidate.risk_level)}",
                f"Human review required: {_bool_text(candidate.human_review_required)}",
                f"Direct code write authorized: {_bool_text(candidate.direct_code_write_authorized)}",
                f"Uses real capital: {_bool_text(candidate.uses_real_capital)}",
                f"Live order routing: {_bool_text(candidate.live_order_routing)}",
                f"Expected value: {_escape_text(candidate.expected_value)}",
                f"Rationale: {_escape_text(candidate.rationale)}",
                "Evidence refs:",
            ]
        )
        lines.extend(_bullet_lines(candidate.evidence_refs))
        lines.extend(["Required tests:"])
        lines.extend(_bullet_lines(candidate.required_tests))
        lines.extend(["Next actions:"])
        lines.extend(_bullet_lines(candidate.next_actions))
        if candidate.target_files:
            lines.extend(["Target files:"])
            lines.extend(_bullet_lines(candidate.target_files))
        if candidate.source_discovery_queries:
            lines.extend(["Source discovery queries:"])
            lines.extend(_bullet_lines(candidate.source_discovery_queries))
        if candidate.source_probe_targets:
            lines.extend(["Source probe targets:"])
            lines.extend(_bullet_lines(candidate.source_probe_targets))
    return "\n".join(lines) + "\n"


def render_creation_cycle_markdown(report: CreationCycleReport) -> str:
    lines = [
        "# Creation Cycle Report",
        "",
        "## Safety",
        f"LLM required: {_bool_text(report.llm_required)}",
        f"Codex required: {_bool_text(report.codex_required)}",
        f"Real capital: {_bool_text(report.uses_real_capital)}",
        f"Live order routing: {_bool_text(report.live_order_routing)}",
        "",
        "## Creation",
        f"Task id: {_escape_markdown_text(report.task_id)}",
        f"Accepted: {_bool_text(report.accepted)}",
        f"Status: {_escape_markdown_text(report.status)}",
        f"Kind: {_escape_markdown_text(report.creation.kind)}",
        f"Title: {_escape_markdown_text(report.creation.title)}",
        f"Hypothesis: {_escape_markdown_text(report.creation.hypothesis)}",
        f"Why now: {_escape_markdown_text(report.creation.why_now)}",
        f"First code change: {_escape_markdown_text(report.creation.first_code_change)}",
        f"Expected experiment: {_escape_markdown_text(report.creation.expected_experiment)}",
        "",
        "## Artifacts",
        f"Task path: {_escape_markdown_text(report.task_path)}",
        f"Patch path: {_escape_markdown_text(report.patch_path or 'none')}",
        f"Runner exit code: {_escape_text(report.runner_exit_code if report.runner_exit_code is not None else 'none')}",
    ]
    if report.rejected_reason_codes:
        lines.extend(["", "## Rejected Reason Codes"])
        lines.extend(_bullet_lines([_escape_markdown_text(reason) for reason in report.rejected_reason_codes]))
    lines.extend(["", "## Next Actions"])
    lines.extend(_bullet_lines([_escape_markdown_text(action) for action in report.next_actions]))
    return "\n".join(lines) + "\n"


def _llm_summary_lines(report: DailyEvidenceReport | WeeklyEvidenceReport) -> list[str]:
    summary = getattr(report, "llm_summary", None)
    if summary is None:
        return []
    lines = [
        "",
        "## LLM Narrative Summary",
        _escape_text(summary.summary),
        "",
        "Metric refs:",
    ]
    lines.extend(_bullet_lines(list(summary.metric_refs)))
    if summary.caveats:
        lines.extend(["", "Caveats:"])
        lines.extend(_bullet_lines(list(summary.caveats)))
    return lines


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


def _escape_markdown_text(value: object) -> str:
    text = html.escape(_escape_text(value), quote=True)
    markdown_meta = "`[]()!|"
    escaped = "".join(f"\\{char}" if char in markdown_meta else char for char in text)
    if escaped[:1] in {"#", "-", "+", "*"}:
        return "\\" + escaped
    return escaped


def _optional_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:g}"
