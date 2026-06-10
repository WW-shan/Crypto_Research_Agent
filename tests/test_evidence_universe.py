from __future__ import annotations

from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from crypto_alpha_agent.data.models import (
    BasisRecord,
    DataSuitability,
    DefiYieldSnapshot,
    DexPairSnapshot,
    LongShortRatioRecord,
    MarketCandle,
    PremiumIndexKlineRecord,
    SourceRecord,
    TakerBuySellVolumeRecord,
)
from crypto_alpha_agent.data.store import ResearchDataStore


START = datetime(2026, 5, 1, tzinfo=UTC)
NOW = datetime(2026, 6, 8, tzinfo=UTC)


def test_evidence_universe_reports_coverage_and_source_roles(tmp_path):
    db_path = tmp_path / "research.sqlite"
    records = [
        _market_candle("BTC/USDT", START, record_id_suffix="a"),
        _market_candle("BTC/USDT", START, record_id_suffix="duplicate"),
        _market_candle("BTC/USDT", START + timedelta(hours=1), record_id_suffix="b"),
        _market_candle("ETH/USDT", START + timedelta(hours=1), record_id_suffix="c"),
        _premium("BTCUSDT", START),
        _basis("BTCUSDT", START),
        _long_short("BTCUSDT", START),
        _taker("BTCUSDT", START),
        _dex_pair(NOW),
        _defi_yield(NOW),
        _source_health("binance_public", "um_futures_ohlcv", START, network_route="proxy"),
        _source_health("binance_usdm", "premium_index_klines", START, network_route="proxy"),
        _source_health("binance_usdm", "basis", START, network_route="proxy"),
        _source_health("binance_usdm", "global_long_short_account_ratio", START, network_route="proxy"),
        _source_health("binance_usdm", "taker_buy_sell_volume", START, network_route="proxy"),
        _source_health("dexscreener", "pairs", NOW, network_route="direct"),
        _source_health("defillama", "yield_pools", NOW, network_route="direct"),
    ]
    ResearchDataStore(db_path).upsert_records(records)

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    before = _record_snapshot(db_path)
    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=2,
    )

    assets = {asset.symbol: asset for asset in report.assets}
    coverage = {
        (item.source, item.record_type, item.feed): item
        for item in report.source_coverage
    }
    reason_codes = {issue.reason_code for issue in report.quality_issues}

    assert report.symbols == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    assert [asset.exchange_symbol for asset in report.assets] == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    ]
    assert assets["BTC/USDT"].market_records == 3
    assert assets["ETH/USDT"].market_records == 1
    assert assets["SOL/USDT"].market_records == 0
    assert "insufficient_history_window" in assets["ETH/USDT"].blocked_reasons
    assert "missing_market_history" in assets["SOL/USDT"].blocked_reasons

    assert coverage[("binance_public", "market_candle", "1h")].records == 4
    assert coverage[("binance_public", "market_candle", "1h")].network_routes == [
        "proxy"
    ]
    assert coverage[("binance_usdm", "premium_index_kline", "premium_index_kline")].records == 1
    assert coverage[("binance_usdm", "basis", "basis")].latest_30_day_limited is False
    assert coverage[("binance_usdm", "basis", "basis")].start_end_pagination is True
    assert coverage[
        ("binance_usdm", "long_short_account_ratio", "long_short_account_ratio")
    ].latest_30_day_limited is True
    assert coverage[
        ("binance_usdm", "taker_buy_sell_volume", "taker_buy_sell_volume")
    ].latest_30_day_limited is True
    assert coverage[("dexscreener", "dex_pair", "pairs")].role == "watchlist_or_regime_only"
    assert coverage[("defillama", "defi_yield", "yield_pools")].role == "watchlist_or_regime_only"

    assert report.point_in_time_universe is False
    assert "duplicate_timestamps" in reason_codes
    assert "missing_market_history" in reason_codes
    assert "timestamp_alignment_gap" in reason_codes
    assert "lookahead_universe_risk" in reason_codes
    assert "watchlist_only_source" in reason_codes
    assert "stale_source_health" in reason_codes
    assert report.uses_real_capital is False
    assert report.live_order_routing is False
    assert _record_snapshot(db_path) == before


