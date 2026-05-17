from datetime import UTC, datetime, timedelta

from crypto_alpha_agent.data.models import DataSuitability, DexPairSnapshot, SourceRecord
from crypto_alpha_agent.strategy.dex_liquidity_watchlist import (
    STRATEGY_FAMILY,
    validate_dex_liquidity_watchlist,
)
from crypto_alpha_agent.strategy.models import StrategyPaperRequest, StrategyValidationRequest
from crypto_alpha_agent.strategy.registry import default_strategy_registry


def _dex_snapshot(
    hour: int,
    *,
    chain: str = "base",
    dex: str = "uniswap",
    pair_address: str = "0xpair",
    base_token: str = "ABC",
    quote_token: str = "USDC",
    liquidity_usd: float = 150_000.0,
    volume_24h_usd: float = 20_000.0,
    observed_at: datetime | None = None,
    raw: dict[str, object] | None = None,
    execution_role: str = "research_only",
) -> DexPairSnapshot:
    return DexPairSnapshot(
        source="dexscreener",
        chain=chain,
        dex=dex,
        pair_address=pair_address,
        base_token=base_token,
        quote_token=quote_token,
        price_usd=1.0,
        liquidity_usd=liquidity_usd,
        volume_24h_usd=volume_24h_usd,
        observed_at=observed_at or datetime(2026, 5, 17, hour, tzinfo=UTC),
        suitability=DataSuitability(execution_role=execution_role),
        raw=raw or {},
    )


def _source_record(snapshot: DexPairSnapshot) -> SourceRecord:
    return SourceRecord(
        record_id=(
            f"dexscreener:{snapshot.chain}:{snapshot.dex}:{snapshot.pair_address}:"
            f"{snapshot.observed_at.isoformat()}"
        ),
        source="dexscreener",
        record_type="dex_pair",
        observed_at=snapshot.observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _record(snapshot: DexPairSnapshot) -> dict[str, object]:
    return _source_record(snapshot).model_dump(mode="json")


def test_liquidity_increase_creates_research_watchlist_candidate():
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=20_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=150_000.0, volume_24h_usd=22_000.0)),
        {"record_type": "market_candle", "payload": {"ignored": True}},
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.strategy_family == STRATEGY_FAMILY
    assert report.validator_name == "dex_liquidity_watchlist"
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert report.metrics["execution_role"] == "research_only"
    assert report.metrics["paper_watchlist_only"] is True
    assert report.metrics["candidate_count"] == 1
    assert report.metrics["candidates"] == [
        {
            "chain": "base",
            "dex": "uniswap",
            "pair_address": "0xpair",
            "base_token": "ABC",
            "quote_token": "USDC",
            "pair_id": "base:uniswap:0xpair",
            "latest_observed_at": "2026-05-17T02:00:00Z",
            "prior_observed_at": "2026-05-17T01:00:00Z",
            "latest_liquidity_usd": 150_000.0,
            "prior_liquidity_usd": 100_000.0,
            "liquidity_change_pct": 0.5,
            "latest_volume_24h_usd": 22_000.0,
            "prior_volume_24h_usd": 20_000.0,
            "volume_change_pct": 0.1,
            "liquidity_direction": "up",
            "volume_direction": "up",
        }
    ]


