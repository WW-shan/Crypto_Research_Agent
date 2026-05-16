from datetime import UTC, datetime

from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome


def _outcome(
    outcome_id: str,
    pnl: float,
    strategy_family: str = "funding_extremity_price_confirmation",
    run_id: str = "paper-run-001",
    status: str = "closed",
):
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id=run_id,
        candidate_id="cand-001",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
        status=status,
        signal_timestamp=datetime(2026, 5, 17, tzinfo=UTC),
        entry_price=100.0,
        exit_price=101.0,
        quantity=0.1,
        notional_usd=10.0,
        gross_pnl_usd=pnl + 0.03,
        fees_usd=0.02,
        slippage_usd=0.01,
        net_pnl_usd=pnl,
        max_drawdown_usd=max(0.0, -pnl),
    )


def test_paper_outcome_ledger_round_trips_outcomes(tmp_path):
    ledger = PaperOutcomeLedger(tmp_path / "research.sqlite")

    written = ledger.upsert_outcomes([_outcome("paper-001", 0.12), _outcome("paper-002", -0.05)])
    loaded = ledger.load_outcomes(strategy_family="funding_extremity_price_confirmation")

    assert written == 2
    assert [item.outcome_id for item in loaded] == ["paper-001", "paper-002"]
    assert loaded[1].net_pnl_usd == -0.05


def test_paper_outcome_ledger_upsert_is_idempotent(tmp_path):
    ledger = PaperOutcomeLedger(tmp_path / "research.sqlite")

    ledger.upsert_outcomes([_outcome("paper-001", 0.12)])
    ledger.upsert_outcomes([_outcome("paper-001", 0.20)])

    loaded = ledger.load_outcomes()
    assert len(loaded) == 1
    assert loaded[0].net_pnl_usd == 0.20


def test_replace_run_outcomes_deletes_only_target_run_before_insert(tmp_path):
    ledger = PaperOutcomeLedger(tmp_path / "research.sqlite")
    ledger.upsert_outcomes(
        [
            _outcome("paper-001", 0.12, run_id="paper-run-001"),
            _outcome("paper-002", 0.08, run_id="paper-run-001"),
            _outcome("paper-other", 0.50, run_id="paper-run-other"),
        ]
    )

    written = ledger.replace_run_outcomes(
        "paper-run-001",
        [_outcome("paper-blocked", 0.0, run_id="paper-run-001", status="blocked")],
    )

    replaced = ledger.load_outcomes(run_id="paper-run-001")
    other = ledger.load_outcomes(run_id="paper-run-other")
    assert written == 1
    assert [item.outcome_id for item in replaced] == ["paper-blocked"]
    assert replaced[0].status == "blocked"
    assert [item.outcome_id for item in other] == ["paper-other"]