def test_evidence_universe_is_point_in_time_when_discovery_precedes_window(tmp_path):
    db_path = tmp_path / "research.sqlite"
    records = [
        _market_candle("BTC/USDT", START),
        _market_candle("BTC/USDT", START + timedelta(hours=1)),
        _source_health("binance_public", "ohlcv", START),
        _dex_pair(START - timedelta(days=1)),
    ]
    ResearchDataStore(db_path).upsert_records(records)

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=START + timedelta(hours=2),
        min_history_records=2,
    )

    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert report.point_in_time_universe is True
    assert "lookahead_universe_risk" not in reason_codes
    assert "watchlist_only_source" in reason_codes


def test_evidence_universe_blocks_source_without_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _market_candle("BTC/USDT", START + timedelta(hours=1)),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=2,
    )

    coverage = report.source_coverage[0]
    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert coverage.source_health_present is False
    assert "source_probe_required" in coverage.blocked_reasons
    assert "source_probe_required" in reason_codes


def test_evidence_universe_filters_future_market_and_derivatives_without_lookahead(tmp_path):
    db_path = tmp_path / "research.sqlite"
    future = START + timedelta(days=1)
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _market_candle("BTC/USDT", START + timedelta(hours=1)),
            _market_candle("BTC/USDT", future),
            _premium("BTCUSDT", future),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("binance_usdm", "premium_index_klines", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=future,
        min_history_records=2,
    )

    coverage = {
        (item.source, item.record_type, item.feed): item
        for item in report.source_coverage
    }
    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert report.assets[0].market_records == 2
    assert ("binance_usdm", "premium_index_kline", "premium_index_kline") not in coverage
    assert report.point_in_time_universe is True
    assert "lookahead_universe_risk" not in reason_codes


def test_evidence_universe_flags_future_discovery_for_past_window(tmp_path):
    db_path = tmp_path / "research.sqlite"
    future = START + timedelta(days=1)
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _market_candle("BTC/USDT", START + timedelta(hours=1)),
            _dex_pair(future),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("dexscreener", "pairs", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=future,
        min_history_records=2,
    )

    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert report.point_in_time_universe is False
    assert "lookahead_universe_risk" in reason_codes


def test_evidence_universe_flags_future_discovery_when_only_end_is_supplied(tmp_path):
    db_path = tmp_path / "research.sqlite"
    evaluation_end = START + timedelta(hours=2)
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _market_candle("BTC/USDT", START + timedelta(hours=1)),
            _dex_pair(evaluation_end + timedelta(hours=1)),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("dexscreener", "pairs", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_end=evaluation_end,
        now=NOW,
        min_history_records=2,
    )

    assert report.point_in_time_universe is False
    assert "lookahead_universe_risk" in report.reason_codes


