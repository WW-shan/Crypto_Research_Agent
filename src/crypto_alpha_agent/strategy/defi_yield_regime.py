from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math

from pydantic import ValidationError

from crypto_alpha_agent.data.models import DefiYieldSnapshot, SourceRecord
from crypto_alpha_agent.strategy.models import StrategyValidationReport

STRATEGY_FAMILY = "defi_yield_regime_watchlist"
VALIDATOR_NAME = "defi_yield_regime"
DEFAULT_SUPPORTED_CHAINS = ("Ethereum", "Base", "Arbitrum", "Optimism", "Polygon")
DEFAULT_MIN_TVL_USD = 100_000.0
DEFAULT_MIN_APY_CHANGE = 1.0
DEFAULT_MIN_OBSERVATIONS = 2
DEFAULT_MAX_AGE_HOURS = 72.0


def validate_defi_yield_regime(
    records: Sequence[object],
    *,
    min_tvl_usd: float = DEFAULT_MIN_TVL_USD,
    min_apy_change: float = DEFAULT_MIN_APY_CHANGE,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
    supported_chains: Sequence[str] = DEFAULT_SUPPORTED_CHAINS,
    now: datetime | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> StrategyValidationReport:
    _validate_thresholds(
        min_tvl_usd=min_tvl_usd,
        min_apy_change=min_apy_change,
        min_observations=min_observations,
        max_age_hours=max_age_hours,
    )
    snapshots = _parse_defi_yield_snapshots(records)
    if not snapshots:
        return _blocked_report(
            blocked_reasons=["missing_defi_yield_records"],
            metrics=_base_metrics(
                min_tvl_usd=min_tvl_usd,
                min_apy_change=min_apy_change,
                min_observations=min_observations,
                supported_chains=supported_chains,
                candidate_count=0,
                candidates=[],
            ),
        )

    grouped: dict[tuple[str, str, str, str], list[DefiYieldSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        pool_id = _pool_identity(snapshot)
        grouped[(snapshot.chain, snapshot.project, snapshot.symbol, pool_id)].append(
            snapshot
        )

    candidates: list[dict[str, object]] = []
    blocked_reasons: list[str] = []
    rejected_group_reasons: list[dict[str, object]] = []
    supported_chain_set = {chain for chain in _normalize_string_tuple(supported_chains)}
    reference_now = _coerce_datetime(now) if now is not None else datetime.now(tz=UTC)
    stale_threshold = reference_now - timedelta(hours=max_age_hours)

    for group_key in sorted(grouped):
        series = sorted(grouped[group_key], key=lambda snapshot: snapshot.observed_at)
        latest = series[-1]
        pool_id = group_key[3]

        if len(series) < min_observations:
            blocked_reasons.append("insufficient_history")
            rejected_group_reasons.append(
                _rejected_group_reason(
                    group_key=group_key,
                    blocked_reasons=["insufficient_history"],
                )
            )
            continue

        group_blocked_reasons: list[str] = []
        if latest.tvl_usd < min_tvl_usd:
            group_blocked_reasons.append("insufficient_tvl")
        if latest.chain not in supported_chain_set:
            group_blocked_reasons.append("unsupported_chain")
        if latest.observed_at < stale_threshold:
            group_blocked_reasons.append("stale_source")

        prior = series[-2]
        apy_change = latest.apy - prior.apy
        if abs(apy_change) < min_apy_change:
            group_blocked_reasons.append("no_apy_regime_change")

        if group_blocked_reasons:
            blocked_reasons.extend(group_blocked_reasons)
            rejected_group_reasons.append(
                _rejected_group_reason(
                    group_key=group_key,
                    blocked_reasons=group_blocked_reasons,
                )
            )
            continue

        candidates.append(
            {
                "chain": latest.chain,
                "project": latest.project,
                "symbol": latest.symbol,
                "pool_id": pool_id,
                "latest_observed_at": _format_datetime(latest.observed_at),
                "prior_observed_at": _format_datetime(prior.observed_at),
                "latest_apy": latest.apy,
                "prior_apy": prior.apy,
                "apy_change": apy_change,
                "tvl_usd": latest.tvl_usd,
                "direction": "apy_up" if apy_change > 0 else "apy_down",
            }
        )

    unique_blocked_reasons = _dedupe_blocked_reasons(blocked_reasons)
    if candidates:
        return StrategyValidationReport(
            strategy_family=STRATEGY_FAMILY,
            validator_name=VALIDATOR_NAME,
            approved=True,
            blocked_reasons=[],
            metrics=_base_metrics(
                min_tvl_usd=min_tvl_usd,
                min_apy_change=min_apy_change,
                min_observations=min_observations,
                supported_chains=supported_chains,
                candidate_count=len(candidates),
                candidates=candidates,
                blocked_reasons_observed=unique_blocked_reasons,
                rejected_group_reasons=rejected_group_reasons,
            ),
        )

    return _blocked_report(
        blocked_reasons=unique_blocked_reasons or ["no_apy_regime_change"],
        metrics=_base_metrics(
            min_tvl_usd=min_tvl_usd,
            min_apy_change=min_apy_change,
            min_observations=min_observations,
            supported_chains=supported_chains,
            candidate_count=0,
            candidates=[],
            blocked_reasons_observed=unique_blocked_reasons or ["no_apy_regime_change"],
            rejected_group_reasons=rejected_group_reasons,
        ),
    )


def _parse_defi_yield_snapshots(
    records: Sequence[object],
) -> list[DefiYieldSnapshot]:
    snapshots: list[DefiYieldSnapshot] = []
    for record in records:
        snapshot = _parse_defi_yield_snapshot(record)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


def _parse_defi_yield_snapshot(record: object) -> DefiYieldSnapshot | None:
    if not isinstance(record, Mapping):
        return None

    raw_record = dict(record)
    if raw_record.get("record_type") == "defi_yield" and "payload" in raw_record:
        try:
            source_record = SourceRecord.model_validate_json(json.dumps(raw_record))
            if source_record.record_type != "defi_yield":
                return None
            if not isinstance(source_record.payload, Mapping):
                return None
            return DefiYieldSnapshot.model_validate_json(
                json.dumps(source_record.payload)
            )
        except (ValidationError, TypeError, ValueError):
            return None

    try:
        return DefiYieldSnapshot.model_validate_json(json.dumps(raw_record))
    except (ValidationError, TypeError, ValueError):
        return None


def _base_metrics(
    *,
    min_tvl_usd: float,
    min_apy_change: float,
    min_observations: int,
    supported_chains: Sequence[str],
    candidate_count: int,
    candidates: list[dict[str, object]],
    blocked_reasons_observed: list[str] | None = None,
    rejected_group_reasons: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "execution_role": "research_only",
        "paper_watchlist_only": True,
        "candidate_count": candidate_count,
        "candidates": candidates,
        "blocked_reasons_observed": blocked_reasons_observed or [],
        "rejected_group_reasons": rejected_group_reasons or [],
        "min_tvl_usd": float(min_tvl_usd),
        "min_apy_change": float(min_apy_change),
        "min_observations": int(min_observations),
        "supported_chains": list(_normalize_string_tuple(supported_chains)),
    }


def _validate_thresholds(
    *,
    min_tvl_usd: float,
    min_apy_change: float,
    min_observations: int,
    max_age_hours: float,
) -> None:
    if isinstance(min_tvl_usd, bool):
        raise ValueError("min_tvl_usd must be a non-negative finite number")
    if isinstance(min_apy_change, bool):
        raise ValueError("min_apy_change must be a non-negative finite number")
    if isinstance(min_observations, bool):
        raise ValueError("min_observations must be an integer at least 2")
    if isinstance(max_age_hours, bool):
        raise ValueError("max_age_hours must be a positive finite number")
    if not math.isfinite(min_tvl_usd) or min_tvl_usd < 0:
        raise ValueError("min_tvl_usd must be a non-negative finite number")
    if not math.isfinite(min_apy_change) or min_apy_change < 0:
        raise ValueError("min_apy_change must be a non-negative finite number")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer at least 2")
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be a positive finite number")


def _blocked_report(
    *,
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


def _dedupe_blocked_reasons(reasons: Sequence[str]) -> list[str]:
    ordered = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        ordered.append(reason)
        seen.add(reason)
    return ordered


def _rejected_group_reason(
    *,
    group_key: tuple[str, str, str, str],
    blocked_reasons: list[str],
) -> dict[str, object]:
    chain, project, symbol, pool_id = group_key
    return {
        "chain": chain,
        "project": project,
        "symbol": symbol,
        "pool_id": pool_id,
        "blocked_reasons": _dedupe_blocked_reasons(blocked_reasons),
    }


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("now must be a datetime or ISO datetime string")
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _pool_identity(snapshot: DefiYieldSnapshot) -> str:
    raw_pool = snapshot.raw.get("pool")
    if _has_identity_value(raw_pool):
        return f"pool-{_research_safe_component(str(raw_pool))}"

    stable_identity = {
        key: snapshot.raw[key]
        for key in ("poolMeta", "stablecoin", "underlyingTokens", "url")
        if key in snapshot.raw and _has_identity_value(snapshot.raw[key])
    }
    identity_payload = stable_identity or snapshot.raw
    digest = hashlib.sha256(
        json.dumps(
            identity_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"pool-hash-{digest}"


def _research_safe_component(value: str) -> str:
    return value.strip().lower().replace("/", "-").replace(":", "-").replace(" ", "-")


def _has_identity_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | dict | tuple | set):
        return bool(value)
    return True


def _format_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalize_string_tuple(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError("supported_chains must contain strings")
        stripped = value.strip()
        if not stripped:
            raise ValueError("supported_chains must contain non-empty strings")
        if stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return tuple(normalized)
