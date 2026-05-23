from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import SourceRecord
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.pipeline.evidence_reports import (
    WeeklyEvidenceReport,
    build_weekly_evidence_report,
)
from crypto_alpha_agent.strategy import default_strategy_registry

SourceReadiness = Literal["health_recorded", "needs_source_probe", "blocked"]
StrategyReadiness = Literal["registered", "blocked"]
AdapterKind = Literal["deterministic_validator", "watchlist_only_adapter", "blocked"]
CredentialRequirement = Literal["none", "optional_api_key", "required_api_key"]
NextPhase = Literal["phase_8_data_depth", "phase_9_strategy_validators"]
RecommendedAction = Literal["continue", "stop", "redesign", "add_data"]


class _StrictExpansionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExpansionSourceCandidate(_StrictExpansionModel):
    priority: int = Field(ge=1)
    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    feed: str = Field(min_length=1)
    endpoint_family: str = Field(min_length=1)
    data_fields: list[str] = Field(min_length=1)
    credential_requirement: CredentialRequirement
    source_health_source: str = Field(min_length=1)
    source_health_feed: str = Field(min_length=1)
    source_health_present: bool
    latest_source_health_route: str = "unknown"
    readiness: SourceReadiness
    blocked_reasons: list[str] = Field(default_factory=list)
    next_phase: NextPhase = "phase_8_data_depth"
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class ExpansionStrategyCandidate(_StrictExpansionModel):
    priority: int = Field(ge=1)
    strategy_family: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    adapter_kind: AdapterKind
    readiness: StrategyReadiness
    required_data_fields: list[str] = Field(min_length=1)
    recommended_action: RecommendedAction
    action_reason_codes: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    next_phase: NextPhase = "phase_9_strategy_validators"
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class ExpansionPreparationReport(_StrictExpansionModel):
    source_candidates: list[ExpansionSourceCandidate]
    strategy_candidates: list[ExpansionStrategyCandidate]
    weekly_report: WeeklyEvidenceReport
    source_readiness_counts: dict[str, int]
    strategy_action_counts: dict[str, int]
    reason_codes: list[str] = Field(default_factory=list)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


_SOURCE_CATALOG = [
    {
        "priority": 1,
        "source_id": "binance_usdm_open_interest",
        "display_name": "Binance USD-M Current Open Interest",
        "provider": "binance_usdm",
        "feed": "open_interest",
        "endpoint_family": "GET /fapi/v1/openInterest",
        "data_fields": ["symbol", "open_interest", "observed_at"],
        "credential_requirement": "none",
        "source_health_source": "binance_usdm",
        "source_health_feed": "open_interest",
    },
    {
        "priority": 2,
        "source_id": "binance_usdm_open_interest_history",
        "display_name": "Binance USD-M Open Interest History",
        "provider": "binance_usdm",
        "feed": "open_interest_history",
        "endpoint_family": "GET /futures/data/openInterestHist",
        "data_fields": [
            "symbol",
            "open_interest",
            "open_interest_value",
            "timestamp",
        ],
        "credential_requirement": "none",
        "source_health_source": "binance_usdm",
        "source_health_feed": "open_interest_history",
    },
    {
        "priority": 3,
        "source_id": "coinalyze_derivatives_history",
        "display_name": "Coinalyze Derivatives History",
        "provider": "coinalyze",
        "feed": "derivatives_history",
        "endpoint_family": (
            "open-interest-history, funding-rate-history, "
            "liquidation-history, long-short-ratio-history"
        ),
        "data_fields": [
            "open_interest",
            "funding_rate",
            "liquidation_long",
            "liquidation_short",
            "long_short_ratio",
        ],
        "credential_requirement": "required_api_key",
        "source_health_source": "coinalyze",
        "source_health_feed": "derivatives_history",
    },
    {
        "priority": 4,
        "source_id": "ccxt_open_interest_history",
        "display_name": "CCXT Open Interest History",
        "provider": "ccxt",
        "feed": "open_interest_history",
        "endpoint_family": "fetchOpenInterestHistory when exchange-supported",
        "data_fields": ["exchange", "symbol", "open_interest", "timestamp"],
        "credential_requirement": "none",
        "source_health_source": "ccxt",
        "source_health_feed": "open_interest_history",
    },
    {
        "priority": 5,
        "source_id": "defillama_yield_pools",
        "display_name": "DefiLlama Yield Pools",
        "provider": "defillama",
        "feed": "yield_pools",
        "endpoint_family": "GET /pools",
        "data_fields": ["chain", "project", "symbol", "tvl_usd", "apy"],
        "credential_requirement": "none",
        "source_health_source": "defillama",
        "source_health_feed": "yield_pools",
    },
    {
        "priority": 6,
        "source_id": "defillama_fundamentals",
        "display_name": "DefiLlama TVL, Stablecoins, Fees, And Revenue",
        "provider": "defillama",
        "feed": "fundamentals",
        "endpoint_family": "TVL, stablecoins, fees, revenue, volumes",
        "data_fields": [
            "tvl",
            "stablecoin_supply",
            "fees",
            "revenue",
            "dex_volume",
        ],
        "credential_requirement": "none",
        "source_health_source": "defillama",
        "source_health_feed": "fundamentals",
    },
    {
        "priority": 7,
        "source_id": "dexscreener_liquidity_snapshots",
        "display_name": "DEX Screener Liquidity Snapshots",
        "provider": "dexscreener",
        "feed": "pairs",
        "endpoint_family": "latest/dex/search, latest/dex/pairs, tokens/v1",
        "data_fields": [
            "chain",
            "dex",
            "pair_address",
            "liquidity_usd",
            "volume_24h_usd",
        ],
        "credential_requirement": "none",
        "source_health_source": "dexscreener",
        "source_health_feed": "pairs",
    },
]

