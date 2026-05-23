from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from statistics import fmean, pstdev

from pydantic import ValidationError

from crypto_alpha_agent.data.models import MarketCandle, SourceRecord
from crypto_alpha_agent.strategy.models import StrategyValidationReport

STRATEGY_FAMILY = "volatility_compression_expansion_watchlist"
VALIDATOR_NAME = "volatility_regime_watchlist"
DEFAULT_SUPPORTED_SYMBOLS = ("BTC/USDT", "ETH/USDT", "SOL/USDT")
DEFAULT_COMPRESSION_WINDOW = 12
DEFAULT_EXPANSION_WINDOW = 3
DEFAULT_MIN_OBSERVATIONS = 16
DEFAULT_MAX_COMPRESSION_VOLATILITY = 0.01
DEFAULT_MIN_EXPANSION_RETURN_ABS = 0.015
DEFAULT_MIN_VOLUME_CHANGE_PCT = 0.25


def validate_volatility_regime_watchlist(
    records: Sequence[object],
    *,
    compression_window: int = DEFAULT_COMPRESSION_WINDOW,
    expansion_window: int = DEFAULT_EXPANSION_WINDOW,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
    max_compression_volatility: float = DEFAULT_MAX_COMPRESSION_VOLATILITY,
    min_expansion_return_abs: float = DEFAULT_MIN_EXPANSION_RETURN_ABS,
    min_volume_change_pct: float = DEFAULT_MIN_VOLUME_CHANGE_PCT,
    supported_symbols: Sequence[str] = DEFAULT_SUPPORTED_SYMBOLS,
    now: datetime | None = None,
    max_age_hours: float | None = None,
) -> StrategyValidationReport:
    _validate_thresholds(
        compression_window=compression_window,
        expansion_window=expansion_window,
        min_observations=min_observations,
        max_compression_volatility=max_compression_volatility,
        min_expansion_return_abs=min_expansion_return_abs,
        min_volume_change_pct=min_volume_change_pct,
        max_age_hours=max_age_hours,
    )
    candles = _parse_market_candles(records)
    if not candles:
        return _blocked_report(
            ["missing_market_candle_records"],
            _base_metrics(
                candidate_count=0,
                candidates=[],
                compression_window=compression_window,
                expansion_window=expansion_window,
                min_observations=min_observations,
                max_compression_volatility=max_compression_volatility,
                min_expansion_return_abs=min_expansion_return_abs,
                min_volume_change_pct=min_volume_change_pct,
                supported_symbols=supported_symbols,
                blocked_reasons_observed=["missing_market_candle_records"],
            ),
        )

    grouped: dict[tuple[str, str], list[MarketCandle]] = defaultdict(list)
    for candle in candles:
        grouped[(candle.symbol, candle.timeframe)].append(candle)

    candidates: list[dict[str, object]] = []
    rejected_series: list[dict[str, object]] = []
    blocked_reasons: list[str] = []
    supported_symbol_set = set(_normalize_string_tuple(supported_symbols))
    required_observations = max(
        min_observations,
        compression_window + expansion_window + 1,
    )
    reference_now = _coerce_utc(now) if now is not None else datetime.now(tz=UTC)
    stale_threshold = (
        reference_now - timedelta(hours=max_age_hours)
        if max_age_hours is not None
        else None
    )

    for group_key in sorted(grouped):
        symbol, timeframe = group_key
        series = sorted(grouped[group_key], key=lambda candle: candle.timestamp)
        latest = series[-1]
        group_reasons: list[str] = []
        if symbol not in supported_symbol_set:
            group_reasons.append("unsupported_symbol")
        if _has_duplicate_timestamps(series):
            group_reasons.append("duplicate_market_candle_timestamp")
        if len(series) < required_observations:
            group_reasons.append("insufficient_history")
        if stale_threshold is not None and _coerce_utc(latest.timestamp) < stale_threshold:
            group_reasons.append("stale_source")
        if group_reasons:
            blocked_reasons.extend(group_reasons)
            rejected_series.append(
                _series_rejection(
                    symbol=symbol,
                    timeframe=timeframe,
                    latest_observed_at=latest.timestamp,
                    blocked_reasons=group_reasons,
                    observation_count=len(series),
                )
            )
            continue

        compression_slice = series[-(compression_window + expansion_window + 1) : -expansion_window]
        expansion_slice = series[-expansion_window:]
        expansion_start = series[-expansion_window - 1]
        analysis_window = series[-(compression_window + expansion_window + 1) :]
        if any(candle.close <= 0 for candle in analysis_window):
            group_reasons.append("non_positive_price")
            blocked_reasons.extend(group_reasons)
            rejected_series.append(
                _series_rejection(
                    symbol=symbol,
                    timeframe=timeframe,
                    latest_observed_at=latest.timestamp,
                    blocked_reasons=group_reasons,
                    observation_count=len(series),
                )
            )
            continue
        compression_returns = _close_returns(compression_slice)
        compression_volatility = (
            pstdev(compression_returns) if len(compression_returns) > 1 else 0.0
        )
        expansion_return = (latest.close / expansion_start.close) - 1.0
        compression_volume = fmean(candle.volume for candle in compression_slice)
        expansion_volume = fmean(candle.volume for candle in expansion_slice)
        volume_change_pct = (
            (expansion_volume / compression_volume) - 1.0
            if compression_volume > 0
            else 0.0
        )

        if compression_volatility > max_compression_volatility:
            group_reasons.append("volatility_not_compressed")
        if (
            abs(expansion_return) < min_expansion_return_abs
            and volume_change_pct < min_volume_change_pct
        ):
            group_reasons.append("no_price_or_volume_expansion")
        if group_reasons:
            blocked_reasons.extend(group_reasons)
            rejected_series.append(
                _series_rejection(
                    symbol=symbol,
                    timeframe=timeframe,
                    latest_observed_at=latest.timestamp,
                    blocked_reasons=group_reasons,
                    observation_count=len(series),
                    compression_volatility=compression_volatility,
                    expansion_return=expansion_return,
                    volume_change_pct=volume_change_pct,
                )
            )
            continue

        candidates.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "latest_observed_at": _format_datetime(latest.timestamp),
                "compression_window": compression_window,
                "expansion_window": expansion_window,
                "compression_volatility": float(compression_volatility),
                "expansion_return": float(expansion_return),
                "volume_change_pct": float(volume_change_pct),
                "direction": _direction(expansion_return),
            }
        )

    if candidates:
        return StrategyValidationReport(
            strategy_family=STRATEGY_FAMILY,
            validator_name=VALIDATOR_NAME,
            approved=True,
            blocked_reasons=[],
            metrics=_base_metrics(
                candidate_count=len(candidates),
                candidates=candidates,
                compression_window=compression_window,
                expansion_window=expansion_window,
                min_observations=min_observations,
                max_compression_volatility=max_compression_volatility,
                min_expansion_return_abs=min_expansion_return_abs,
                min_volume_change_pct=min_volume_change_pct,
                supported_symbols=supported_symbols,
                blocked_reasons_observed=_dedupe(blocked_reasons),
                rejected_series=rejected_series,
            ),
        )

    unique_reasons = _dedupe(blocked_reasons) or ["no_price_or_volume_expansion"]
    return _blocked_report(
        unique_reasons,
        _base_metrics(
            candidate_count=0,
            candidates=[],
            compression_window=compression_window,
            expansion_window=expansion_window,
            min_observations=min_observations,
            max_compression_volatility=max_compression_volatility,
            min_expansion_return_abs=min_expansion_return_abs,
            min_volume_change_pct=min_volume_change_pct,
            supported_symbols=supported_symbols,
            blocked_reasons_observed=unique_reasons,
            rejected_series=rejected_series,
        ),
    )


