from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import RecordType, SourceRecord

UniverseReasonCode = Literal[
    "missing_market_history",
    "insufficient_history_window",
    "insufficient_month_coverage",
    "insufficient_asset_coverage",
    "stale_source_health",
    "duplicate_timestamps",
    "timestamp_alignment_gap",
    "lookahead_universe_risk",
    "watchlist_only_source",
    "source_probe_required",
]
UniverseSourceRole = Literal[
    "execution_history",
    "recent_derivatives_context",
    "watchlist_or_regime_only",
    "source_health",
]

_DERIVATIVES_RECENT_WINDOW_TYPES = {
    "long_short_account_ratio",
    "taker_buy_sell_volume",
}
_DERIVATIVES_TYPES = {
    "funding_rate",
    "open_interest",
    "premium_index_kline",
    "basis",
    "long_short_account_ratio",
    "taker_buy_sell_volume",
}
_WATCHLIST_TYPES = {"dex_pair", "defi_yield"}
_UNKNOWN_SOURCE_HEALTH_FEED = "__unknown__"
_MARKET_SOURCE_PRIORITY = {
    "binance_public": 0,
    "ccxt": 1,
}
_DERIVATIVES_ENDPOINT_METADATA = {
    ("binance_usdm", "funding_rate", "funding_rate_history"): {
        "endpoint_family": "GET /fapi/v1/fundingRate",
        "max_limit": 1000,
        "start_end_pagination": True,
        "latest_30_day_limited": False,
    },
    ("binance_usdm", "open_interest", "open_interest_history"): {
        "endpoint_family": "GET /futures/data/openInterestHist",
        "max_limit": 500,
        "start_end_pagination": True,
        "latest_30_day_limited": False,
    },
    ("binance_usdm", "premium_index_kline", "premium_index_kline"): {
        "endpoint_family": "GET /fapi/v1/premiumIndexKlines",
        "max_limit": 1500,
        "start_end_pagination": True,
        "latest_30_day_limited": False,
    },
    ("binance_usdm", "basis", "basis"): {
        "endpoint_family": "GET /futures/data/basis",
        "max_limit": 500,
        "start_end_pagination": True,
        "latest_30_day_limited": False,
    },
    ("binance_usdm", "long_short_account_ratio", "long_short_account_ratio"): {
        "endpoint_family": "GET /futures/data/globalLongShortAccountRatio",
        "max_limit": 500,
        "start_end_pagination": True,
        "latest_30_day_limited": True,
    },
    ("binance_usdm", "taker_buy_sell_volume", "taker_buy_sell_volume"): {
        "endpoint_family": "GET /futures/data/takerlongshortRatio",
        "max_limit": 500,
        "start_end_pagination": True,
        "latest_30_day_limited": True,
    },
}


class _StrictUniverseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class UniverseAsset(_StrictUniverseModel):
    symbol: str
    exchange_symbol: str
    market_records: int = Field(ge=0)
    first_market_timestamp: datetime | None = None
    latest_market_timestamp: datetime | None = None
    requested_market_months: int = Field(default=0, ge=0)
    unique_market_months: int = Field(default=0, ge=0)
    missing_market_months: list[str] = Field(default_factory=list)
    point_in_time_eligible: bool = True
    blocked_reasons: list[UniverseReasonCode] = Field(default_factory=list)


class UniverseSourceCoverage(_StrictUniverseModel):
    source: str
    record_type: RecordType
    feed: str
    role: UniverseSourceRole
    records: int = Field(ge=0)
    latest_observed_at: datetime | None = None
    endpoint_family: str | None = None
    max_limit: int | None = Field(default=None, ge=0)
    start_end_pagination: bool = False
    latest_30_day_limited: bool = False
    source_health_present: bool = False
    network_routes: list[str] = Field(default_factory=list)
    blocked_reasons: list[UniverseReasonCode] = Field(default_factory=list)


class UniverseQualityIssue(_StrictUniverseModel):
    reason_code: UniverseReasonCode
    severity: Literal["warning", "error"]
    source: str
    record_type: RecordType
    message: str
    symbol: str | None = None
    observed_at: datetime | None = None