_STRATEGY_CATALOG = [
    {
        "priority": 1,
        "strategy_family": "funding_mean_reversion_after_extreme",
        "display_name": "Funding Mean Reversion After Extreme",
        "required_data_fields": ["market_candle", "funding_rate", "open_interest"],
    },
    {
        "priority": 2,
        "strategy_family": "funding_oi_crowding_candidate",
        "display_name": "Funding Plus OI Crowding Candidate",
        "required_data_fields": ["market_candle", "funding_rate", "open_interest"],
    },
    {
        "priority": 3,
        "strategy_family": "cross_exchange_funding_dispersion_candidate",
        "display_name": "Cross-Exchange Funding Dispersion Candidate",
        "required_data_fields": [
            "multi_exchange_funding_rate",
            "symbol_normalization",
        ],
    },
    {
        "priority": 4,
        "strategy_family": "defi_yield_regime_watchlist",
        "display_name": "DefiLlama Yield Regime Watchlist",
        "required_data_fields": ["defi_yield", "tvl_usd", "apy"],
    },
    {
        "priority": 5,
        "strategy_family": "defi_stablecoin_tvl_regime_candidate",
        "display_name": "DeFi Stablecoin And TVL Regime Candidate",
        "required_data_fields": [
            "stablecoin_supply",
            "protocol_tvl",
            "fees",
            "revenue",
        ],
    },
    {
        "priority": 6,
        "strategy_family": "dex_liquidity_volume_watchlist",
        "display_name": "DEX Liquidity And Volume Regime Watchlist",
        "required_data_fields": ["dex_pair", "liquidity_usd", "volume_24h_usd"],
    },
]


def build_expansion_preparation_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    current_capital_usd: float = 300.0,
) -> ExpansionPreparationReport:
    store = ResearchDataStore(db_path)
    source_health_records = store.load_records(record_type="source_health")
    weekly_report = build_weekly_evidence_report(
        db_path=db_path,
        memory_path=memory_path,
    )
    registry = default_strategy_registry(current_capital_usd=current_capital_usd)
    weekly_by_family = {
        summary.strategy_family: summary
        for summary in weekly_report.family_summaries
    }
    sources = [
        _source_candidate(definition, source_health_records)
        for definition in _SOURCE_CATALOG
    ]
    strategies = [
        _strategy_candidate(
            definition,
            registry=registry,
            weekly_by_family=weekly_by_family,
            current_capital_usd=current_capital_usd,
        )
        for definition in _STRATEGY_CATALOG
    ]
    return ExpansionPreparationReport(
        source_candidates=sources,
        strategy_candidates=strategies,
        weekly_report=weekly_report,
        source_readiness_counts=dict(Counter(source.readiness for source in sources)),
        strategy_action_counts=dict(
            Counter(strategy.recommended_action for strategy in strategies)
        ),
        reason_codes=_report_reason_codes(sources, strategies),
    )


