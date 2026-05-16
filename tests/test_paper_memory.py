from datetime import UTC, datetime

from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.memory import persist_paper_outcome_memory


def test_paper_outcomes_are_persisted_to_memory_with_failure_reasons(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    outcome = PaperSimulationOutcome(
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
        failure_reasons=["no_signal", "insufficient_walk_forward_splits"],
    )

    stored = persist_paper_outcome_memory([outcome], memory_path)
    records = MemoryStore(memory_path).list_records()

    assert len(stored) == 1
    assert records[0].opportunity["strategy_family"] == "funding_extremity_price_confirmation"
    assert "no_signal" in records[0].rejected_reasons
    assert "paper-evidence" in records[0].tags
