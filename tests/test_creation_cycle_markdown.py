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
                "<https://example.invalid> www.example.com user@example.com "
                "\\*bold\\* \\_emphasis\\_"
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
    assert "www.example.com" not in markdown
    assert "user@example.com" not in markdown
    assert "\\*bold\\*" not in markdown
    assert "\\_emphasis\\_" not in markdown
    assert "&lt;img" in markdown
    assert "&#33;&#91;x&#93;&#40;" in markdown
    assert "&#96;code&#96;" in markdown
    assert "&#124; table" in markdown
    assert "&#95;emphasis&#95;" in markdown
    assert "&#42;bold&#42;" in markdown
    assert "&#126;&#126;strike&#126;&#126;" in markdown
    assert "https&#58;&#47;&#47;example&#46;invalid" in markdown
    assert "www&#46;example&#46;com" in markdown
    assert "user&#64;example&#46;com" in markdown
    assert "&#92;&#42;bold&#92;&#42;" in markdown
    assert "&#92;&#95;emphasis&#92;&#95;" in markdown
