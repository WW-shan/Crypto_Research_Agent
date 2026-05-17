from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from crypto_alpha_agent.data.models import DexPairSnapshot, SourceRecord
from crypto_alpha_agent.strategy.models import StrategyValidationReport

ModelT = TypeVar("ModelT", bound=BaseModel)

STRATEGY_FAMILY = "dex_liquidity_volume_watchlist"
VALIDATOR_NAME = "dex_liquidity_watchlist"
DEFAULT_SUPPORTED_CHAINS = (
    "ethereum",
    "base",
    "arbitrum",
    "optimism",
    "polygon",
    "bsc",
)
DEFAULT_MIN_LIQUIDITY_USD = 100_000.0
DEFAULT_MIN_VOLUME_24H_USD = 10_000.0
DEFAULT_MIN_LIQUIDITY_CHANGE_PCT = 0.25
DEFAULT_MIN_VOLUME_CHANGE_PCT = 0.25
DEFAULT_MIN_OBSERVATIONS = 2
DEFAULT_MAX_AGE_HOURS = 72.0


def validate_dex_liquidity_watchlist(
    records: Sequence[object],
    *,
    min_liquidity_usd: float = DEFAULT_MIN_LIQUIDITY_USD,
    min_volume_24h_usd: float = DEFAULT_MIN_VOLUME_24H_USD,
    min_liquidity_change_pct: float = DEFAULT_MIN_LIQUIDITY_CHANGE_PCT,
    min_volume_change_pct: float = DEFAULT_MIN_VOLUME_CHANGE_PCT,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
    supported_chains: Sequence[str] = DEFAULT_SUPPORTED_CHAINS,
    now: datetime | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    require_research_only: bool = True,
) -> StrategyValidationReport:
    _validate_thresholds(
        min_liquidity_usd=min_liquidity_usd,
        min_volume_24h_usd=min_volume_24h_usd,
        min_liquidity_change_pct=min_liquidity_change_pct,
        min_volume_change_pct=min_volume_change_pct,
        min_observations=min_observations,
        max_age_hours=max_age_hours,
        require_research_only=require_research_only,
    )
    snapshots = _parse_dex_pair_snapshots(records)
    if not snapshots:
        blocked_reasons = ["missing_dex_pair_records"]
        if not require_research_only:
            blocked_reasons.append("direct_dex_execution_blocked")
        return _blocked_report(
            blocked_reasons=_dedupe_blocked_reasons(blocked_reasons),
            metrics=_base_metrics(
                min_liquidity_usd=min_liquidity_usd,
                min_volume_24h_usd=min_volume_24h_usd,
                min_liquidity_change_pct=min_liquidity_change_pct,
                min_volume_change_pct=min_volume_change_pct,
                min_observations=min_observations,
                supported_chains=supported_chains,
                max_age_hours=max_age_hours,
                candidate_count=0,
                candidates=[],
                blocked_reasons_observed=blocked_reasons,
            ),
        )

    grouped: dict[tuple[str, str, str], list[DexPairSnapshot]] = defaultdict(list)
    unstable_identity_groups: set[tuple[str, str, str]] = set()
    for snapshot in snapshots:
        group_key, unstable_identity = _pair_identity(snapshot)
        grouped[group_key].append(snapshot)
        if unstable_identity:
            unstable_identity_groups.add(group_key)

    candidates: list[dict[str, object]] = []
    blocked_reasons: list[str] = []
    rejected_group_reasons: list[dict[str, object]] = []
    supported_chain_set = {
        _normalize_component(chain) for chain in _normalize_string_tuple(supported_chains)
    }
    reference_now = _coerce_datetime(now) if now is not None else datetime.now(tz=UTC)
    stale_threshold = reference_now - timedelta(hours=max_age_hours)

    for group_key in sorted(grouped):
        series = sorted(grouped[group_key], key=lambda snapshot: snapshot.observed_at)
        latest = series[-1]
        pair_id = _format_pair_id(group_key)

        if len(series) < min_observations:
            blocked_reasons.append("insufficient_history")
            rejected_group_reasons.append(
                _rejected_group_reason(
                    latest=latest,
                    group_key=group_key,
                    blocked_reasons=["insufficient_history"],
                )
            )
            continue

        prior = series[-2]
        liquidity_change_pct = _change_pct(
            latest.liquidity_usd,
            prior.liquidity_usd,
        )
        volume_change_pct = _change_pct(
            latest.volume_24h_usd,
            prior.volume_24h_usd,
        )
        liquidity_direction = _direction(liquidity_change_pct)
        volume_direction = _direction(volume_change_pct)

        group_blocked_reasons: list[str] = []
        if latest.liquidity_usd < min_liquidity_usd:
            group_blocked_reasons.append("insufficient_liquidity")
        if latest.volume_24h_usd < min_volume_24h_usd:
            group_blocked_reasons.append("insufficient_volume")
        if _normalize_component(latest.chain) not in supported_chain_set:
            group_blocked_reasons.append("unsupported_chain")
        if _coerce_datetime(latest.observed_at) < stale_threshold:
            group_blocked_reasons.append("stale_source")
        if group_key in unstable_identity_groups:
            group_blocked_reasons.append("unstable_pair_identity")
        if not (
            _meets_change(liquidity_change_pct, min_liquidity_change_pct)
            or _meets_change(volume_change_pct, min_volume_change_pct)
        ):
            group_blocked_reasons.append("no_liquidity_or_volume_regime_change")

        if group_blocked_reasons:
            blocked_reasons.extend(group_blocked_reasons)
            rejected_group_reasons.append(
                _rejected_group_reason(
                    latest=latest,
                    group_key=group_key,
                    blocked_reasons=group_blocked_reasons,
                    prior=prior,
                    liquidity_change_pct=liquidity_change_pct,
                    volume_change_pct=volume_change_pct,
                    liquidity_direction=liquidity_direction,
                    volume_direction=volume_direction,
                )
            )
            continue

        candidates.append(
            {
                "chain": latest.chain,
                "dex": latest.dex,
                "pair_address": latest.pair_address,
                "base_token": latest.base_token,
                "quote_token": latest.quote_token,
                "pair_id": pair_id,
                "latest_observed_at": _format_datetime(latest.observed_at),
                "prior_observed_at": _format_datetime(prior.observed_at),
                "latest_liquidity_usd": latest.liquidity_usd,
                "prior_liquidity_usd": prior.liquidity_usd,
                "liquidity_change_pct": liquidity_change_pct,
                "latest_volume_24h_usd": latest.volume_24h_usd,
                "prior_volume_24h_usd": prior.volume_24h_usd,
                "volume_change_pct": volume_change_pct,
                "liquidity_direction": liquidity_direction,
                "volume_direction": volume_direction,
            }
        )

    direct_execution_blocked = _direct_execution_blocked(
        require_research_only=require_research_only,
        snapshots=snapshots,
    )
    if direct_execution_blocked:
        blocked_reasons.append("direct_dex_execution_blocked")

    unique_blocked_reasons = _dedupe_blocked_reasons(blocked_reasons)
    base_metrics = _base_metrics(
        min_liquidity_usd=min_liquidity_usd,
        min_volume_24h_usd=min_volume_24h_usd,
        min_liquidity_change_pct=min_liquidity_change_pct,
        min_volume_change_pct=min_volume_change_pct,
        min_observations=min_observations,
        supported_chains=supported_chains,
        max_age_hours=max_age_hours,
        candidate_count=len(candidates),
        candidates=candidates,
        blocked_reasons_observed=unique_blocked_reasons,
        rejected_group_reasons=rejected_group_reasons,
        observed_execution_roles=_observed_execution_roles(snapshots),
    )
    if candidates and not direct_execution_blocked:
        return StrategyValidationReport(
            strategy_family=STRATEGY_FAMILY,
            validator_name=VALIDATOR_NAME,
            approved=True,
            blocked_reasons=[],
            metrics=base_metrics,
        )

    return _blocked_report(
        blocked_reasons=unique_blocked_reasons
        or ["no_liquidity_or_volume_regime_change"],
        metrics=base_metrics,
    )