class EvidenceUniverseReport(_StrictUniverseModel):
    generated_at: datetime
    symbols: list[str]
    timeframe: str
    evaluation_start: datetime | None = None
    evaluation_end: datetime | None = None
    point_in_time_universe: bool
    requested_market_months: list[str] = Field(default_factory=list)
    min_unique_months: int = Field(default=0, ge=0)
    min_asset_count: int = Field(default=0, ge=0)
    eligible_asset_count: int = Field(default=0, ge=0)
    reason_codes: list[UniverseReasonCode] = Field(default_factory=list)
    assets: list[UniverseAsset]
    source_coverage: list[UniverseSourceCoverage]
    quality_issues: list[UniverseQualityIssue]
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_evidence_universe_report(
    db_path: str | Path,
    *,
    symbols: list[str],
    timeframe: str,
    evaluation_start: datetime | None = None,
    evaluation_end: datetime | None = None,
    now: datetime | None = None,
    min_history_records: int = 24,
    requested_months: list[tuple[int, int]] | None = None,
    min_unique_months: int = 0,
    min_asset_count: int = 0,
    max_source_health_age: timedelta = timedelta(days=7),
) -> EvidenceUniverseReport:
    normalized_symbols = _dedupe_preserving_order(symbols)
    normalized_requested_months = _normalize_requested_months(requested_months)
    records = _load_records_read_only(db_path)
    generated_at = _aware(now) if now is not None else _latest_observed_at(records)
    issues: list[UniverseQualityIssue] = []
    source_health = _source_health_by_feed(records, issues)
    market_by_symbol = _market_records_by_symbol(
        records,
        normalized_symbols,
        timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
    )

    assets = [
        _asset_report(
            symbol,
            market_by_symbol[symbol],
            min_history_records=min_history_records,
            requested_months=normalized_requested_months,
            min_unique_months=min_unique_months,
            issues=issues,
        )
        for symbol in normalized_symbols
    ]
    eligible_asset_count = sum(1 for asset in assets if asset.point_in_time_eligible)
    if min_asset_count and eligible_asset_count < min_asset_count:
        issues.append(
            UniverseQualityIssue(
                reason_code="insufficient_asset_coverage",
                severity="error",
                source="binance_public",
                record_type="market_candle",
                message=(
                    f"{eligible_asset_count} point-in-time eligible assets; "
                    f"requires at least {min_asset_count}"
                ),
            )
        )

    issues.extend(_duplicate_market_timestamp_issues(market_by_symbol))
    issues.extend(_timestamp_alignment_issues(market_by_symbol, normalized_symbols, timeframe))
    source_coverage = _source_coverage(
        records,
        source_health,
        normalized_symbols,
        timeframe,
        evaluation_start,
        evaluation_end,
        generated_at,
        max_source_health_age,
        issues,
    )
    point_in_time_universe = not _append_lookahead_issues(
        records,
        symbols=normalized_symbols,
        timeframe=timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
        issues=issues,
    )

    reason_codes = _dedupe_preserving_order(issue.reason_code for issue in issues)
    return EvidenceUniverseReport(
        generated_at=generated_at,
        symbols=normalized_symbols,
        timeframe=timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
        point_in_time_universe=point_in_time_universe,
        requested_market_months=[_format_month(year, month) for year, month in normalized_requested_months],
        min_unique_months=min_unique_months,
        min_asset_count=min_asset_count,
        eligible_asset_count=eligible_asset_count,
        reason_codes=reason_codes,
        assets=assets,
        source_coverage=source_coverage,
        quality_issues=issues,
        uses_real_capital=False,
        live_order_routing=False,
    )