def test_evidence_universe_does_not_flag_redundant_qualified_market_sources_as_duplicates(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle(
                "BTC/USDT",
                START,
                source="binance_public",
                close=100.0,
                record_id_suffix="public-0",
            ),
            _market_candle(
                "BTC/USDT",
                START,
                source="ccxt",
                close=101.0,
                record_id_suffix="ccxt-0",
            ),
            _market_candle(
                "BTC/USDT",
                START + timedelta(hours=1),
                source="binance_public",
                close=102.0,
                record_id_suffix="public-1",
            ),
            _market_candle(
                "BTC/USDT",
                START + timedelta(hours=1),
                source="ccxt",
                close=103.0,
                record_id_suffix="ccxt-1",
            ),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("ccxt", "ohlcv", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=START + timedelta(hours=2),
        min_history_records=2,
    )

    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert report.assets[0].market_records == 2
    assert "duplicate_timestamps" not in reason_codes


def test_evidence_universe_requires_feed_level_source_health(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _premium("BTCUSDT", START),
            _basis("BTCUSDT", START),
            _source_health("binance_usdm", "premium_index_klines", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=START + timedelta(hours=2),
        min_history_records=1,
    )

    coverage = {
        (item.source, item.record_type, item.feed): item
        for item in report.source_coverage
    }
    assert coverage[
        ("binance_usdm", "premium_index_kline", "premium_index_kline")
    ].source_health_present is True
    assert coverage[("binance_usdm", "basis", "basis")].source_health_present is False
    assert "source_probe_required" in coverage[
        ("binance_usdm", "basis", "basis")
    ].blocked_reasons


def test_evidence_universe_reports_funding_and_open_interest_source_coverage(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _funding_rate("BTC/USDT", START, source="binance_usdm"),
            _open_interest("BTC/USDT", START, source="binance_usdm"),
            _long_short("BTCUSDT", START),
            _taker("BTCUSDT", START),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("binance_usdm", "funding_rate_history", START),
            _source_health("binance_usdm", "open_interest_history", START),
            _source_health("binance_usdm", "global_long_short_account_ratio", START),
            _source_health("binance_usdm", "taker_buy_sell_volume", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=START + timedelta(hours=2),
        min_history_records=1,
    )

    coverage = {
        (item.source, item.record_type, item.feed): item
        for item in report.source_coverage
    }
    funding = coverage[("binance_usdm", "funding_rate", "funding_rate_history")]
    open_interest = coverage[("binance_usdm", "open_interest", "open_interest_history")]
    long_short = coverage[
        ("binance_usdm", "long_short_account_ratio", "long_short_account_ratio")
    ]
    taker = coverage[("binance_usdm", "taker_buy_sell_volume", "taker_buy_sell_volume")]

    assert funding.role == "recent_derivatives_context"
    assert funding.source_health_present is True
    assert funding.latest_30_day_limited is False
    assert funding.start_end_pagination is True
    assert funding.max_limit == 1000
    assert open_interest.role == "recent_derivatives_context"
    assert open_interest.source_health_present is True
    assert open_interest.latest_30_day_limited is False
    assert open_interest.start_end_pagination is True
    assert open_interest.max_limit == 500
    assert long_short.latest_30_day_limited is True
    assert taker.latest_30_day_limited is True


def test_evidence_universe_uses_latest_source_health_for_staleness(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health(
                "binance_public",
                "um_futures_ohlcv",
                NOW - timedelta(days=1),
            ),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=1,
    )

    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert "stale_source_health" not in reason_codes
    assert report.source_coverage[0].source_health_present is True


def test_evidence_universe_failed_and_malformed_health_fail_closed(tmp_path):
    db_path = tmp_path / "research.sqlite"
    malformed = _source_health("binance_public", "um_futures_ohlcv", START)
    malformed.payload["observed_at"] = "not-a-date"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _source_health(
                "binance_public",
                "um_futures_ohlcv",
                START,
                success=False,
            ),
            malformed,
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=1,
    )

    reason_codes = {issue.reason_code for issue in report.quality_issues}
    assert report.source_coverage[0].source_health_present is False
    assert "source_probe_required" in report.source_coverage[0].blocked_reasons
    assert "source_probe_required" in reason_codes


def test_evidence_universe_latest_malformed_health_overrides_older_success(tmp_path):
    db_path = tmp_path / "research.sqlite"
    malformed = _source_health(
        "binance_public",
        "um_futures_ohlcv",
        START + timedelta(hours=1),
    )
    malformed.payload["success"] = "yes"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _source_health("binance_public", "um_futures_ohlcv", START),
            malformed,
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=1,
    )

    assert report.source_coverage[0].source_health_present is False
    assert "source_probe_required" in report.source_coverage[0].blocked_reasons
    assert "source_probe_required" in report.reason_codes


def test_evidence_universe_latest_missing_feed_health_overrides_older_success(tmp_path):
    db_path = tmp_path / "research.sqlite"
    malformed = _source_health(
        "binance_public",
        "um_futures_ohlcv",
        START + timedelta(hours=1),
    )
    malformed.payload.pop("feed")
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _source_health("binance_public", "um_futures_ohlcv", START),
            malformed,
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=1,
    )

    assert report.source_coverage[0].source_health_present is False
    assert "source_probe_required" in report.source_coverage[0].blocked_reasons
    assert "source_probe_required" in report.reason_codes


