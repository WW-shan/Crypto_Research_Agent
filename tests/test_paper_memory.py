from datetime import UTC, datetime

from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.pipeline.memory import (
    persist_paper_outcome_memory,
    replace_paper_outcome_memory,
)


def _paper_outcome(
    *,
    outcome_id: str = "paper-001",
    run_id: str = "paper-run",
    status: str = "blocked",
    notional_usd: float = 0.0,
    failure_reasons: list[str] | None = None,
) -> PaperSimulationOutcome:
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id=run_id,
        candidate_id="cand-001",
        strategy_family="funding_extremity_price_confirmation",
        symbol="BTC/USDT",
        observed_at=datetime(2026, 5, 17, tzinfo=UTC),
        status=status,
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
    assert records[0].opportunity["status"] == "closed"


def test_replace_paper_outcome_memory_keeps_colon_prefixed_other_run_id(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    persist_paper_outcome_memory(
        [
            _paper_outcome(outcome_id="stale", run_id="paper", status="closed"),
            _paper_outcome(outcome_id="other", run_id="paper:other", status="closed"),
        ],
        memory_path,
    )

    replace_paper_outcome_memory(
        [
            _paper_outcome(
                outcome_id="fresh",
                run_id="paper",
                status="blocked",
                failure_reasons=["rerun_blocked"],
            )
        ],
        memory_path,
    )
    records = MemoryStore(memory_path).list_records()
    record_ids = {record.record_id for record in records}

    assert "paper-outcome:paper:stale" not in record_ids
    assert "paper-outcome:paper:fresh" in record_ids
    assert "paper-outcome:paper:other:other" in record_ids
    assert any(
        record.opportunity["run_id"] == "paper:other"
        for record in records
        if "paper-evidence" in record.tags
    )


def test_replace_paper_outcome_memory_keeps_non_paper_prefix_match(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    store = MemoryStore(memory_path)
    store.upsert(
        MemoryRecord(
            record_id="paper-outcome:paper:manual-note",
            opportunity={"run_id": "paper"},
            hypothesis={"note": "manual record that only resembles paper memory"},
            tags=["manual-note"],
        )
    )
    persist_paper_outcome_memory(
        [_paper_outcome(outcome_id="stale", run_id="paper", status="closed")],
        memory_path,
    )

    replace_paper_outcome_memory(
        [_paper_outcome(outcome_id="fresh", run_id="paper", status="closed")],
        memory_path,
    )

    records = MemoryStore(memory_path)
    manual_note = records.get("paper-outcome:paper:manual-note")
    assert manual_note is not None
    assert manual_note.tags == ["manual-note"]
    assert records.get("paper-outcome:paper:stale") is None
    assert records.get("paper-outcome:paper:fresh") is not None
