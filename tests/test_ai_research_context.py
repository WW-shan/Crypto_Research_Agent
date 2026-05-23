from __future__ import annotations

from datetime import UTC, datetime

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.pipeline.ai_research_context import build_ai_research_context
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO


def _validation(
    *,
    run_id: str,
    strategy_family: str,
    approved: bool,
    blocked_reasons: tuple[str, ...] = (),
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id=run_id,
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        timeframe="1h",
        validator_name="funding_price_confirmation",
        trade_count=4,
        net_return=0.02 if approved else -0.01,
        gross_expectancy=0.01,
        fee_adjusted_expectancy=0.005,
        slippage_adjusted_expectancy=0.004,
        max_drawdown=0.02,
        walk_forward_split_count=3 if approved else 0,
        walk_forward_pass_rate=0.75 if approved else 0.0,
        approved=approved,
        blocked_reasons=blocked_reasons,
    )


def _paper_outcome(
    *,
    outcome_id: str,
    strategy_family: str,
    net_pnl_usd: float,
    status: str = "closed",
) -> PaperSimulationOutcome:
    observed_at = datetime(2026, 5, 17, tzinfo=UTC)
    return PaperSimulationOutcome(
        outcome_id=outcome_id,
        run_id="paper-run-context",
        candidate_id="candidate-1",
        strategy_family=strategy_family,
        symbol="BTC/USDT",
        observed_at=observed_at,
        status=status,
        signal_timestamp=observed_at,
        entry_price=100.0,
        exit_price=101.0,
        quantity=0.1,
        notional_usd=10.0,
        gross_pnl_usd=net_pnl_usd,
        fees_usd=0.1,
        slippage_usd=0.05,
        net_pnl_usd=net_pnl_usd,
        max_drawdown_usd=abs(net_pnl_usd),
        failure_reasons=("fee_killed_edge",) if net_pnl_usd < 0 else (),
    )


def test_build_ai_research_context_uses_recent_evidence_and_registry(tmp_path) -> None:
    db_path = tmp_path / "research.sqlite"
    memory_path = tmp_path / "memory.jsonl"

    ValidationEvidenceLedger(db_path).upsert_evidence(
        [
            _validation(
                run_id="validation-run-a",
                strategy_family="funding_extremity_price_confirmation",
                approved=False,
                blocked_reasons=("insufficient_walk_forward_splits",),
            ),
            _validation(
                run_id="validation-run-b",
                strategy_family="funding_open_interest_crowding",
                approved=True,
            ),
        ]
    )
    PaperOutcomeLedger(db_path).upsert_outcomes(
        [
            _paper_outcome(
                outcome_id="paper-context-1",
                strategy_family="funding_extremity_price_confirmation",
                net_pnl_usd=-0.25,
            )
        ]
    )
    ResearchDataStore(db_path).upsert_records(
        [
            SourceRecord(
                record_id="ccxt:open_interest_history:source_health:2026-05-17T00:00:00+00:00",
                source="ccxt",
                record_type="source_health",
                observed_at=datetime(2026, 5, 17, tzinfo=UTC),
                payload={
                    "source": "ccxt",
                    "feed": "open_interest_history",
                    "success": True,
                    "attempts": 1,
                    "records_fetched": 2,
                    "records_written": 2,
                    "network_route": "public",
                    "provider_status": "ok",
                    "http_status": 200,
                    "parse_status": "ok",
                    "typed_record_count": 2,
                    "observed_at": "2026-05-17T00:00:00+00:00",
                },
            )
        ]
    )
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="degraded:funding_extremity_price_confirmation",
            opportunity={"strategy_family": "funding_extremity_price_confirmation"},
            rejected_reasons=["degraded_expectancy"],
            tags=["funding_extremity_price_confirmation", "degraded_expectancy"],
        )
    )
    MemoryStore(memory_path).upsert(
        MemoryRecord(
            record_id="experiment-proposal:existing",
            opportunity={"strategy_family": "funding_open_interest_crowding"},
            hypothesis={
                "proposal": {
                    "strategy_family": "funding_open_interest_crowding",
                    "parameter_changes": {"threshold_abs": 0.001, "hold_bars": 2},
                }
            },
            rejected_reasons=["non_positive_net_return"],
            tags=["experiment-proposal", "rejected"],
        )
    )

    context = build_ai_research_context(db_path=db_path, memory_path=memory_path, recent_limit=1)

    assert context.validation_evidence_summaries[0].run_id == "validation-run-b"
    assert context.paper_evidence_packages[0].strategy_family == "funding_extremity_price_confirmation"
    assert context.source_health_summaries[0].source == "ccxt"
    assert context.stopped_strategy_families == ["funding_extremity_price_confirmation"]
    assert context.blocked_parameter_set_count == 1
    assert "market_candle" in context.available_data_fields
    assert context.registered_validators[0].validator_name
    assert any(ref.startswith("validation:") for ref in context.evidence_refs)
    assert context.generated_at == DETERMINISTIC_EVENT_TIME_ISO