def _parse_dex_pair_snapshots(records: Sequence[object]) -> list[DexPairSnapshot]:
    snapshots: list[DexPairSnapshot] = []
    for record in records:
        snapshot = _parse_dex_pair_snapshot(record)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


def _parse_dex_pair_snapshot(record: object) -> DexPairSnapshot | None:
    if isinstance(record, DexPairSnapshot):
        return record

    if isinstance(record, SourceRecord):
        return _parse_dex_pair_source_record(record)

    if not isinstance(record, Mapping):
        return None

    raw_record = dict(record)
    if raw_record.get("record_type") == "dex_pair" and "payload" in raw_record:
        source_record = _validate_model(SourceRecord, raw_record)
        if source_record is None:
            return None
        return _parse_dex_pair_source_record(source_record)

    return _validate_model(DexPairSnapshot, raw_record)


def _parse_dex_pair_source_record(
    source_record: SourceRecord,
) -> DexPairSnapshot | None:
    if source_record.record_type != "dex_pair":
        return None
    if not isinstance(source_record.payload, Mapping):
        return None
    return _validate_model(DexPairSnapshot, dict(source_record.payload))


def _validate_model(model: type[ModelT], payload: Mapping[str, object]) -> ModelT | None:
    try:
        return model.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        pass
    try:
        return model.model_validate_json(json.dumps(payload, default=str))
    except (ValidationError, TypeError, ValueError):
        return None


def _base_metrics(
    *,
    min_liquidity_usd: float,
    min_volume_24h_usd: float,
    min_liquidity_change_pct: float,
    min_volume_change_pct: float,
    min_observations: int,
    supported_chains: Sequence[str],
    max_age_hours: float,
    candidate_count: int,
    candidates: list[dict[str, object]],
    blocked_reasons_observed: list[str] | None = None,
    rejected_group_reasons: list[dict[str, object]] | None = None,
    observed_execution_roles: list[str] | None = None,
) -> dict[str, object]:
    return {
        "execution_role": "research_only",
        "paper_watchlist_only": True,
        "candidate_count": candidate_count,
        "candidates": candidates,
        "blocked_reasons_observed": blocked_reasons_observed or [],
        "rejected_group_reasons": rejected_group_reasons or [],
        "min_liquidity_usd": float(min_liquidity_usd),
        "min_volume_24h_usd": float(min_volume_24h_usd),
        "min_liquidity_change_pct": float(min_liquidity_change_pct),
        "min_volume_change_pct": float(min_volume_change_pct),
        "min_observations": int(min_observations),
        "supported_chains": list(_normalize_string_tuple(supported_chains)),
        "max_age_hours": float(max_age_hours),
        "observed_execution_roles": observed_execution_roles or [],
    }


def _validate_thresholds(
    *,
    min_liquidity_usd: float,
    min_volume_24h_usd: float,
    min_liquidity_change_pct: float,
    min_volume_change_pct: float,
    min_observations: int,
    max_age_hours: float,
    require_research_only: bool,
) -> None:
    if not isinstance(require_research_only, bool):
        raise ValueError("require_research_only must be boolean")
    _validate_non_negative_float(min_liquidity_usd, "min_liquidity_usd")
    _validate_non_negative_float(min_volume_24h_usd, "min_volume_24h_usd")
    _validate_non_negative_float(
        min_liquidity_change_pct,
        "min_liquidity_change_pct",
    )
    _validate_non_negative_float(
        min_volume_change_pct,
        "min_volume_change_pct",
    )
    if isinstance(min_observations, bool):
        raise ValueError("min_observations must be an integer at least 2")
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer at least 2")
    if isinstance(max_age_hours, bool):
        raise ValueError("max_age_hours must be a positive finite number")
    if not math.isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be a positive finite number")


def _validate_non_negative_float(value: float, name: str) -> None:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative finite number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a non-negative finite number")


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
    latest: DexPairSnapshot,
    group_key: tuple[str, str, str],
    blocked_reasons: list[str],
    prior: DexPairSnapshot | None = None,
    liquidity_change_pct: float | None = None,
    volume_change_pct: float | None = None,
    liquidity_direction: str = "unknown",
    volume_direction: str = "unknown",
) -> dict[str, object]:
    metrics: dict[str, object] = {
        "chain": latest.chain,
        "dex": latest.dex,
        "pair_address": latest.pair_address,
        "base_token": latest.base_token,
        "quote_token": latest.quote_token,
        "pair_id": _format_pair_id(group_key),
        "blocked_reasons": _dedupe_blocked_reasons(blocked_reasons),
    }
    if prior is not None:
        metrics.update(
            {
                "latest_observed_at": _format_datetime(latest.observed_at),
                "prior_observed_at": _format_datetime(prior.observed_at),
                "latest_liquidity_usd": latest.liquidity_usd,
                "prior_liquidity_usd": prior.liquidity_usd,
                "liquidity_change_pct": liquidity_change_pct,
                "latest_volume_24h_usd": latest.volume_24h_usd,
                "prior_volume_24h_usd": prior.volume_24h_usd,
                "volume_change_pct": volume_change_pct,
                "liquidity_direction": liquidity_direction,
                "volume_direction": volume_direction,
            }
        )
    return metrics


