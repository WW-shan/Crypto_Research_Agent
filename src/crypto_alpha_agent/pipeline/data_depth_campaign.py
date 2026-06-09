from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore


CampaignMarket = Literal["um-futures"]
CampaignReadiness = Literal["ready", "blocked"]
CampaignReasonCode = Literal["insufficient_month_coverage"]


class _StrictCampaignModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class CampaignMonth(_StrictCampaignModel):
    year: int = Field(ge=2000)
    month: int = Field(ge=1, le=12)


class DataDepthCampaignSpec(_StrictCampaignModel):
    symbols: tuple[str, ...]
    timeframe: str
    market: CampaignMarket
    start: CampaignMonth
    end: CampaignMonth
    min_unique_months: int = Field(ge=1)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False

    @field_validator("symbols", mode="before")
    @classmethod
    def _normalize_symbols(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list | tuple):
            raise ValueError("symbols must be a non-empty list or tuple")
        symbols = _dedupe_preserving_order(_normalize_symbol(str(symbol)) for symbol in value)
        if not symbols:
            raise ValueError("symbols must be non-empty")
        return tuple(symbols)

    @model_validator(mode="after")
    def _validate_month_range(self) -> DataDepthCampaignSpec:
        if _month_index(self.end) < _month_index(self.start):
            raise ValueError("campaign end month is before campaign start month")
        return self


class DataDepthCoverageRow(_StrictCampaignModel):
    symbol: str
    timeframe: str
    market: CampaignMarket
    requested_months: int = Field(ge=0)
    unique_months: int = Field(ge=0)
    missing_months: tuple[CampaignMonth, ...] = Field(default_factory=tuple)
    readiness: CampaignReadiness
    reason_codes: tuple[CampaignReasonCode, ...] = Field(default_factory=tuple)


class DataDepthCollectionJob(_StrictCampaignModel):
    symbol: str
    timeframe: str
    market: CampaignMarket
    month: CampaignMonth
    status: Literal["planned", "succeeded", "failed"] = "planned"
    error: str | None = None
    records_written: int = Field(default=0, ge=0)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class DataDepthCampaignReport(_StrictCampaignModel):
    generated_at: datetime
    spec: DataDepthCampaignSpec
    readiness: CampaignReadiness
    coverage: tuple[DataDepthCoverageRow, ...] = Field(default_factory=tuple)
    missing_collection_jobs: tuple[DataDepthCollectionJob, ...] = Field(default_factory=tuple)
    reason_codes: tuple[CampaignReasonCode, ...] = Field(default_factory=tuple)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def expand_campaign_months(
    start: CampaignMonth,
    end: CampaignMonth,
) -> tuple[CampaignMonth, ...]:
    if _month_index(end) < _month_index(start):
        raise ValueError("campaign end month is before campaign start month")

    months = []
    current_year = start.year
    current_month = start.month
    while (current_year * 12 + current_month) <= _month_index(end):
        months.append(CampaignMonth(year=current_year, month=current_month))
        current_month += 1
        if current_month > 12:
            current_year += 1
            current_month = 1
    return tuple(months)


def build_data_depth_campaign_report(
    db_path: str | Path,
    *,
    spec: DataDepthCampaignSpec,
    now: datetime | None = None,
) -> DataDepthCampaignReport:
    records = ResearchDataStore(db_path).load_records(record_type="market_candle")
    requested_months = expand_campaign_months(spec.start, spec.end)
    coverage_rows: list[DataDepthCoverageRow] = []
    missing_jobs: list[DataDepthCollectionJob] = []

    for symbol in spec.symbols:
        available_months = _available_market_months(
            records,
            symbol=symbol,
            timeframe=spec.timeframe,
            market=spec.market,
            requested_months=requested_months,
        )
        missing_months = tuple(
            month
            for month in requested_months
            if (month.year, month.month) not in available_months
        )
        readiness: CampaignReadiness = (
            "ready" if len(available_months) >= spec.min_unique_months else "blocked"
        )
        reason_codes: tuple[CampaignReasonCode, ...] = (
            () if readiness == "ready" else ("insufficient_month_coverage",)
        )
        coverage_rows.append(
            DataDepthCoverageRow(
                symbol=symbol,
                timeframe=spec.timeframe,
                market=spec.market,
                requested_months=len(requested_months),
                unique_months=len(available_months),
                missing_months=missing_months,
                readiness=readiness,
                reason_codes=reason_codes,
            )
        )
        missing_jobs.extend(
            DataDepthCollectionJob(
                symbol=symbol,
                timeframe=spec.timeframe,
                market=spec.market,
                month=month,
            )
            for month in missing_months
        )

    report_reason_codes = _dedupe_reason_codes(
        reason
        for coverage in coverage_rows
        for reason in coverage.reason_codes
    )
    return DataDepthCampaignReport(
        generated_at=_aware(now) if now is not None else datetime.now(tz=UTC),
        spec=spec,
        readiness="blocked" if report_reason_codes else "ready",
        coverage=tuple(coverage_rows),
        missing_collection_jobs=tuple(missing_jobs),
        reason_codes=report_reason_codes,
        uses_real_capital=False,
        live_order_routing=False,
    )


def render_data_depth_campaign_markdown(report: DataDepthCampaignReport) -> str:
    lines = [
        "# Data Depth Campaign",
        "",
        "## Safety",
        f"Real capital: {str(report.uses_real_capital).lower()}",
        f"Live order routing: {str(report.live_order_routing).lower()}",
        "",
        "## Decision",
        f"Readiness: {report.readiness}",
        f"Reason codes: {', '.join(report.reason_codes) or 'none'}",
        "",
        "## Coverage",
        "| Symbol | Market | Timeframe | Requested months | Unique months | Missing months | Readiness | Reasons |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in report.coverage:
        missing = ", ".join(_format_month(month) for month in row.missing_months) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    row.symbol,
                    row.market,
                    row.timeframe,
                    str(row.requested_months),
                    str(row.unique_months),
                    missing,
                    row.readiness,
                    ", ".join(row.reason_codes) or "none",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Missing Collection Jobs",
            "| Symbol | Market | Timeframe | Month | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if report.missing_collection_jobs:
        for job in report.missing_collection_jobs:
            lines.append(
                "| "
                + " | ".join(
                    [
                        job.symbol,
                        job.market,
                        job.timeframe,
                        _format_month(job.month),
                        job.status,
                    ]
                )
                + " |"
            )
    else:
        lines.append("| none | none | none | none | none |")

    lines.extend(["", "Live execution remains blocked.", ""])
    return "\n".join(lines)


def empty_campaign_report(spec: DataDepthCampaignSpec) -> DataDepthCampaignReport:
    return DataDepthCampaignReport(
        generated_at=datetime.now(tz=UTC),
        spec=spec,
        readiness="ready",
        coverage=(),
        missing_collection_jobs=(),
        reason_codes=(),
        uses_real_capital=False,
        live_order_routing=False,
    )


def _month_index(month: CampaignMonth) -> int:
    return month.year * 12 + month.month


def _available_market_months(
    records: list[SourceRecord],
    *,
    symbol: str,
    timeframe: str,
    market: CampaignMarket,
    requested_months: tuple[CampaignMonth, ...],
) -> set[tuple[int, int]]:
    requested = {(month.year, month.month) for month in requested_months}
    venue = _venue_for_market(market)
    months: set[tuple[int, int]] = set()
    for record in records:
        payload = record.payload
        if _normalize_symbol(str(payload.get("symbol", ""))) != symbol:
            continue
        if str(payload.get("timeframe", "")) != timeframe:
            continue
        if str(payload.get("venue", "")) != venue:
            continue
        observed_at = _aware(record.observed_at)
        month_key = (observed_at.year, observed_at.month)
        if month_key in requested:
            months.add(month_key)
    return months


def _venue_for_market(market: CampaignMarket) -> str:
    if market == "um-futures":
        return "binance_usdm"
    raise ValueError(f"unsupported campaign market: {market}")


def _format_month(month: CampaignMonth) -> str:
    return f"{month.year}-{month.month:02d}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _dedupe_reason_codes(values: object) -> tuple[CampaignReasonCode, ...]:
    seen: set[CampaignReasonCode] = set()
    deduped: list[CampaignReasonCode] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _normalize_symbol(symbol: str) -> str:
    upper_symbol = symbol.strip().upper()
    if "/" in upper_symbol:
        base, quote = upper_symbol.split("/", 1)
        return f"{base}/{quote}"
    for quote in ("FDUSD", "USDT", "USDC", "BUSD", "TUSD", "USD", "BTC", "ETH"):
        if upper_symbol.endswith(quote) and len(upper_symbol) > len(quote):
            return f"{upper_symbol[: -len(quote)]}/{quote}"
    return upper_symbol


def _dedupe_preserving_order(values: object) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)