def _asset_report(
    symbol: str,
    market_records: list[SourceRecord],
    *,
    min_history_records: int,
    requested_months: tuple[tuple[int, int], ...],
    min_unique_months: int,
    issues: list[UniverseQualityIssue],
) -> UniverseAsset:
    timestamps = sorted(record.observed_at for record in market_records)
    unique_timestamps = set(timestamps)
    actual_months = {(timestamp.year, timestamp.month) for timestamp in unique_timestamps}
    if requested_months:
        unique_market_months = len(actual_months & set(requested_months))
        missing_market_months = [
            _format_month(year, month)
            for year, month in requested_months
            if (year, month) not in actual_months
        ]
    else:
        unique_market_months = len(actual_months)
        missing_market_months = []
    blocked_reasons: list[UniverseReasonCode] = []
    if not market_records:
        blocked_reasons.append("missing_market_history")
        issues.append(
            UniverseQualityIssue(
                reason_code="missing_market_history",
                severity="error",
                source="binance_public",
                record_type="market_candle",
                symbol=symbol,
                message=f"no market candles for {symbol}",
            )
        )
    elif len(unique_timestamps) < min_history_records:
        blocked_reasons.append("insufficient_history_window")
        issues.append(
            UniverseQualityIssue(
                reason_code="insufficient_history_window",
                severity="error",
                source=market_records[0].source,
                record_type="market_candle",
                symbol=symbol,
                message=(
                    f"{symbol} has {len(unique_timestamps)} unique market timestamps; "
                    f"requires at least {min_history_records}"
                ),
                observed_at=timestamps[-1],
            )
        )
    if requested_months and min_unique_months and unique_market_months < min_unique_months:
        blocked_reasons.append("insufficient_month_coverage")
        issues.append(
            UniverseQualityIssue(
                reason_code="insufficient_month_coverage",
                severity="error",
                source=market_records[0].source if market_records else "binance_public",
                record_type="market_candle",
                symbol=symbol,
                message=(
                    f"{symbol} covers {unique_market_months} requested months; "
                    f"requires at least {min_unique_months}"
                ),
                observed_at=timestamps[-1] if timestamps else None,
            )
        )

    return UniverseAsset(
        symbol=symbol,
        exchange_symbol=_exchange_symbol(symbol),
        market_records=len(market_records),
        first_market_timestamp=timestamps[0] if timestamps else None,
        latest_market_timestamp=timestamps[-1] if timestamps else None,
        requested_market_months=len(requested_months),
        unique_market_months=unique_market_months,
        missing_market_months=missing_market_months,
        point_in_time_eligible=not blocked_reasons,
        blocked_reasons=blocked_reasons,
    )