def _parse_market_candles(records: Sequence[object]) -> list[MarketCandle]:
    candles: list[MarketCandle] = []
    for record in records:
        candle = _parse_market_candle(record)
        if candle is not None:
            candles.append(candle)
    return candles


def _parse_market_candle(record: object) -> MarketCandle | None:
    if isinstance(record, MarketCandle):
        return record
    if isinstance(record, SourceRecord):
        return _parse_market_candle_source_record(record)
    if not isinstance(record, Mapping):
        return None

    raw_record = dict(record)
    if raw_record.get("record_type") == "market_candle" and "payload" in raw_record:
        try:
            source_record = SourceRecord.model_validate_json(json.dumps(raw_record))
        except (ValidationError, TypeError, ValueError):
            return None
        return _parse_market_candle_source_record(source_record)

    try:
        return MarketCandle.model_validate_json(json.dumps(raw_record))
    except (ValidationError, TypeError, ValueError):
        return None


def _parse_market_candle_source_record(source_record: SourceRecord) -> MarketCandle | None:
    if source_record.record_type != "market_candle":
        return None
    if not isinstance(source_record.payload, Mapping):
        return None
    try:
        return MarketCandle.model_validate_json(json.dumps(source_record.payload))
    except (ValidationError, TypeError, ValueError):
        return None


