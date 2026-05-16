from datetime import UTC, datetime

from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.memory import persist_paper_outcome_memory


def _paper_outcome(
    *,
    outcome_id: str = "paper-001",
    status: str = "blocked",
    notional_usd: float = 0.0,
    failure_reasons: list[str] | None = None,
) -> PaperSimulationOutcome:
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
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
        notional_usd=notional_usd,
        gross_pnl_usd=0.0,
        fees_usd=0.0,
        slippage_usd=0.0,
        net_pnl_usd=0.0,
        max_drawdown_usd=0.0,
        failure_reasons=failure_reasons or [],
    )


def test_paper_outcomes_are_persisted_to_memory_with_failure_reasons(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    outcome = _paper_outcome(
        status="blocked",
        notional_usd=25.0,
        failure_reasons=["no_signal", "insufficient_walk_forward_splits"],
    )

    stored = persist_paper_outcome_memory([outcome], memory_path)
    records = MemoryStore(memory_path).list_records()

    assert len(stored) == 1
    assert records[0].opportunity["strategy_family"] == "funding_extremity_price_confirmation"
    assert records[0].opportunity["notional"] == outcome.notional_usd
    assert "no_signal" in records[0].rejected_reasons
    assert "paper-evidence" in records[0].tags


def test_closed_paper_outcome_without_failure_reasons_has_no_rejected_reasons(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    outcome = _paper_outcome(status="closed", notional_usd=25.0, failure_reasons=[])

    persist_paper_outcome_memory([outcome], memory_path)
    records = MemoryStore(memory_path).list_records()

    assert records[0].rejected_reasons == []