def _source_candidate(
    definition: dict[str, object],
    records: list[SourceRecord],
) -> ExpansionSourceCandidate:
    latest = _latest_source_health(
        records,
        source=str(definition["source_health_source"]),
        feed=str(definition["source_health_feed"]),
    )
    blocked_reasons: list[str] = []
    route = "unknown"
    if latest is None:
        blocked_reasons.extend(["source_health_missing", "source_probe_required"])
        readiness: SourceReadiness = "needs_source_probe"
        if definition["credential_requirement"] == "required_api_key":
            blocked_reasons.append("credential_required")
    else:
        payload = latest.payload
        route = str(payload.get("network_route", "unknown"))
        success = _strict_bool(payload.get("success"))
        records_written = _non_negative_int_or_none(payload.get("records_written"))
        typed_record_count = _non_negative_int_or_none(payload.get("typed_record_count"))
        has_typed_record_count = "typed_record_count" in payload
        provider_status = str(payload.get("provider_status", "unknown"))
        usable_record_count = (
            typed_record_count
            if typed_record_count is not None
            else records_written
        )
        if (
            success is None
            or records_written is None
            or (has_typed_record_count and typed_record_count is None)
        ):
            blocked_reasons.append("source_health_malformed")
        elif not success:
            blocked_reasons.append("source_health_failed")
        elif (
            provider_status
            not in {"unknown", "ResearchUsable", "ProductionResearchSource"}
        ):
            blocked_reasons.append("source_probe_not_research_usable")
        if usable_record_count is not None and usable_record_count <= 0:
            blocked_reasons.append("no_typed_records")
        readiness = "health_recorded"
    if definition["credential_requirement"] == "required_api_key":
        blocked_reasons.append("credential_required")
    if blocked_reasons:
        readiness = "blocked" if latest is not None else "needs_source_probe"
    return ExpansionSourceCandidate(
        **definition,
        source_health_present=latest is not None,
        latest_source_health_route=route,
        readiness=readiness,
        blocked_reasons=_dedupe(blocked_reasons),
    )


def _strategy_candidate(
    definition: dict[str, object],
    *,
    registry: object,
    weekly_by_family: dict[str, object],
    current_capital_usd: float,
) -> ExpansionStrategyCandidate:
    family = str(definition["strategy_family"])
    blocked_reasons: list[str] = []
    try:
        spec = registry.get(family)
    except KeyError:
        spec = None

    summary = weekly_by_family.get(family)
    if spec is None:
        adapter_kind: AdapterKind = "blocked"
        readiness: StrategyReadiness = "blocked"
        blocked_reasons.append("validator_or_watchlist_not_registered")
    else:
        adapter_kind = (
            "deterministic_validator"
            if spec.supports_paper_simulation
            else "watchlist_only_adapter"
        )
        readiness = "registered"
        blocked_reasons.extend(spec.blocked_reasons)
        if current_capital_usd < spec.min_capital_usd:
            blocked_reasons.append("insufficient_current_capital")
    if family == "funding_mean_reversion_after_extreme":
        blocked_reasons.append("open_interest_confirmation_missing")
    if blocked_reasons:
        readiness = "blocked"

    recommended_action: RecommendedAction = getattr(
        summary,
        "recommended_action",
        "add_data",
    )
    action_reason_codes = list(
        getattr(summary, "action_reason_codes", ["no_weekly_family_evidence"])
    )
    if "insufficient_current_capital" in blocked_reasons:
        recommended_action = "add_data"
        action_reason_codes = _dedupe(
            [*action_reason_codes, "capital_below_strategy_minimum"]
        )
    elif "validator_or_watchlist_not_registered" in blocked_reasons:
        recommended_action = "add_data"
        action_reason_codes = _dedupe(
            [*action_reason_codes, "register_validator_or_watchlist"]
        )
    elif "open_interest_confirmation_missing" in blocked_reasons:
        recommended_action = "add_data"
        action_reason_codes = _dedupe(
            [*action_reason_codes, "required_data_missing"]
        )
    elif blocked_reasons:
        recommended_action = "redesign"
        action_reason_codes = _dedupe([*action_reason_codes, "adapter_blocked"])

    return ExpansionStrategyCandidate(
        **definition,
        adapter_kind=adapter_kind,
        readiness=readiness,
        recommended_action=recommended_action,
        action_reason_codes=action_reason_codes,
        blocked_reasons=_dedupe(blocked_reasons),
    )


def _latest_source_health(
    records: list[SourceRecord],
    *,
    source: str,
    feed: str,
) -> SourceRecord | None:
    matches = [
        record
        for record in records
        if record.source == source and str(record.payload.get("feed", "")) == feed
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda record: record.observed_at)[-1]


def _report_reason_codes(
    sources: list[ExpansionSourceCandidate],
    strategies: list[ExpansionStrategyCandidate],
) -> list[str]:
    codes: list[str] = ["phase_5_expansion_preparation"]
    if any(source.blocked_reasons for source in sources):
        codes.append("source_candidates_need_probe")
    if any(strategy.blocked_reasons for strategy in strategies):
        codes.append("strategy_candidates_need_data_or_adapter")
    if any(strategy.adapter_kind == "watchlist_only_adapter" for strategy in strategies):
        codes.append("watchlist_adapters_registered")
    return _dedupe(codes)


def _strict_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _non_negative_int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