def _pair_identity(snapshot: DexPairSnapshot) -> tuple[tuple[str, str, str], bool]:
    chain = _normalize_component(snapshot.chain)
    dex = _normalize_component(snapshot.dex)
    pair_address = snapshot.pair_address.strip()
    if not pair_address:
        raw_pair_address = snapshot.raw.get("pairAddress")
        if _has_identity_value(raw_pair_address):
            pair_address = str(raw_pair_address).strip()
    if pair_address:
        return (chain, dex, _normalize_component(pair_address)), False

    identity_payload = _stable_pair_identity_payload(snapshot)
    if identity_payload is None:
        return (chain, dex, "unstable-pair-identity"), True
    digest = hashlib.sha256(
        json.dumps(
            identity_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return (chain, dex, f"pair-hash-{digest}"), False


def _stable_pair_identity_payload(snapshot: DexPairSnapshot) -> dict[str, object] | None:
    raw = snapshot.raw
    url = raw.get("url")
    if _has_identity_value(url):
        return _stable_pair_identity_base(snapshot) | {"url": str(url).strip()}

    pair_created_at = raw.get("pairCreatedAt")
    if _has_identity_value(pair_created_at):
        return _stable_pair_identity_base(snapshot) | {"pairCreatedAt": pair_created_at}

    base_address = _nested_raw_value(raw, "baseToken", "address")
    quote_address = _nested_raw_value(raw, "quoteToken", "address")
    if _has_identity_value(base_address) and _has_identity_value(quote_address):
        return _stable_pair_identity_base(snapshot) | {
            "baseToken.address": str(base_address).strip().lower(),
            "quoteToken.address": str(quote_address).strip().lower(),
        }
    return None


def _stable_pair_identity_base(snapshot: DexPairSnapshot) -> dict[str, object]:
    return {
        "chain": _normalize_component(snapshot.chain),
        "dex": _normalize_component(snapshot.dex),
    }


def _nested_raw_value(
    raw: Mapping[str, object],
    key: str,
    nested_key: str,
) -> object | None:
    value = raw.get(key)
    if not isinstance(value, Mapping):
        return None
    return value.get(nested_key)


def _format_pair_id(group_key: tuple[str, str, str]) -> str:
    return ":".join(group_key)


def _normalize_component(value: object) -> str:
    return str(value).strip().lower()


def _normalize_string_tuple(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = str(value).strip()
        if not stripped or stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return tuple(normalized)


def _has_identity_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping | Sequence):
        return bool(value)
    return True


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("datetime value must be a datetime or ISO datetime string")
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return _coerce_datetime(value).isoformat().replace("+00:00", "Z")


def _change_pct(latest: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return (latest - prior) / prior


def _meets_change(change_pct: float | None, threshold: float) -> bool:
    return change_pct is not None and change_pct >= threshold


def _direction(change_pct: float | None) -> str:
    if change_pct is None:
        return "unknown"
    if change_pct > 0:
        return "up"
    if change_pct < 0:
        return "down"
    return "flat"


def _direct_execution_blocked(
    *,
    require_research_only: bool,
    snapshots: Sequence[DexPairSnapshot],
) -> bool:
    if not require_research_only:
        return True
    return any(
        snapshot.suitability.execution_role != "research_only"
        for snapshot in snapshots
    )


def _observed_execution_roles(snapshots: Sequence[DexPairSnapshot]) -> list[str]:
    roles: list[str] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        role = snapshot.suitability.execution_role
        if role in seen:
            continue
        roles.append(role)
        seen.add(role)
    return roles