def test_volume_increase_from_direct_dex_pair_snapshots_creates_candidate():
    records = [
        _dex_snapshot(1, liquidity_usd=200_000.0, volume_24h_usd=10_000.0).model_dump(
            mode="json"
        ),
        _dex_snapshot(2, liquidity_usd=210_000.0, volume_24h_usd=15_000.0).model_dump(
            mode="json"
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1
    assert report.metrics["candidates"][0]["volume_change_pct"] == 0.5
    assert report.metrics["candidates"][0]["pair_id"] == "base:uniswap:0xpair"


def test_direct_dex_pair_snapshot_model_instances_create_candidate():
    records = [
        _dex_snapshot(1, liquidity_usd=200_000.0, volume_24h_usd=10_000.0),
        _dex_snapshot(2, liquidity_usd=210_000.0, volume_24h_usd=15_000.0),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_source_record_model_instances_create_candidate():
    records = [
        _source_record(_dex_snapshot(1, liquidity_usd=200_000.0, volume_24h_usd=10_000.0)),
        _source_record(_dex_snapshot(2, liquidity_usd=210_000.0, volume_24h_usd=15_000.0)),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_non_json_model_dump_records_create_candidate():
    records = [
        _source_record(
            _dex_snapshot(1, liquidity_usd=200_000.0, volume_24h_usd=10_000.0)
        ).model_dump(),
        _source_record(
            _dex_snapshot(2, liquidity_usd=210_000.0, volume_24h_usd=15_000.0)
        ).model_dump(),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_direct_model_dump_records_with_datetimes_create_candidate():
    records = [
        _dex_snapshot(
            1,
            liquidity_usd=200_000.0,
            volume_24h_usd=10_000.0,
        ).model_dump(),
        _dex_snapshot(
            2,
            liquidity_usd=210_000.0,
            volume_24h_usd=15_000.0,
        ).model_dump(),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_thin_liquidity_blocks_with_insufficient_liquidity():
    records = [
        _record(_dex_snapshot(1, liquidity_usd=50_000.0, volume_24h_usd=20_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=60_000.0, volume_24h_usd=40_000.0)),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_usd=100_000.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_liquidity",)
    assert report.metrics["candidate_count"] == 0


def test_low_volume_blocks_with_insufficient_volume():
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=5_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=150_000.0, volume_24h_usd=6_000.0)),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_volume_24h_usd=10_000.0,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_volume",)


def test_missing_prior_observations_blocks_with_insufficient_history():
    records = [_record(_dex_snapshot(1))]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_history",)


def test_unsupported_chain_and_stale_source_block():
    records = [
        _record(
            _dex_snapshot(
                1,
                chain="solana",
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
                observed_at=datetime(2020, 1, 1, 1, tzinfo=UTC),
            )
        ),
        _record(
            _dex_snapshot(
                2,
                chain="solana",
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
                observed_at=datetime(2020, 1, 1, 2, tzinfo=UTC),
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert set(report.blocked_reasons) >= {"unsupported_chain", "stale_source"}


def test_direct_dex_execution_attempt_blocks():
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=10_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=150_000.0, volume_24h_usd=20_000.0)),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        require_research_only=False,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("direct_dex_execution_blocked",)
    assert report.metrics["execution_role"] == "research_only"
    assert report.metrics["paper_watchlist_only"] is True


def test_research_and_paper_dex_snapshots_block_direct_execution():
    records = [
        _record(
            _dex_snapshot(
                1,
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
                execution_role="research_and_paper",
            )
        ),
        _record(
            _dex_snapshot(
                2,
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
                execution_role="research_and_paper",
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("direct_dex_execution_blocked",)
    assert report.metrics["candidate_count"] == 1
    assert report.metrics["observed_execution_roles"] == ["research_and_paper"]


def test_distinct_pair_addresses_with_same_symbols_do_not_mix():
    records = [
        _record(_dex_snapshot(1, pair_address="0xaaa", base_token="SAME")),
        _record(_dex_snapshot(2, pair_address="0xbbb", base_token="SAME")),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("insufficient_history",)
    assert report.metrics["candidate_count"] == 0
    assert {item["pair_id"] for item in report.metrics["rejected_group_reasons"]} == {
        "base:uniswap:0xaaa",
        "base:uniswap:0xbbb",
    }


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

    assert spec.required_record_types == ("dex_pair",)
    assert spec.required_symbols == ("*dex_pair",)
    assert spec.execution_role == "research_only"
    assert spec.supports_paper_simulation is False
    assert spec.min_capital_usd == 0.0
    assert spec.max_notional_usd == 0.0
    assert paper.status == "unsupported"
    assert paper.blocked_reasons == ("paper_simulation_not_supported",)
    assert paper.metrics == {}


def test_default_registry_validate_can_validate_family_from_records():
    registry = default_strategy_registry(current_capital_usd=300.0)
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=10_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=130_000.0, volume_24h_usd=12_000.0)),
    ]

    report = registry.validate(
        StrategyValidationRequest(
            strategy_family=STRATEGY_FAMILY,
            records=records,
            current_capital_usd=300.0,
            parameters={"now": datetime(2026, 5, 17, 3, tzinfo=UTC)},
        )
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1
    assert report.metrics["execution_role"] == "research_only"


def test_default_registry_dex_watchlist_invalid_parameters_fail_closed():
    registry = default_strategy_registry(current_capital_usd=300.0)
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=10_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=150_000.0, volume_24h_usd=20_000.0)),
    ]

    for parameters in (
        {"min_observations": 2.9},
        {"min_observations": True},
        {"min_liquidity_usd": True},
        {"min_volume_change_pct": float("inf")},
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
        assert report.metrics["execution_role"] == "research_only"


def test_default_now_blocks_old_dex_pair_records_as_stale():
    records = [
        _record(
            _dex_snapshot(
                1,
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
                observed_at=datetime(2020, 1, 1, 1, tzinfo=UTC),
            )
        ),
        _record(
            _dex_snapshot(
                2,
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
                observed_at=datetime(2020, 1, 1, 2, tzinfo=UTC),
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(records)

    assert report.approved is False
    assert "stale_source" in report.blocked_reasons


def test_missing_dex_pair_records_block_without_crashing():
    records = [
        {"record_type": "dex_pair", "payload": {"chain": "base"}},
        {"record_type": "funding_rate", "payload": {"symbol": "BTC/USDT:USDT"}},
        {"not": "a dex pair record"},
    ]

    report = validate_dex_liquidity_watchlist(records)

    assert report.approved is False
    assert report.blocked_reasons == ("missing_dex_pair_records",)


def test_no_regime_change_blocks_when_liquidity_and_volume_are_flat():
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=10_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=110_000.0, volume_24h_usd=11_000.0)),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        min_liquidity_change_pct=0.25,
        min_volume_change_pct=0.25,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("no_liquidity_or_volume_regime_change",)
    assert report.metrics["rejected_group_reasons"][0]["liquidity_direction"] == "up"


def test_pair_identity_falls_back_to_raw_pair_address():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                raw={"pairAddress": "0xrawpair"},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                raw={"pairAddress": "0xrawpair"},
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidates"][0]["pair_id"] == "base:uniswap:0xrawpair"


def test_pair_identity_falls_back_to_stable_raw_url():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                raw={"url": "https://dexscreener.com/base/0xstable"},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                raw={"url": "https://dexscreener.com/base/0xstable"},
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_pair_identity_prefers_url_over_additional_stable_fields():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                raw={"url": "https://dexscreener.com/base/0xstable"},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                raw={
                    "url": "https://dexscreener.com/base/0xstable",
                    "pairCreatedAt": 1_700_000_000,
                    "labels": ["v3"],
                },
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_pair_identity_url_ignores_token_symbol_changes():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                base_token="OLD",
                quote_token="USDC",
                raw={"url": "https://dexscreener.com/base/0xstable"},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                base_token="NEW",
                quote_token="USDC",
                raw={"url": "https://dexscreener.com/base/0xstable"},
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_pair_identity_stable_raw_fields_ignore_liquidity_changes():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                raw={
                    "pairCreatedAt": 1_700_000_000,
                    "baseToken": {"address": "0xbase"},
                    "quoteToken": {"address": "0xquote"},
                    "liquidity": {"usd": 100_000},
                },
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                raw={
                    "pairCreatedAt": 1_700_000_000,
                    "baseToken": {"address": "0xbase"},
                    "quoteToken": {"address": "0xquote"},
                    "liquidity": {"usd": 150_000},
                },
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is True
    assert report.metrics["candidate_count"] == 1


def test_labels_only_raw_identity_blocks_instead_of_merging_candidates():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                raw={"labels": ["v3"]},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                raw={"labels": ["v3"]},
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("unstable_pair_identity",)
    assert report.metrics["candidate_count"] == 0


def test_missing_stable_pair_identity_blocks_candidate():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                raw={},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                raw={},
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("unstable_pair_identity",)
    assert report.metrics["candidate_count"] == 0


def test_missing_stable_pair_identity_with_symbol_change_reports_unstable_identity():
    records = [
        _record(
            _dex_snapshot(
                1,
                pair_address="",
                base_token="OLD",
                quote_token="USDC",
                raw={},
                liquidity_usd=100_000.0,
                volume_24h_usd=10_000.0,
            )
        ),
        _record(
            _dex_snapshot(
                2,
                pair_address="",
                base_token="NEW",
                quote_token="USDC",
                raw={},
                liquidity_usd=150_000.0,
                volume_24h_usd=20_000.0,
            )
        ),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 3, tzinfo=UTC),
    )

    assert report.approved is False
    assert report.blocked_reasons == ("unstable_pair_identity",)
    assert report.metrics["candidate_count"] == 0


def test_stale_boundary_uses_max_age_hours():
    records = [
        _record(_dex_snapshot(1, liquidity_usd=100_000.0, volume_24h_usd=10_000.0)),
        _record(_dex_snapshot(2, liquidity_usd=150_000.0, volume_24h_usd=20_000.0)),
    ]

    report = validate_dex_liquidity_watchlist(
        records,
        now=datetime(2026, 5, 17, 2, tzinfo=UTC) + timedelta(hours=73),
        max_age_hours=72.0,
    )

    assert report.approved is False
    assert report.blocked_reasons == ("stale_source",)
