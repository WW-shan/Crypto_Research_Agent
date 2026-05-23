from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import RecordType, SourceRecord

DataQualityReasonCode = Literal[
    "missing_ohlcv_bars",
    "missing_open_interest_bars",
    "duplicate_semantic_record",
    "stale_source",
    "non_positive_price",
    "non_positive_open_interest",
    "zero_volume",
    "source_error",
    "timestamp_skew",
]


class DataQualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reason_code: DataQualityReasonCode
    severity: Literal["warning", "error"]
    source: str
    record_type: RecordType
    semantic_key: str
    message: str
    observed_at: datetime | None = None


class SourceHealthSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    feed: str
    success: bool
    attempts: int = Field(ge=0)
    failure: str | None = None
    observed_at: datetime
    records_fetched: int = Field(ge=0)
    records_written: int = Field(ge=0)
    network_route: str = "unknown"
    provider_status: str = "unknown"
    http_status: int | None = None
    parse_status: str | None = None
    typed_record_count: int | None = Field(default=None, ge=0)


class DataQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    generated_at: datetime
    checked_records: int = Field(ge=0)
    issues: list[DataQualityIssue] = Field(default_factory=list)
    source_health: list[SourceHealthSnapshot] = Field(default_factory=list)


def build_data_quality_report(
    records: list[SourceRecord], now: datetime | None = None
) -> DataQualityReport:
    generated_at = _aware(now or datetime.now(tz=UTC))
    issues: list[DataQualityIssue] = []
    source_health: list[SourceHealthSnapshot] = []

    semantic_records: dict[str, list[SourceRecord]] = defaultdict(list)
    ohlcv_groups: dict[str, list[SourceRecord]] = defaultdict(list)
    open_interest_groups: dict[str, list[SourceRecord]] = defaultdict(list)

    for record in records:
        semantic_records[_duplicate_semantic_key(record)].append(record)
        if record.record_type == "market_candle":
            issues.extend(_market_value_issues(record))
            ohlcv_groups[_ohlcv_series_key(record)].append(record)
        elif record.record_type == "open_interest":
            issues.extend(_open_interest_value_issues(record))
            open_interest_groups[_open_interest_series_key(record)].append(record)
        elif record.record_type == "source_health":
            try:
                snapshot = _source_health_snapshot(record)
            except ValueError as exc:
                issues.append(
                    DataQualityIssue(
                        reason_code="source_error",
                        severity="error",
                        source=record.source,
                        record_type="source_health",
                        semantic_key=f"{record.source}:{record.payload.get('feed', '')}",
                        message=str(exc) or "malformed source health payload",
                        observed_at=record.observed_at,
                    )
                )
                continue
            source_health.append(snapshot)
            if not snapshot.success:
                issues.append(
                    DataQualityIssue(
                        reason_code="source_error",
                        severity="error",
                        source=snapshot.source,
                        record_type="source_health",
                        semantic_key=f"{snapshot.source}:{snapshot.feed}",
                        message=snapshot.failure or "source ingestion failed",
                        observed_at=snapshot.observed_at,
                    )
                )

    for semantic_key, duplicates in sorted(semantic_records.items()):
        if len(duplicates) > 1:
            first = duplicates[0]
            issues.append(
                DataQualityIssue(
                    reason_code="duplicate_semantic_record",
                    severity="warning",
                    source=first.source,
                    record_type=first.record_type,
                    semantic_key=semantic_key,
                    message=f"{len(duplicates)} records share the same semantic key",
                    observed_at=max(record.observed_at for record in duplicates),
                )
            )

    issues.extend(
        _series_continuity_issues(
            ohlcv_groups,
            generated_at=generated_at,
            missing_reason_code="missing_ohlcv_bars",
            missing_message_template="missing {missing_bars} expected OHLCV bars",
        )
    )
    issues.extend(
        _series_continuity_issues(
            open_interest_groups,
            generated_at=generated_at,
            missing_reason_code="missing_open_interest_bars",
            missing_message_template="missing {missing_bars} expected open-interest bars",
        )
    )
    for group in open_interest_groups.values():
        for record in group:
            issue = _timestamp_skew_issue(record)
            if issue is not None:
                issues.append(issue)

    return DataQualityReport(
        generated_at=generated_at,
        checked_records=len(records),
        issues=sorted(issues, key=lambda issue: (issue.reason_code, issue.semantic_key, issue.message)),
        source_health=sorted(
            source_health,
            key=lambda snapshot: (snapshot.observed_at, snapshot.source, snapshot.feed),
        ),
    )


