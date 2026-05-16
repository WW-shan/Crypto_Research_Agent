from datetime import UTC, datetime

from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome


def _outcome(outcome_id: str, pnl: float, strategy_family: str = "funding_extremity_price_confirmation"):
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="paper-run-001",
        candidate_id="cand-001",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
        status="closed",
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