def test_evidence_universe_duplicate_timestamps_do_not_satisfy_history_window(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START, record_id_suffix="a"),
            _market_candle("BTC/USDT", START, record_id_suffix="duplicate"),
            _source_health("binance_public", "um_futures_ohlcv", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
        min_history_records=2,
    )

    assert report.assets[0].market_records == 2
    assert "insufficient_history_window" in report.assets[0].blocked_reasons
    assert "duplicate_timestamps" in report.reason_codes


def test_evidence_universe_excludes_unrelated_dex_pairs(tmp_path):
    db_path = tmp_path / "research.sqlite"
    future = START + timedelta(days=1)
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _market_candle("BTC/USDT", START + timedelta(hours=1)),
            _dex_pair(
                future,
                base_token="ETH",
                quote_token="USDT",
                pair_address="0xeth",
            ),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("dexscreener", "pairs", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=future,
        min_history_records=2,
    )

    coverage_keys = {
        (item.source, item.record_type, item.feed)
        for item in report.source_coverage
    }
    assert ("dexscreener", "dex_pair", "pairs") not in coverage_keys
    assert report.point_in_time_universe is True
    assert "lookahead_universe_risk" not in report.reason_codes


def test_evidence_universe_excludes_dex_pair_boundary_collisions(tmp_path):
    db_path = tmp_path / "research.sqlite"
    future = START + timedelta(days=1)
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", START),
            _market_candle("BTC/USDT", START + timedelta(hours=1)),
            _dex_pair(
                future,
                base_token="BT",
                quote_token="CUSDT",
                pair_address="0xboundary",
            ),
            _source_health("binance_public", "um_futures_ohlcv", START),
            _source_health("dexscreener", "pairs", START),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=future,
        min_history_records=2,
    )

    coverage_keys = {
        (item.source, item.record_type, item.feed)
        for item in report.source_coverage
    }
    assert ("dexscreener", "dex_pair", "pairs") not in coverage_keys
    assert report.point_in_time_universe is True
    assert "lookahead_universe_risk" not in report.reason_codes


def test_evidence_universe_missing_database_is_read_only(tmp_path):
    db_path = tmp_path / "missing.sqlite"

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT"],
        timeframe="1h",
        evaluation_start=START,
        evaluation_end=START + timedelta(hours=2),
        now=NOW,
    )

    assert not db_path.exists()
    assert report.assets[0].market_records == 0
    assert "missing_market_history" in report.reason_codes


def test_evidence_universe_reports_month_and_asset_depth_gates(tmp_path):
    db_path = tmp_path / "research.sqlite"
    ResearchDataStore(db_path).upsert_records(
        [
            _market_candle("BTC/USDT", datetime(2026, 1, 1, tzinfo=UTC)),
            _market_candle("BTC/USDT", datetime(2026, 3, 1, tzinfo=UTC)),
            _market_candle("ETH/USDT", datetime(2026, 1, 1, tzinfo=UTC)),
            _source_health("binance_public", "um_futures_ohlcv", NOW),
        ]
    )

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    report = build_evidence_universe_report(
        db_path,
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        timeframe="1h",
        evaluation_start=datetime(2026, 1, 1, tzinfo=UTC),
        evaluation_end=datetime(2026, 4, 1, tzinfo=UTC),
        now=NOW,
        min_history_records=1,
        requested_months=[(2026, 1), (2026, 2), (2026, 3)],
        min_unique_months=3,
        min_asset_count=2,
    )

    assets = {asset.symbol: asset for asset in report.assets}
    assert report.requested_market_months == ["2026-01", "2026-02", "2026-03"]
    assert report.min_unique_months == 3
    assert report.min_asset_count == 2
    assert report.eligible_asset_count == 0
    assert "insufficient_month_coverage" in report.reason_codes
    assert "insufficient_asset_coverage" in report.reason_codes

    btc = assets["BTC/USDT"]
    assert btc.unique_market_months == 2
    assert btc.requested_market_months == 3
    assert btc.missing_market_months == ["2026-02"]
    assert btc.point_in_time_eligible is False
    assert "insufficient_month_coverage" in btc.blocked_reasons

    eth = assets["ETH/USDT"]
    assert eth.unique_market_months == 1
    assert eth.missing_market_months == ["2026-02", "2026-03"]
    assert "insufficient_month_coverage" in eth.blocked_reasons

    sol = assets["SOL/USDT"]
    assert sol.unique_market_months == 0
    assert sol.missing_market_months == ["2026-01", "2026-02", "2026-03"]
    assert "missing_market_history" in sol.blocked_reasons
    assert "insufficient_month_coverage" in sol.blocked_reasons