def _source_coverage(
    records: list[SourceRecord],
    source_health: dict[tuple[str, str], list[_SourceHealth]],
    symbols: list[str],
    timeframe: str,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
    generated_at: datetime,
    max_source_health_age: timedelta,
    issues: list[UniverseQualityIssue],
) -> list[UniverseSourceCoverage]:
    grouped: dict[tuple[str, str, str], list[SourceRecord]] = defaultdict(list)
    for record in _coverage_records(
        records,
        symbols=symbols,
        timeframe=timeframe,
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
    ):
        if record.record_type == "source_health":
            continue
        role = _source_role(record)
        if role is None:
            continue
        grouped[(record.source, record.record_type, _coverage_feed(record))].append(record)

    coverage_items: list[UniverseSourceCoverage] = []
    for key, group_records in sorted(grouped.items()):
        source, record_type, feed = key
        endpoint_metadata = _endpoint_metadata(source, record_type, feed)
        required_health_feeds = _required_health_feeds(record_type, group_records)
        latest_health_rows = [
            _latest_health(source_health.get((source, health_feed), []))
            for health_feed in required_health_feeds
        ]
        latest_unknown_health = _latest_health(
            source_health.get((source, _UNKNOWN_SOURCE_HEALTH_FEED), [])
        )
        known_health_observed_at = [
            health.observed_at for health in latest_health_rows if health is not None
        ]
        unknown_health_blocks = latest_unknown_health is not None and (
            not known_health_observed_at
            or latest_unknown_health.observed_at >= max(known_health_observed_at)
        )
        source_health_present = (
            all(health is not None and health.success for health in latest_health_rows)
            and not unknown_health_blocks
        )
        routes = _dedupe_preserving_order(
            health.network_route
            for health in latest_health_rows
            if health is not None and health.network_route
        )
        blocked_reasons: list[UniverseReasonCode] = []
        if not source_health_present:
            blocked_reasons.append("source_probe_required")
            missing_feeds = [
                health_feed
                for health_feed, health in zip(required_health_feeds, latest_health_rows, strict=True)
                if health is None or not health.success
            ]
            if unknown_health_blocks:
                missing_feeds.append("unknown")
            issues.append(
                UniverseQualityIssue(
                    reason_code="source_probe_required",
                    severity="error",
                    source=source,
                    record_type=record_type,
                    message=(
                        f"{source} {record_type} missing successful source-health "
                        f"for feeds: {', '.join(missing_feeds)}"
                    ),
                    observed_at=max(record.observed_at for record in group_records),
                )
            )
        elif any(
            health is not None and generated_at - health.observed_at > max_source_health_age
            for health in latest_health_rows
        ):
            blocked_reasons.append("stale_source_health")
            stale_feeds = [
                health.feed
                for health in latest_health_rows
                if health is not None and generated_at - health.observed_at > max_source_health_age
            ]
            issues.append(
                UniverseQualityIssue(
                    reason_code="stale_source_health",
                    severity="warning",
                    source=source,
                    record_type="source_health",
                    message=f"{source} source-health is stale for feeds: {', '.join(stale_feeds)}",
                    observed_at=max(
                        health.observed_at
                        for health in latest_health_rows
                        if health is not None and health.feed in stale_feeds
                    ),
                )
            )

        if record_type in _WATCHLIST_TYPES:
            blocked_reasons.append("watchlist_only_source")
            issues.append(
                UniverseQualityIssue(
                    reason_code="watchlist_only_source",
                    severity="warning",
                    source=source,
                    record_type=record_type,
                    message=f"{source} {record_type} is watchlist or regime input only",
                    observed_at=max(record.observed_at for record in group_records),
                )
            )

        coverage_items.append(
            UniverseSourceCoverage(
                source=source,
                record_type=record_type,
                feed=feed,
                role=_source_role(group_records[0]) or "execution_history",
                records=len(group_records),
                latest_observed_at=max(record.observed_at for record in group_records),
                endpoint_family=endpoint_metadata["endpoint_family"],
                max_limit=endpoint_metadata["max_limit"],
                start_end_pagination=endpoint_metadata["start_end_pagination"],
                latest_30_day_limited=endpoint_metadata["latest_30_day_limited"],
                source_health_present=source_health_present,
                network_routes=routes,
                blocked_reasons=_dedupe_preserving_order(blocked_reasons),
            )
        )
    return coverage_items


def _endpoint_metadata(source: str, record_type: str, feed: str) -> dict[str, object]:
    default = {
        "endpoint_family": None,
        "max_limit": None,
        "start_end_pagination": False,
        "latest_30_day_limited": record_type in _DERIVATIVES_RECENT_WINDOW_TYPES,
    }
    return {
        **default,
        **_DERIVATIVES_ENDPOINT_METADATA.get((source, record_type, feed), {}),
    }


def _append_lookahead_issues(
    records: list[SourceRecord],
    *,
    symbols: list[str],
    timeframe: str,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
    issues: list[UniverseQualityIssue],
) -> bool:
    if evaluation_start is None and evaluation_end is None:
        return False
    requested_symbols = {_exchange_symbol(symbol) for symbol in symbols}
    requested_pairs = _requested_symbol_pairs(symbols)
    had_lookahead_risk = False
    for record in records:
        if record.record_type not in _WATCHLIST_TYPES:
            continue
        if not _record_matches_universe(record, requested_symbols, requested_pairs, timeframe):
            continue
        if evaluation_start is not None:
            if record.observed_at <= _aware(evaluation_start):
                continue
        elif evaluation_end is not None:
            if record.observed_at < _aware(evaluation_end):
                continue
        else:
            continue
        had_lookahead_risk = True
        issues.append(
            UniverseQualityIssue(
                reason_code="lookahead_universe_risk",
                severity="error",
                source=record.source,
                record_type=record.record_type,
                message=f"{record.source} {record.record_type} record is outside the point-in-time window",
                observed_at=record.observed_at,
            )
        )
    return had_lookahead_risk


def _duplicate_market_timestamp_issues(
    market_by_symbol: dict[str, list[SourceRecord]]
) -> list[UniverseQualityIssue]:
    issues: list[UniverseQualityIssue] = []
    for symbol, records in market_by_symbol.items():
        counts = Counter(record.observed_at for record in records)
        duplicate_timestamps = [timestamp for timestamp, count in counts.items() if count > 1]
        for timestamp in duplicate_timestamps:
            issues.append(
                UniverseQualityIssue(
                    reason_code="duplicate_timestamps",
                    severity="error",
                    source=records[0].source if records else "unknown",
                    record_type="market_candle",
                    symbol=symbol,
                    message=f"duplicate market candle timestamp for {symbol}",
                    observed_at=timestamp,
                )
            )
    return issues


def _timestamp_alignment_issues(
    market_by_symbol: dict[str, list[SourceRecord]],
    symbols: list[str],
    timeframe: str,
) -> list[UniverseQualityIssue]:
    non_empty_timestamps = [
        {record.observed_at for record in market_by_symbol[symbol]}
        for symbol in symbols
        if market_by_symbol[symbol]
    ]
    if len(non_empty_timestamps) < 2:
        return []
    aligned = set.intersection(*non_empty_timestamps)
    max_records = max(len(timestamps) for timestamps in non_empty_timestamps)
    if len(aligned) >= max_records:
        return []
    return [
        UniverseQualityIssue(
            reason_code="timestamp_alignment_gap",
            severity="error",
            source="binance_public",
            record_type="market_candle",
            message=f"market candle timestamps do not align for timeframe {timeframe}",
        )
    ]