def _series_continuity_issues(
    groups: dict[str, list[SourceRecord]],
    *,
    generated_at: datetime,
    missing_reason_code: Literal["missing_ohlcv_bars", "missing_open_interest_bars"],
    missing_message_template: str,
) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    for semantic_key, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda record: record.observed_at)
        expected_interval = _timeframe_delta(
            str(ordered[0].payload.get("timeframe", ""))
        )
        if expected_interval is None:
            continue

        for previous, current in zip(ordered, ordered[1:], strict=False):
            missing_bars = int((current.observed_at - previous.observed_at) / expected_interval) - 1
            if missing_bars > 0:
                issues.append(
                    DataQualityIssue(
                        reason_code=missing_reason_code,
                        severity="warning",
                        source=current.source,
                        record_type=current.record_type,
                        semantic_key=semantic_key,
                        message=missing_message_template.format(
                            missing_bars=missing_bars
                        ),
                        observed_at=current.observed_at,
                    )
                )

        latest = ordered[-1]
        if generated_at - latest.observed_at > expected_interval * 2:
            issues.append(
                DataQualityIssue(
                    reason_code="stale_source",
                    severity="warning",
                    source=latest.source,
                    record_type=latest.record_type,
                    semantic_key=semantic_key,
                    message="latest record is stale relative to report time",
                    observed_at=latest.observed_at,
                )
            )

    return issues


def _market_value_issues(record: SourceRecord) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    for field_name in ("open", "high", "low", "close"):
        value = _float_or_none(record.payload.get(field_name))
        if value is not None and value <= 0:
            issues.append(
                DataQualityIssue(
                    reason_code="non_positive_price",
                    severity="error",
                    source=record.source,
                    record_type=record.record_type,
                    semantic_key=_duplicate_semantic_key(record),
                    message=f"{field_name} price is non-positive",
                    observed_at=record.observed_at,
                )
            )

    volume = _float_or_none(record.payload.get("volume"))
    if volume is not None and volume <= 0:
        issues.append(
            DataQualityIssue(
                reason_code="zero_volume",
                severity="warning",
                source=record.source,
                record_type=record.record_type,
                semantic_key=_duplicate_semantic_key(record),
                message="volume is zero or negative",
                observed_at=record.observed_at,
            )
        )
    return issues


def _source_health_snapshot(record: SourceRecord) -> SourceHealthSnapshot:
    payload = record.payload
    feed = payload.get("feed")
    success = _strict_bool(payload.get("success"))
    attempts = _non_negative_int(payload.get("attempts"))
    records_fetched = _non_negative_int(payload.get("records_fetched"))
    records_written = _non_negative_int(payload.get("records_written"))
    typed_record_count = _optional_non_negative_int(payload.get("typed_record_count"))
    if (
        feed is None
        or success is None
        or attempts is None
        or records_fetched is None
        or records_written is None
    ):
        raise ValueError("malformed source_health payload")
    return SourceHealthSnapshot(
        source=str(payload.get("source", record.source)),
        feed=str(feed),
        success=success,
        attempts=attempts,
        failure=None if payload.get("failure") is None else str(payload["failure"]),
        observed_at=_parse_datetime(payload.get("observed_at", record.observed_at)),
        records_fetched=records_fetched,
        records_written=records_written,
        network_route=str(payload.get("network_route", "unknown")),
        provider_status=str(payload.get("provider_status", "unknown")),
        http_status=_optional_non_negative_int(payload.get("http_status")),
        parse_status=None if payload.get("parse_status") is None else str(payload.get("parse_status")),
        typed_record_count=typed_record_count,
    )


def _duplicate_semantic_key(record: SourceRecord) -> str:
    payload = record.payload
    if record.record_type == "market_candle":
        return ":".join(
            [
                record.source,
                str(payload.get("venue", "")),
                str(payload.get("symbol", "")),
                str(payload.get("timeframe", "")),
                _payload_timestamp(payload, record),
            ]
        )
    if record.record_type == "funding_rate":
        return ":".join(
            [
                record.source,
                str(payload.get("venue", "")),
                str(payload.get("symbol", "")),
                _payload_timestamp(payload, record),
            ]
        )
    if record.record_type == "dex_pair":
        return ":".join(
            [
                record.source,
                str(payload.get("chain", "")),
                str(payload.get("dex", "")),
                str(payload.get("pair_address", "")),
                _payload_timestamp(payload, record, field="observed_at"),
            ]
        )
    if record.record_type == "defi_yield":
        return ":".join(
            [
                record.source,
                str(payload.get("chain", "")),
                str(payload.get("project", "")),
                str(payload.get("symbol", "")),
                _payload_timestamp(payload, record, field="observed_at"),
            ]
        )
    if record.record_type == "source_health":
        return ":".join(
            [
                record.source,
                str(payload.get("feed", "")),
                _payload_timestamp(payload, record, field="observed_at"),
            ]
        )
    if record.record_type == "open_interest":
        return ":".join(
            [
                record.source,
                str(payload.get("venue", "")),
                str(payload.get("symbol", "")),
                str(payload.get("timeframe", "")),
                _payload_timestamp(payload, record),
            ]
        )
    return f"{record.source}:{record.record_type}:{record.observed_at.isoformat()}"


def _ohlcv_series_key(record: SourceRecord) -> str:
    payload = record.payload
    return ":".join(
        [
            record.source,
            str(payload.get("venue", "")),
            str(payload.get("symbol", "")),
            str(payload.get("timeframe", "")),
        ]
    )


def _open_interest_value_issues(record: SourceRecord) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    open_interest = _float_or_none(record.payload.get("open_interest"))
    if open_interest is not None and open_interest <= 0:
        issues.append(
            DataQualityIssue(
                reason_code="non_positive_open_interest",
                severity="error",
                source=record.source,
                record_type=record.record_type,
                semantic_key=_duplicate_semantic_key(record),
                message="open interest is non-positive",
                observed_at=record.observed_at,
            )
        )
    value = _float_or_none(record.payload.get("open_interest_value"))
    if value is not None and value < 0:
        issues.append(
            DataQualityIssue(
                reason_code="non_positive_open_interest",
                severity="error",
                source=record.source,
                record_type=record.record_type,
                semantic_key=_duplicate_semantic_key(record),
                message="open interest value is negative",
                observed_at=record.observed_at,
            )
        )
    return issues


def _open_interest_series_key(record: SourceRecord) -> str:
    payload = record.payload
    return ":".join(
        [
            record.source,
            str(payload.get("venue", "")),
            str(payload.get("symbol", "")),
            str(payload.get("timeframe", "")),
        ]
    )


def _timestamp_skew_issue(record: SourceRecord) -> DataQualityIssue | None:
    try:
        payload_timestamp = _parse_datetime(
            record.payload.get("timestamp", record.observed_at)
        )
    except ValueError as exc:
        return DataQualityIssue(
            reason_code="source_error",
            severity="error",
            source=record.source,
            record_type=record.record_type,
            semantic_key=_duplicate_semantic_key(record),
            message=str(exc) or "malformed open-interest timestamp",
            observed_at=record.observed_at,
        )
    observed_at = _aware(record.observed_at)
    timeframe = str(record.payload.get("timeframe", ""))
    delta = _timeframe_delta(timeframe)
    if delta is None:
        return None
    if abs((observed_at - payload_timestamp).total_seconds()) > delta.total_seconds():
        return DataQualityIssue(
            reason_code="timestamp_skew",
            severity="warning",
            source=record.source,
            record_type=record.record_type,
            semantic_key=_duplicate_semantic_key(record),
            message="payload timestamp is skewed from observed_at",
            observed_at=record.observed_at,
        )
    return None


def _payload_timestamp(
    payload: dict[str, Any], record: SourceRecord, *, field: str = "timestamp"
) -> str:
    value = payload.get(field)
    if value is None:
        return record.observed_at.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _timeframe_delta(timeframe: str) -> timedelta | None:
    if len(timeframe) < 2:
        return None
    unit = timeframe[-1]
    try:
        amount = int(timeframe[:-1])
    except ValueError:
        return None
    if amount <= 0:
        return None
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _strict_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _optional_non_negative_int(value: object) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value)


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return _aware(value)
    return _aware(datetime.fromisoformat(str(value)))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