def _base_metrics(
    *,
    candidate_count: int,
    candidates: list[dict[str, object]],
    compression_window: int,
    expansion_window: int,
    min_observations: int,
    max_compression_volatility: float,
    min_expansion_return_abs: float,
    min_volume_change_pct: float,
    supported_symbols: Sequence[str],
    blocked_reasons_observed: list[str] | None = None,
    rejected_series: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "execution_role": "research_only",
        "paper_watchlist_only": True,
        "candidate_count": int(candidate_count),
        "candidates": candidates,
        "blocked_reasons_observed": blocked_reasons_observed or [],
        "rejected_series": rejected_series or [],
        "compression_window": int(compression_window),
        "expansion_window": int(expansion_window),
        "min_observations": int(min_observations),
        "max_compression_volatility": float(max_compression_volatility),
        "min_expansion_return_abs": float(min_expansion_return_abs),
        "min_volume_change_pct": float(min_volume_change_pct),
        "supported_symbols": list(_normalize_string_tuple(supported_symbols)),
    }


def _blocked_report(
    blocked_reasons: list[str],
    metrics: dict[str, object],
) -> StrategyValidationReport:
    return StrategyValidationReport(
        strategy_family=STRATEGY_FAMILY,
        validator_name=VALIDATOR_NAME,
        approved=False,
        blocked_reasons=blocked_reasons,
        metrics=metrics,
    )


def _validate_thresholds(
    *,
    compression_window: int,
    expansion_window: int,
    min_observations: int,
    max_compression_volatility: float,
    min_expansion_return_abs: float,
    min_volume_change_pct: float,
    max_age_hours: float | None,
) -> None:
    _validate_positive_int(compression_window, "compression_window")
    _validate_positive_int(expansion_window, "expansion_window")
    _validate_positive_int(min_observations, "min_observations")
    _validate_non_negative_float(
        max_compression_volatility,
        "max_compression_volatility",
    )
    _validate_non_negative_float(
        min_expansion_return_abs,
        "min_expansion_return_abs",
    )
    _validate_non_negative_float(min_volume_change_pct, "min_volume_change_pct")
    if max_age_hours is not None and (
        not math.isfinite(max_age_hours) or max_age_hours <= 0
    ):
        raise ValueError("max_age_hours must be finite and greater than 0")


def _validate_positive_int(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_non_negative_float(value: float, name: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")


def _close_returns(candles: Sequence[MarketCandle]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(candles, candles[1:]):
        if previous.close <= 0:
            continue
        returns.append((current.close / previous.close) - 1.0)
    return returns


def _has_duplicate_timestamps(candles: Sequence[MarketCandle]) -> bool:
    timestamps: set[datetime] = set()
    for candle in candles:
        timestamp = _coerce_utc(candle.timestamp)
        if timestamp in timestamps:
            return True
        timestamps.add(timestamp)
    return False


def _series_rejection(
    *,
    symbol: str,
    timeframe: str,
    latest_observed_at: datetime,
    blocked_reasons: list[str],
    observation_count: int,
    compression_volatility: float | None = None,
    expansion_return: float | None = None,
    volume_change_pct: float | None = None,
) -> dict[str, object]:
    rejection: dict[str, object] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "latest_observed_at": _format_datetime(latest_observed_at),
        "observation_count": int(observation_count),
        "blocked_reasons": _dedupe(blocked_reasons),
    }
    if compression_volatility is not None:
        rejection["compression_volatility"] = float(compression_volatility)
    if expansion_return is not None:
        rejection["expansion_return"] = float(expansion_return)
    if volume_change_pct is not None:
        rejection["volume_change_pct"] = float(volume_change_pct)
    return rejection


def _direction(expansion_return: float) -> str:
    if expansion_return > 0:
        return "expansion_up"
    if expansion_return < 0:
        return "expansion_down"
    return "volume_expansion_only"


def _normalize_string_tuple(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise ValueError("supported_symbols must be a sequence of symbols")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("supported_symbols must contain strings")
        stripped = value.strip()
        if not stripped:
            raise ValueError("supported_symbols must contain non-empty strings")
        if stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    if not normalized:
        raise ValueError("supported_symbols must not be empty")
    return tuple(normalized)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return _coerce_utc(value).isoformat().replace("+00:00", "Z")


def _dedupe(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped
