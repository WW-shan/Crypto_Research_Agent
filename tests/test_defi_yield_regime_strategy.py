from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.data.models import DefiYieldSnapshot, SourceRecord
from crypto_alpha_agent.strategy.defi_yield_regime import (
    STRATEGY_FAMILY,
    validate_defi_yield_regime,
)
from crypto_alpha_agent.strategy.models import StrategyPaperRequest, StrategyValidationRequest
from crypto_alpha_agent.strategy.registry import default_strategy_registry


def _yield_snapshot(
    hour: int,
    *,
    chain: str = "Ethereum",
    project: str = "aave-v3",
    symbol: str = "USDC",
    tvl_usd: float = 1_000_000.0,
    apy: float = 4.0,
    observed_at: datetime | None = None,
    raw: dict[str, object] | None = None,
) -> DefiYieldSnapshot:
    return DefiYieldSnapshot(
        source="defillama",
        chain=chain,
        project=project,
        symbol=symbol,
        tvl_usd=tvl_usd,
        apy=apy,
        observed_at=observed_at or datetime(2026, 5, 17, hour, tzinfo=UTC),
        raw=raw or {},
    )


def _source_record(snapshot: DefiYieldSnapshot) -> SourceRecord:
    return SourceRecord(
        record_id=(
            f"defillama:{snapshot.chain}:{snapshot.project}:{snapshot.symbol}:"
            f"{snapshot.observed_at.isoformat()}"
        ),
        source="defillama",
        record_type="defi_yield",
        observed_at=snapshot.observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _record(snapshot: DefiYieldSnapshot) -> dict[str, object]:
    return _source_record(snapshot).model_dump(mode="json")


def test_apy_jump_with_sufficient_tvl_creates_research_watchlist_candidate():
    records = [
        _record(_yield_snapshot(1, apy=3.0, raw={"pool": "Ethereum Aave/V3:USDC"})),
        _record(_yield_snapshot(2, apy=4.5, raw={"pool": "Ethereum Aave/V3:USDC"})),
        {"record_type": "market_candle", "payload": {"ignored": True}},
    ]

    report = validate_defi_yield_regime(
        records,
        min_apy_change=1.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.strategy_family == STRATEGY_FAMILY
    assert report.validator_name == "defi_yield_regime"
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.metrics["execution_role"] == "research_only"
    assert report.metrics["paper_watchlist_only"] is True
    assert report.metrics["candidate_count"] == 1
    assert report.metrics["candidates"] == [
        {
            "chain": "Ethereum",
            "project": "aave-v3",
            "symbol": "USDC",
            "pool_id": "pool-ethereum-aave-v3-usdc",
            "latest_observed_at": "2026-05-17T02:00:00Z",
            "prior_observed_at": "2026-05-17T01:00:00Z",
            "latest_apy": 4.5,
            "prior_apy": 3.0,
            "apy_change": 1.5,
            "tvl_usd": 1_000_000.0,
            "direction": "apy_up",
        }
    ]


def test_direct_defi_yield_snapshot_payload_is_accepted():
    records = [
        _yield_snapshot(1, chain="Base", apy=6.0).model_dump(mode="json"),
        _yield_snapshot(2, chain="Base", apy=4.5).model_dump(mode="json"),
    ]

    report = validate_defi_yield_regime(
        records,
        min_apy_change=1.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1
    assert report.metrics["candidates"][0]["direction"] == "apy_down"
    assert "pool_id" in report.metrics["candidates"][0]


def test_approved_report_preserves_rejected_group_reasons_in_metrics():
    records = [
        _record(_yield_snapshot(1, apy=3.0, raw={"pool": "candidate"})),
        _record(_yield_snapshot(2, apy=4.5, raw={"pool": "candidate"})),
        _record(_yield_snapshot(1, tvl_usd=50_000.0, apy=3.0, raw={"pool": "low tvl"})),
        _record(_yield_snapshot(2, tvl_usd=50_000.0, apy=5.0, raw={"pool": "low tvl"})),
    ]

    report = validate_defi_yield_regime(
        records,
        min_tvl_usd=100_000.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.blocked_reasons == ()
    assert report.metrics["blocked_reasons_observed"] == ["insufficient_tvl"]
    assert report.metrics["rejected_group_reasons"] == [
        {
            "chain": "Ethereum",
            "project": "aave-v3",
            "symbol": "USDC",
            "pool_id": "pool-low-tvl",
            "blocked_reasons": ["insufficient_tvl"],
        }
    ]


def test_low_tvl_blocks_with_insufficient_tvl():
    records = [
        _record(_yield_snapshot(1, tvl_usd=50_000.0, apy=3.0)),
        _record(_yield_snapshot(2, tvl_usd=50_000.0, apy=5.0)),
    ]

    report = validate_defi_yield_regime(
        records,
        min_tvl_usd=100_000.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_tvl",)
    assert report.metrics["candidate_count"] == 0


def test_missing_prior_observations_blocks_with_insufficient_history():
    records = [_record(_yield_snapshot(1, apy=5.0))]

    report = validate_defi_yield_regime(records, now=datetime(2026, 5, 17, 3, tzinfo=UTC))

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_history",)


def test_unsupported_chain_blocks_with_unsupported_chain():
    records = [
        _record(_yield_snapshot(1, chain="Solana", apy=3.0)),
        _record(_yield_snapshot(2, chain="Solana", apy=5.0)),
    ]

    report = validate_defi_yield_regime(records, now=datetime(2026, 5, 17, 3, tzinfo=UTC))

    assert report.approved is False
    assert report.blocked_reasons == ("unsupported_chain",)


def test_stale_source_blocks_when_now_is_provided():
    records = [
        _record(_yield_snapshot(1, apy=3.0)),
        _record(_yield_snapshot(2, apy=5.0)),
    ]
    now = datetime(2026, 5, 17, 2, tzinfo=UTC) + timedelta(hours=73)

    report = validate_defi_yield_regime(records, now=now, max_age_hours=72.0)

    assert report.approved is False
    assert report.blocked_reasons == ("stale_source",)


def test_default_now_blocks_old_defi_yield_records_as_stale():
    records = [
        _record(_yield_snapshot(1, apy=3.0, observed_at=datetime(2020, 1, 1, 1, tzinfo=UTC))),
        _record(_yield_snapshot(2, apy=5.0, observed_at=datetime(2020, 1, 1, 2, tzinfo=UTC))),
    ]

    report = validate_defi_yield_regime(records)

    assert report.approved is False
    assert "stale_source" in report.blocked_reasons


def test_distinct_defillama_pools_do_not_share_history():
    records = [
        _record(_yield_snapshot(1, apy=2.0, raw={"pool": "pool-a"})),
        _record(_yield_snapshot(2, apy=5.0, raw={"pool": "pool-b"})),
    ]

    report = validate_defi_yield_regime(
        records,
        min_apy_change=1.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_history",)
    assert report.metrics["candidate_count"] == 0


def test_distinct_stable_pool_metadata_does_not_share_history():
    records = [
        _record(_yield_snapshot(1, apy=2.0, raw={"poolMeta": "USDC main"})),
        _record(_yield_snapshot(2, apy=5.0, raw={"poolMeta": "USDC boosted"})),
    ]

    report = validate_defi_yield_regime(
        records,
        min_apy_change=1.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_history",)
    assert report.metrics["candidate_count"] == 0


def test_stale_unsupported_low_tvl_latest_reports_all_blockers():
    records = [
        _record(
            _yield_snapshot(
                1,
                chain="Solana",
                tvl_usd=50_000.0,
                apy=3.0,
                observed_at=datetime(2020, 1, 1, 1, tzinfo=UTC),
            )
        ),
        _record(
            _yield_snapshot(
                2,
                chain="Solana",
                tvl_usd=50_000.0,
                apy=5.0,
                observed_at=datetime(2020, 1, 1, 2, tzinfo=UTC),
            )
        ),
    ]

    report = validate_defi_yield_regime(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert set(report.blocked_reasons) >= {
        "insufficient_tvl",
        "unsupported_chain",
        "stale_source",
    }


def test_malformed_and_missing_defi_yield_records_block_without_crashing():
    records = [
        {"record_type": "defi_yield", "payload": {"chain": "Ethereum"}},
        {"record_type": "funding_rate", "payload": {"symbol": "BTC/USDT:USDT"}},
        {"not": "a defi yield record"},
    ]

    report = validate_defi_yield_regime(records)

    assert report.approved is False
    assert report.blocked_reasons == ("missing_defi_yield_records",)


def test_registry_spec_is_research_only_and_run_paper_is_unsupported():
    registry = default_strategy_registry(current_capital_usd=300.0)

    spec = registry.get(STRATEGY_FAMILY)
    paper = registry.run_paper(
        StrategyPaperRequest(
            strategy_family=STRATEGY_FAMILY,
            records=[],
            current_capital_usd=300.0,
            notional_usd=0.0,
        )
    )

    assert spec.required_record_types == ("defi_yield",)
    assert spec.required_symbols == ("*defi_yield",)
    assert spec.supports_paper_simulation is False
    assert spec.min_capital_usd == 0.0
    assert spec.max_notional_usd == 0.0
    assert spec.execution_role == "research_only"
    assert paper.status == "unsupported"
    assert paper.blocked_reasons == ("paper_simulation_not_supported",)
    assert paper.metrics == {}


def test_default_registry_validate_can_validate_family_from_records():
    registry = default_strategy_registry(current_capital_usd=300.0)
    records = [
        _record(_yield_snapshot(1, apy=2.0)),
        _record(_yield_snapshot(2, apy=3.25)),
    ]

    report = registry.validate(
        StrategyValidationRequest(
            strategy_family=STRATEGY_FAMILY,
            records=records,
            current_capital_usd=300.0,
            parameters={
                "min_apy_change": 1.0,
                "now": datetime(2026, 5, 17, 3, tzinfo=UTC),
            },
        )
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_default_registry_defi_yield_invalid_parameters_fail_closed():
    registry = default_strategy_registry(current_capital_usd=300.0)
    records = [
        _record(_yield_snapshot(1, apy=2.0)),
        _record(_yield_snapshot(2, apy=3.25)),
    ]

    for parameters in (
        {"min_observations": 2.9},
        {"min_observations": True},
        {"min_tvl_usd": True},
    ):
        report = registry.validate(
            StrategyValidationRequest(
                strategy_family=STRATEGY_FAMILY,
                records=records,
                current_capital_usd=300.0,
                parameters=parameters,
            )
        )

        assert report.approved is False
        assert report.blocked_reasons == ("strategy_validation_error",)
