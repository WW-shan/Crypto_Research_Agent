import pytest

from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.memory.store import MemoryStore
from crypto_alpha_agent.pipeline.memory import (
    persist_validation_evidence_memory,
    replace_validation_evidence_memory,
)


def _validation_evidence(**overrides: object) -> ValidationEvidence:
    data = {
        "run_id": "validation-run",
        "strategy_family": "funding_extremity_price_confirmation",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "validator_name": "funding_price",
        "trade_count": 12,
        "net_return": 0.04,
        "gross_expectancy": 0.004,
        "fee_adjusted_expectancy": 0.003,
        "slippage_adjusted_expectancy": 0.002,
        "max_drawdown": 0.03,
        "walk_forward_split_count": 0,
        "walk_forward_pass_rate": 0.0,
        "approved": False,
        "blocked_reasons": ["insufficient_walk_forward_splits"],
    }
    data.update(overrides)
    return ValidationEvidence(**data)


def test_blocked_validation_evidence_is_persisted_to_memory(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = _validation_evidence(
        blocked_reasons=[
            "insufficient_walk_forward_splits",
            "fee_adjusted_expectancy_below_zero",
        ],
    )

    stored = persist_validation_evidence_memory([evidence], memory_path, run_id="validation-run")
    records = MemoryStore(memory_path).list_records()

    assert len(stored) == 1
    assert records[0].record_id == f"validation:validation-run:{evidence.evidence_id}"
    assert {
        "validation-evidence",
        "funding_extremity_price_confirmation",
        "btc-usdt",
        "blocked",
        "validation-run",
    } <= set(records[0].tags)
    assert records[0].opportunity == {
        "strategy_family": "funding_extremity_price_confirmation",
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "validator": "funding_price",
        "run_id": "validation-run",
        "uses_real_capital": False,
        "live_order_routing": False,
    }
    assert records[0].hypothesis["lesson"] == "validation_blocked"
    assert records[0].hypothesis["metrics"]["net_return"] == 0.04
    assert records[0].hypothesis["blocked_reasons"] == [
        "insufficient_walk_forward_splits",
        "fee_adjusted_expectancy_below_zero",
    ]
    assert "insufficient_walk_forward_splits" in records[0].hypothesis["disconfirmation_hints"]
    assert records[0].score == {
        "trade_count": 12,
        "net_return": 0.04,
        "gross_expectancy": 0.004,
        "fee_adjusted_expectancy": 0.003,
        "slippage_adjusted_expectancy": 0.002,
        "max_drawdown": 0.03,
        "walk_forward_split_count": 0,
        "walk_forward_pass_rate": 0.0,
    }
    assert records[0].rejected_reasons == [
        "insufficient_walk_forward_splits",
        "fee_adjusted_expectancy_below_zero",
    ]


def test_approved_validation_evidence_memory_has_no_rejected_reasons(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = _validation_evidence(
        approved=True,
        blocked_reasons=[],
        trade_count=30,
        walk_forward_split_count=4,
        walk_forward_pass_rate=0.75,
    )

    persist_validation_evidence_memory([evidence], memory_path, run_id="validation-run")
    record = MemoryStore(memory_path).list_records()[0]

    assert "approved" in record.tags
    assert "blocked" not in record.tags
    assert record.hypothesis["lesson"] == "validation_approved"
    assert record.hypothesis["blocked_reasons"] == []
    assert record.rejected_reasons == []


def test_persist_validation_evidence_memory_is_idempotent_by_record_id(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = _validation_evidence()

    first = persist_validation_evidence_memory([evidence], memory_path, run_id="validation-run")
    second = persist_validation_evidence_memory([evidence], memory_path, run_id="validation-run")
    records = MemoryStore(memory_path).list_records()

    assert [record.record_id for record in second] == [record.record_id for record in first]
    assert [record.record_id for record in records] == [first[0].record_id]


def test_mismatched_validation_evidence_run_id_raises(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = _validation_evidence(run_id="other-run")

    with pytest.raises(ValueError, match="run_id"):
        persist_validation_evidence_memory([evidence], memory_path, run_id="validation-run")

    assert not memory_path.exists()


def test_empty_validation_evidence_returns_empty_without_file(tmp_path):
    memory_path = tmp_path / "memory.jsonl"

    records = persist_validation_evidence_memory([], memory_path, run_id="validation-run")

    assert records == []
    assert not memory_path.exists()


def test_validation_evidence_without_run_id_uses_supplied_run_id(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    evidence = _validation_evidence(run_id=None)

    stored = persist_validation_evidence_memory([evidence], memory_path, run_id="validation-run")

    assert stored[0].record_id == f"validation:validation-run:{evidence.evidence_id}"
    assert stored[0].opportunity["run_id"] == "validation-run"
    assert "validation-run" in stored[0].tags


def test_replace_validation_evidence_memory_matches_exact_run_id(tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    base = _validation_evidence(run_id="validation-run", symbol="BTC/USDT")
    family = _validation_evidence(run_id="validation-run:family", symbol="ETH/USDT")
    replacement = _validation_evidence(run_id="validation-run", symbol="SOL/USDT")

    persist_validation_evidence_memory([base], memory_path, run_id="validation-run")
    persist_validation_evidence_memory([family], memory_path, run_id="validation-run:family")

    replaced = replace_validation_evidence_memory(
        [replacement],
        memory_path,
        run_id="validation-run",
    )
    records = MemoryStore(memory_path).list_records()

    assert [record.opportunity["symbol"] for record in replaced] == ["SOL/USDT"]
    assert {
        (record.opportunity["run_id"], record.opportunity["symbol"])
        for record in records
        if "validation-evidence" in record.tags
    } == {
        ("validation-run", "SOL/USDT"),
        ("validation-run:family", "ETH/USDT"),
    }
