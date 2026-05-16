from __future__ import annotations

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
            "## Notes",
        ]
    )
    if report.notes:
        lines.extend(f"- {_escape_text(note)}" for note in report.notes)
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _escape_table_cell(value: object) -> str:
    return _escape_text(str(value)).replace("|", "\\|")


def _escape_text(value: object) -> str:
    return str(value).replace("\n", " ").strip()