def _market_records_by_symbol(
    records: list[SourceRecord],
    symbols: list[str],
    timeframe: str,
    *,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> dict[str, list[SourceRecord]]:
    grouped: dict[str, dict[datetime, list[SourceRecord]]] = {
        symbol: defaultdict(list) for symbol in symbols
    }
    exchange_symbol_to_symbol = {_exchange_symbol(symbol): symbol for symbol in symbols}
    for record in records:
        if record.record_type != "market_candle":
            continue
        if not _in_window(record.observed_at, evaluation_start, evaluation_end):
            continue
        payload = record.payload
        if payload.get("timeframe") != timeframe:
            continue
        symbol = exchange_symbol_to_symbol.get(_exchange_symbol(str(payload.get("symbol", ""))))
        if symbol is None:
            continue
        grouped[symbol][_aware(record.observed_at)].append(record)
    return {
        symbol: sorted(
            _canonical_market_records_by_timestamp(by_timestamp),
            key=lambda record: record.observed_at,
        )
        for symbol, by_timestamp in grouped.items()
    }


def _canonical_market_records_by_timestamp(
    by_timestamp: dict[datetime, list[SourceRecord]],
) -> list[SourceRecord]:
    canonical_records: list[SourceRecord] = []
    for records in by_timestamp.values():
        if not records:
            continue
        source_order = sorted(
            {record.source for record in records},
            key=lambda source: (_MARKET_SOURCE_PRIORITY.get(source, 100), source),
        )
        canonical_source = source_order[0]
        canonical_records.extend(
            record for record in records if record.source == canonical_source
        )
    return canonical_records


def _coverage_records(
    records: list[SourceRecord],
    *,
    symbols: list[str],
    timeframe: str,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> list[SourceRecord]:
    requested_symbols = {_exchange_symbol(symbol) for symbol in symbols}
    requested_pairs = _requested_symbol_pairs(symbols)
    selected: list[SourceRecord] = []
    for record in records:
        if not _record_matches_universe(record, requested_symbols, requested_pairs, timeframe):
            continue
        if record.record_type in {"market_candle", *_DERIVATIVES_TYPES} and not _in_window(
            record.observed_at,
            evaluation_start,
            evaluation_end,
        ):
            continue
        selected.append(record)
    return selected


def _record_matches_universe(
    record: SourceRecord,
    requested_symbols: set[str],
    requested_pairs: set[tuple[str, str]],
    timeframe: str,
) -> bool:
    if record.record_type == "market_candle":
        if record.payload.get("timeframe") != timeframe:
            return False
        return _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
    if record.record_type == "premium_index_kline":
        if record.payload.get("interval") != timeframe:
            return False
        return _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
    if record.record_type == "basis":
        if record.payload.get("period") != timeframe:
            return False
        return _exchange_symbol(str(record.payload.get("pair", ""))) in requested_symbols
    if record.record_type in {"long_short_account_ratio", "taker_buy_sell_volume"}:
        if record.payload.get("period") != timeframe:
            return False
        return _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
    if record.record_type == "funding_rate":
        return _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
    if record.record_type == "open_interest":
        if record.payload.get("timeframe") != timeframe:
            return False
        return _exchange_symbol(str(record.payload.get("symbol", ""))) in requested_symbols
    if record.record_type == "dex_pair":
        base = str(record.payload.get("base_token", "")).upper()
        quote = str(record.payload.get("quote_token", "")).upper()
        if not base or not quote:
            return False
        return (base, quote) in requested_pairs
    if record.record_type == "defi_yield":
        token = str(record.payload.get("symbol", "")).upper().replace("/", "")
        return any(token and token in symbol for symbol in requested_symbols)
    return False


def _in_window(
    timestamp: datetime,
    evaluation_start: datetime | None,
    evaluation_end: datetime | None,
) -> bool:
    observed_at = _aware(timestamp)
    if evaluation_start is not None and observed_at < _aware(evaluation_start):
        return False
    if evaluation_end is not None and observed_at >= _aware(evaluation_end):
        return False
    return True


def _source_role(record: SourceRecord) -> UniverseSourceRole | None:
    if record.record_type == "market_candle":
        return "execution_history"
    if record.record_type in _DERIVATIVES_TYPES:
        return "recent_derivatives_context"
    if record.record_type in _WATCHLIST_TYPES:
        return "watchlist_or_regime_only"
    if record.record_type == "source_health":
        return "source_health"
    return None


def _coverage_feed(record: SourceRecord) -> str:
    payload = record.payload
    if record.record_type == "market_candle":
        return str(payload.get("timeframe") or "unknown")
    if record.record_type == "premium_index_kline":
        return "premium_index_kline"
    if record.record_type == "basis":
        return "basis"
    if record.record_type == "funding_rate":
        return "funding_rate_history"
    if record.record_type == "open_interest":
        return "open_interest_history"
    if record.record_type == "long_short_account_ratio":
        return "long_short_account_ratio"
    if record.record_type == "taker_buy_sell_volume":
        return "taker_buy_sell_volume"
    if record.record_type == "dex_pair":
        return "pairs"
    if record.record_type == "defi_yield":
        return "yield_pools"
    return record.record_type


def _required_health_feeds(
    record_type: str,
    group_records: list[SourceRecord],
) -> list[str]:
    if record_type == "market_candle":
        feeds = []
        for record in group_records:
            venue = str(record.payload.get("venue") or "")
            feeds.append("um_futures_ohlcv" if venue == "binance_usdm" else "ohlcv")
        return _dedupe_preserving_order(feeds)
    if record_type == "premium_index_kline":
        return ["premium_index_klines"]
    if record_type == "basis":
        return ["basis"]
    if record_type == "funding_rate":
        return ["funding_rate_history"]
    if record_type == "open_interest":
        return ["open_interest_history"]
    if record_type == "long_short_account_ratio":
        return ["global_long_short_account_ratio"]
    if record_type == "taker_buy_sell_volume":
        return ["taker_buy_sell_volume"]
    if record_type == "dex_pair":
        return ["pairs"]
    if record_type == "defi_yield":
        return ["yield_pools"]
    return [record_type]


class _SourceHealth(_StrictUniverseModel):
    source: str
    feed: str
    observed_at: datetime
    network_route: str
    success: bool


def _source_health_by_feed(
    records: list[SourceRecord],
    issues: list[UniverseQualityIssue],
) -> dict[tuple[str, str], list[_SourceHealth]]:
    by_feed: dict[tuple[str, str], list[_SourceHealth]] = defaultdict(list)
    for record in records:
        if record.record_type != "source_health":
            continue
        payload = record.payload
        source = str(payload.get("source") or record.source)
        feed_value = payload.get("feed")
        if feed_value is None or not str(feed_value).strip():
            _append_malformed_health_issue(record, issues, "missing source-health feed")
            try:
                observed_at = _parse_datetime(payload.get("observed_at"), record.observed_at)
            except ValueError as exc:
                _append_malformed_health_issue(record, issues, str(exc))
                observed_at = _aware(record.observed_at)
            by_feed[(source, _UNKNOWN_SOURCE_HEALTH_FEED)].append(
                _SourceHealth(
                    source=source,
                    feed=_UNKNOWN_SOURCE_HEALTH_FEED,
                    observed_at=observed_at,
                    network_route=str(payload.get("network_route") or "unknown"),
                    success=False,
                )
            )
            continue
        feed = str(feed_value)
        malformed = False
        try:
            observed_at = _parse_datetime(payload.get("observed_at"), record.observed_at)
        except ValueError as exc:
            _append_malformed_health_issue(record, issues, str(exc))
            observed_at = _aware(record.observed_at)
            malformed = True
        success = payload.get("success")
        if not isinstance(success, bool):
            _append_malformed_health_issue(record, issues, "source-health success must be boolean")
            success = False
            malformed = True
        network_route = str(payload.get("network_route") or "unknown")
        by_feed[(source, feed)].append(
            _SourceHealth(
                source=source,
                feed=feed,
                observed_at=observed_at,
                network_route=network_route,
                success=success and not malformed,
            )
        )
    return {
        key: sorted(health_rows, key=lambda item: item.observed_at)
        for key, health_rows in by_feed.items()
    }


def _append_malformed_health_issue(
    record: SourceRecord,
    issues: list[UniverseQualityIssue],
    message: str,
) -> None:
    issues.append(
        UniverseQualityIssue(
            reason_code="source_probe_required",
            severity="error",
            source=record.source,
            record_type="source_health",
            message=f"malformed source-health payload: {message}",
            observed_at=record.observed_at,
        )
    )


def _latest_health(health_rows: list[_SourceHealth]) -> _SourceHealth | None:
    if not health_rows:
        return None
    return max(health_rows, key=lambda health: health.observed_at)


def _parse_datetime(value: object, fallback: datetime) -> datetime:
    if isinstance(value, str):
        return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    if isinstance(value, datetime):
        return _aware(value)
    return _aware(fallback)


def _normalize_requested_months(
    requested_months: list[tuple[int, int]] | None,
) -> tuple[tuple[int, int], ...]:
    if not requested_months:
        return ()
    normalized: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for year, month in requested_months:
        if month < 1 or month > 12:
            raise ValueError(f"invalid requested month: {year}-{month}")
        key = (int(year), int(month))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return tuple(sorted(normalized))


def _format_month(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _exchange_symbol(symbol: str) -> str:
    return symbol.strip().upper().split(":", maxsplit=1)[0].replace("/", "")


def _requested_symbol_pairs(symbols: list[str]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for symbol in symbols:
        base_quote = symbol.strip().upper().split(":", maxsplit=1)[0]
        if "/" not in base_quote:
            continue
        base, quote = base_quote.split("/", maxsplit=1)
        if base and quote:
            pairs.add((base, quote))
    return pairs


def _latest_observed_at(records: list[SourceRecord]) -> datetime:
    if not records:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return max(_aware(record.observed_at) for record in records)


def _load_records_read_only(db_path: str | Path) -> list[SourceRecord]:
    path = Path(db_path)
    if not path.exists():
        return []
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(
                """
                SELECT record_id, source, record_type, observed_at, payload_json
                FROM source_records
                ORDER BY observed_at, record_id
                """
            ).fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"cannot read evidence records from {path}: {exc}") from exc
    return [
        SourceRecord(
            record_id=record_id,
            source=source,
            record_type=record_type,
            observed_at=datetime.fromisoformat(observed_at),
            payload=json.loads(payload_json),
        )
        for record_id, source, record_type, observed_at, payload_json in rows
    ]


def _dedupe_preserving_order(values) -> list:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
