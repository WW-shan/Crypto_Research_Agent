from __future__ import annotations

from crypto_alpha_agent.autonomy.models import CreationCycleReport, CreationObject
from crypto_alpha_agent.pipeline.markdown import render_creation_cycle_markdown


def test_creation_cycle_markdown_neutralizes_untrusted_markup() -> None:
    report = CreationCycleReport(
        task_id="creation-<img src=x onerror=alert(1)>",
        creation=CreationObject(
            id="creation-markup",
            kind="family_idea",
            title=(
                "![x](https://example.invalid/image.png) `code` | table "
                "_emphasis_ *bold* ~~strike~~ https://example.invalid "
                "<https://example.invalid>"
            ),
            hypothesis="# heading\n<script>alert(1)</script>",
            why_now="> quote *bold* [link](https://example.invalid)",
            first_code_change="- list item with <img src=x>",
            expected_experiment="`pytest` and ![alt](https://example.invalid/a.png)",
            status="active",
            continuation_reason="continue with <b>safe text</b>",
            uses_real_capital=False,
            live_order_routing=False,
        ),
        accepted=False,
        status="needs_fix",
        report_path="/tmp/reports/creation/latest.md",
        json_path="/tmp/reports/creation/latest.json",
        task_path="/tmp/task|path",
        patch_path="/tmp/patch|path.diff",
        runner_exit_code=1,
        rejected_reason_codes=["bad|reason"],
        next_actions=[
            "Inspect ![runner](https://example.invalid/runner.png)",
            "`rerun` after <img src=x>",
        ],
    )

    markdown = render_creation_cycle_markdown(report)

    assert "<img" not in markdown
    assert "<script>" not in markdown
    assert "![x](" not in markdown
    assert "![alt](" not in markdown
    assert "![runner](" not in markdown
    assert "`code`" not in markdown
    assert "`pytest`" not in markdown
    assert "`rerun`" not in markdown
    assert "`code` | table" not in markdown
    assert "_emphasis_" not in markdown
    assert "*bold*" not in markdown
    assert "~~strike~~" not in markdown
    assert "https://example.invalid" not in markdown
    assert "<https://example.invalid>" not in markdown
    assert "&lt;img" in markdown
    assert "\\!\\[x\\]\\(" in markdown
    assert "\\`code\\`" in markdown
    assert "\\| table" in markdown
    assert "\\_emphasis\\_" in markdown
    assert "\\*bold\\*" in markdown
    assert "\\~\\~strike\\~\\~" in markdown
    assert "https\\://example.invalid" in markdown