def test_evidence_universe_existing_database_schema_errors_are_not_silently_empty(tmp_path):
    db_path = tmp_path / "invalid.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE unrelated (id TEXT PRIMARY KEY)")

    from crypto_alpha_agent.pipeline.evidence_universe import (
        build_evidence_universe_report,
    )

    with pytest.raises(RuntimeError, match="cannot read evidence records"):
        build_evidence_universe_report(
            db_path,
            symbols=["BTC/USDT"],
            timeframe="1h",
            evaluation_start=START,
            evaluation_end=START + timedelta(hours=2),
            now=NOW,
        )


def test_evidence_universe_models_are_strict():
    from pydantic import ValidationError

    from crypto_alpha_agent.pipeline.evidence_universe import (
        EvidenceUniverseReport,
        UniverseAsset,
        UniverseQualityIssue,
        UniverseSourceCoverage,
    )

    with pytest.raises(ValidationError):
        UniverseAsset(
            symbol="BTC/USDT",
            exchange_symbol="BTCUSDT",
            market_records="1",
        )
    with pytest.raises(ValidationError):
        UniverseSourceCoverage(
            source="binance_public",
            record_type="market_candle",
            feed="1h",
            role="execution_history",
            records="1",
        )
    with pytest.raises(ValidationError):
        UniverseQualityIssue(
            reason_code="missing_market_history",
            severity="error",
            source="binance_public",
            record_type="market_candle",
            message="missing",
            extra_field="not allowed",
        )
    with pytest.raises(ValidationError):
        EvidenceUniverseReport(
            generated_at=NOW,
            symbols=["BTC/USDT"],
            timeframe="1h",
            point_in_time_universe=True,
            assets=[],
            source_coverage=[],
            quality_issues=[],
            uses_real_capital=True,
        )


def _market_candle(
    symbol: str,
    timestamp: datetime,
    *,
    source: str = "binance_public",
    close: float = 100.5,
    record_id_suffix: str | None = None,
) -> SourceRecord:
    record = MarketCandle(
        source=source,
        venue="binance_usdm",
        symbol=symbol,
        timestamp=timestamp,
        timeframe="1h",
        open=100.0,
        high=101.0,
        low=99.0,
        close=close,
        volume=25.0,
        suitability=DataSuitability(),
    ).to_source_record()
    if record_id_suffix is None:
        return record
    return record.model_copy(update={"record_id": f"{record.record_id}:{record_id_suffix}"})


def _premium(symbol: str, timestamp: datetime) -> SourceRecord:
    return PremiumIndexKlineRecord(
        source="binance_usdm",
        venue="binance",
        symbol=symbol,
        timestamp=timestamp,
        interval="1h",
        open=-0.0001,
        high=0.0001,
        low=-0.0002,
        close=0.0,
    ).to_source_record()


def _basis(pair: str, timestamp: datetime) -> SourceRecord:
    return BasisRecord(
        source="binance_usdm",
        venue="binance",
        pair=pair,
        contract_type="PERPETUAL",
        period="1h",
        timestamp=timestamp,
        index_price=100.0,
        futures_price=100.1,
        basis=0.1,
        basis_rate=0.001,
    ).to_source_record()


