import json
from datetime import UTC, datetime

from crypto_alpha_agent.cli import main
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.pipeline.markdown import render_research_loop_markdown
from crypto_alpha_agent.pipeline.research_loop import run_stored_research_loop


def test_research_loop_can_attach_paper_evidence_packages(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            PaperSimulationOutcome(
                outcome_id="paper-001",
                run_id="paper-run",
                candidate_id="cand-001",
                strategy_family="funding_extremity_price_confirmation",
                symbol="BTC/USDT",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                status="closed",
                signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                entry_price=100.0,
                exit_price=101.0,
                quantity=0.1,
                notional_usd=10.0,
                gross_pnl_usd=0.1,
                fees_usd=0.02,
                slippage_usd=0.01,
                net_pnl_usd=0.07,
                max_drawdown_usd=0.01,
            )
        ]
    )

    report = run_stored_research_loop(db_path, include_paper_evidence=True)

    assert (
        report.paper_evidence_packages[0].strategy_family
        == "funding_extremity_price_confirmation"
    )
    assert report.paper_evidence_packages[0].sample_size == 1


def test_markdown_report_renders_paper_evidence_section(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            PaperSimulationOutcome(
                outcome_id="paper-001",
                run_id="paper-run",
                candidate_id="cand-001",
                strategy_family="funding_extremity_price_confirmation",
                symbol="BTC/USDT",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                status="blocked",
                signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                entry_price=100.0,
                exit_price=100.0,
                quantity=0.0,
                notional_usd=0.0,
                gross_pnl_usd=0.0,
                fees_usd=0.0,
                slippage_usd=0.0,
                net_pnl_usd=0.0,
                max_drawdown_usd=0.0,
                failure_reasons=["no_signal"],
            )
        ]
    )

    report = run_stored_research_loop(db_path, include_paper_evidence=True)
    markdown = render_research_loop_markdown(report)

    assert "## Paper Evidence" in markdown
    assert "funding_extremity_price_confirmation" in markdown
    assert "no_signal" in markdown


def test_research_loop_cli_can_include_paper_evidence(capsys, tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path)
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            PaperSimulationOutcome(
                outcome_id="paper-001",
                run_id="paper-run",
                candidate_id="cand-001",
                strategy_family="funding_extremity_price_confirmation",
                symbol="BTC/USDT",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                status="closed",
                signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
                entry_price=100.0,
                exit_price=101.0,
                quantity=0.1,
                notional_usd=10.0,
                gross_pnl_usd=0.1,
                fees_usd=0.02,
                slippage_usd=0.01,
                net_pnl_usd=0.07,
                max_drawdown_usd=0.01,
            )
        ]
    )

    exit_code = main(
        [
            "research-loop",
            "--db",
            str(db_path),
            "--include-paper-evidence",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert (
        payload["report"]["paper_evidence_packages"][0]["strategy_family"]
        == "funding_extremity_price_confirmation"
    )