def _long_short(symbol: str, timestamp: datetime) -> SourceRecord:
    return LongShortRatioRecord(
        source="binance_usdm",
        venue="binance",
        symbol=symbol,
        period="1h",
        timestamp=timestamp,
        long_short_ratio=1.2,
        long_account=0.55,
        short_account=0.45,
    ).to_source_record()


def _taker(symbol: str, timestamp: datetime) -> SourceRecord:
    return TakerBuySellVolumeRecord(
        source="binance_usdm",
        venue="binance",
        symbol=symbol,
        period="1h",
        timestamp=timestamp,
        buy_sell_ratio=1.1,
        buy_volume=110.0,
        sell_volume=100.0,
    ).to_source_record()


def _funding_rate(
    symbol: str,
    timestamp: datetime,
    *,
    source: str = "ccxt",
) -> SourceRecord:
    return SourceRecord(
        record_id=f"{source}:binance:{symbol}:funding_rate:{timestamp.isoformat()}",
        source=source,
        record_type="funding_rate",
        observed_at=timestamp,
        payload={
            "source": source,
            "venue": "binance",
            "symbol": symbol,
            "timestamp": timestamp.isoformat(),
            "funding_rate": 0.0005,
        },
    )


def _open_interest(
    symbol: str,
    timestamp: datetime,
    *,
    source: str = "ccxt",
) -> SourceRecord:
    return SourceRecord(
        record_id=f"{source}:binance:{symbol}:open_interest:1h:{timestamp.isoformat()}",
        source=source,
        record_type="open_interest",
        observed_at=timestamp,
        payload={
            "source": source,
            "venue": "binance",
            "symbol": symbol,
            "timestamp": timestamp.isoformat(),
            "timeframe": "1h",
            "open_interest": 1000.0,
            "open_interest_value": 100000.0,
        },
    )


def _dex_pair(
    observed_at: datetime,
    *,
    base_token: str = "BTC",
    quote_token: str = "USDT",
    pair_address: str = "0xabc",
) -> SourceRecord:
    snapshot = DexPairSnapshot(
        source="dexscreener",
        chain="ethereum",
        dex="uniswap",
        pair_address=pair_address,
        base_token=base_token,
        quote_token=quote_token,
        price_usd=100.0,
        liquidity_usd=1_000_000.0,
        volume_24h_usd=250_000.0,
        observed_at=observed_at,
    )
    return SourceRecord(
        record_id=f"dexscreener:ethereum:uniswap:{pair_address}:{observed_at.isoformat()}",
        source="dexscreener",
        record_type="dex_pair",
        observed_at=observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _defi_yield(observed_at: datetime) -> SourceRecord:
    snapshot = DefiYieldSnapshot(
        source="defillama",
        chain="Ethereum",
        project="Example",
        symbol="USDT",
        tvl_usd=1_000_000.0,
        apy=4.0,
        observed_at=observed_at,
    )
    return SourceRecord(
        record_id=f"defillama:yield:example:{observed_at.isoformat()}",
        source="defillama",
        record_type="defi_yield",
        observed_at=observed_at,
        payload=snapshot.model_dump(mode="json"),
    )


def _source_health(
    source: str,
    feed: str,
    observed_at: datetime,
    *,
    network_route: str = "direct",
    success: bool = True,
) -> SourceRecord:
    return SourceRecord(
        record_id=f"{source}:{feed}:source_health:{observed_at.isoformat()}",
        source=source,
        record_type="source_health",
        observed_at=observed_at,
        payload={
            "source": source,
            "feed": feed,
            "success": success,
            "attempts": 1,
            "failure": None if success else "probe failed",
            "observed_at": observed_at.isoformat(),
            "records_fetched": 1,
            "records_written": 1,
            "network_route": network_route,
        },
    )


def _record_snapshot(db_path) -> list[tuple[str, str, datetime]]:
    return [
        (record.record_id, record.record_type, record.observed_at)
        for record in ResearchDataStore(db_path).load_records()
    ]
