from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.models import (
    DefiYieldSnapshot,
    DexPairSnapshot,
    FundingRateRecord,
    MarketCandle,
    OpenInterestRecord,
    RecordType,
)
from crypto_alpha_agent.data.quality import SourceHealthSnapshot, build_data_quality_report
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import ValidationEvidence
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.risk.charter_guard import guard_generated_idea
from crypto_alpha_agent.strategy import default_strategy_registry


class _StrictAIResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class AIValidationEvidenceSummary(_StrictAIResearchModel):
    evidence_ref: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    validator_name: str = Field(min_length=1)
    trade_count: int = Field(ge=0)
    net_return: float
    gross_expectancy: float
    fee_adjusted_expectancy: float
    slippage_adjusted_expectancy: float
    max_drawdown: float = Field(ge=0)
    walk_forward_split_count: int = Field(ge=0)
    walk_forward_pass_rate: float = Field(ge=0, le=1)
    approved: bool
    blocked_reasons: list[str] = Field(default_factory=list)


class AIPaperEvidenceSummary(_StrictAIResearchModel):
    evidence_ref: str = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    closed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    net_pnl_usd: float
    hit_rate: float
    max_drawdown_usd: float = Field(ge=0)
    total_notional_usd: float = Field(ge=0)
    gross_pnl_usd: float
    total_fees_usd: float = Field(ge=0)
    total_slippage_usd: float = Field(ge=0)
    stale_signal_count: int = Field(ge=0)
    missed_fill_count: int = Field(ge=0)
    partial_fill_count: int = Field(ge=0)
    cost_model_modes: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class AISourceHealthSummary(_StrictAIResearchModel):
    evidence_ref: str = Field(min_length=1)
    source: str = Field(min_length=1)
    feed: str = Field(min_length=1)
    success: bool
    attempts: int = Field(ge=0)
    failure: str | None = None
    observed_at: str = Field(min_length=1)
    records_fetched: int = Field(ge=0)
    records_written: int = Field(ge=0)
    network_route: str = "unknown"
    provider_status: str = "unknown"
    http_status: int | None = Field(default=None, ge=0)
    parse_status: str | None = None
    typed_record_count: int | None = Field(default=None, ge=0)


class AIRegisteredValidatorSummary(_StrictAIResearchModel):
    strategy_family: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    validator_name: str = Field(min_length=1)
    required_record_types: list[RecordType] = Field(min_length=1)
    required_symbols: list[str] = Field(min_length=1)
    execution_role: str = Field(min_length=1)
    supports_paper_simulation: bool
    min_capital_usd: float = Field(ge=0)
    max_notional_usd: float = Field(ge=0)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


class AIResearchContext(_StrictAIResearchModel):
    generated_at: str = Field(min_length=1)
    validation_evidence_summaries: list[AIValidationEvidenceSummary] = Field(default_factory=list)
    paper_evidence_packages: list[AIPaperEvidenceSummary] = Field(default_factory=list)
    source_health_summaries: list[AISourceHealthSummary] = Field(default_factory=list)
    stopped_strategy_families: list[str] = Field(default_factory=list)
    blocked_parameter_sets: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    blocked_parameter_set_count: int = Field(ge=0)
    available_data_fields: dict[str, list[str]] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    registered_validators: list[AIRegisteredValidatorSummary] = Field(default_factory=list)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_ai_research_context(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    strategy_family: str | None = None,
    current_capital_usd: float = 300.0,
    recent_limit: int = 10,
) -> AIResearchContext:
    from crypto_alpha_agent.pipeline.evidence_reports import load_stopped_strategy_families

    if recent_limit <= 0:
        raise ValueError("recent_limit must be positive")

    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence(
        strategy_family=strategy_family
    )[-recent_limit:]
    paper_outcomes = PaperOutcomeLedger(db_path).load_outcomes(
        strategy_family=strategy_family
    )[-recent_limit:]
    paper_evidence = aggregate_paper_evidence(_paper_mapping(outcome) for outcome in paper_outcomes)
    source_health = _recent_source_health(db_path, recent_limit=recent_limit)
    memory_records = MemoryStore(memory_path).list_records()
    blocked_parameter_sets = _blocked_parameter_sets(memory_records)

    validation_summaries = [_validation_summary(item) for item in validation_evidence]
    paper_summaries = [_paper_summary(item) for item in paper_evidence]
    source_health_summaries = [_source_health_summary(item) for item in source_health]

    return AIResearchContext(
        generated_at=DETERMINISTIC_EVENT_TIME_ISO,
        validation_evidence_summaries=validation_summaries,
        paper_evidence_packages=paper_summaries,
        source_health_summaries=source_health_summaries,
        stopped_strategy_families=_safe_string_list(load_stopped_strategy_families(memory_path)),
        blocked_parameter_sets=_safe_blocked_parameter_sets(blocked_parameter_sets),
        blocked_parameter_set_count=sum(len(items) for items in blocked_parameter_sets.values()),
        available_data_fields=_available_data_fields(),
        evidence_refs=[
            *[item.evidence_ref for item in validation_summaries],
            *[item.evidence_ref for item in paper_summaries],
            *[item.evidence_ref for item in source_health_summaries],
        ],
        registered_validators=_registered_validator_summaries(current_capital_usd),
    )


def _validation_summary(item: ValidationEvidence) -> AIValidationEvidenceSummary:
    run_id = item.run_id or "unknown"
    return AIValidationEvidenceSummary(
        evidence_ref=f"validation:{run_id}:{item.evidence_id}",
        evidence_id=item.evidence_id,
        run_id=run_id,
        strategy_family=item.strategy_family,
        symbol=item.symbol,
        timeframe=item.timeframe,
        validator_name=item.validator_name,
        trade_count=item.trade_count,
        net_return=item.net_return,
        gross_expectancy=item.gross_expectancy,
        fee_adjusted_expectancy=item.fee_adjusted_expectancy,
        slippage_adjusted_expectancy=item.slippage_adjusted_expectancy,
        max_drawdown=item.max_drawdown,
        walk_forward_split_count=item.walk_forward_split_count,
        walk_forward_pass_rate=item.walk_forward_pass_rate,
        approved=item.approved,
        blocked_reasons=_safe_string_list(item.blocked_reasons),
    )


def _paper_summary(item: PaperEvidencePackage) -> AIPaperEvidenceSummary:
    return AIPaperEvidenceSummary(
        evidence_ref=f"paper:{item.strategy_family}:sample_size:{item.sample_size}",
        strategy_family=item.strategy_family,
        sample_size=item.sample_size,
        closed_count=item.closed_count,
        failed_count=item.failed_count,
        blocked_count=item.blocked_count,
        net_pnl_usd=item.net_pnl_usd,
        hit_rate=item.hit_rate,
        max_drawdown_usd=item.max_drawdown_usd,
        total_notional_usd=item.total_notional_usd,
        gross_pnl_usd=item.gross_pnl_usd,
        total_fees_usd=item.total_fees_usd,
        total_slippage_usd=item.total_slippage_usd,
        stale_signal_count=item.stale_signal_count,
        missed_fill_count=item.missed_fill_count,
        partial_fill_count=item.partial_fill_count,
        cost_model_modes=_safe_string_list(item.cost_model_modes),
        failure_reasons=_safe_string_list(item.failure_reasons),
    )


def _source_health_summary(item: SourceHealthSnapshot) -> AISourceHealthSummary:
    observed_at = item.observed_at.isoformat()
    return AISourceHealthSummary(
        evidence_ref=f"source_health:{item.source}:{item.feed}:{observed_at}",
        source=_safe_string(item.source),
        feed=_safe_string(item.feed),
        success=item.success,
        attempts=item.attempts,
        failure=None if item.failure is None else _safe_string(item.failure),
        observed_at=observed_at,
        records_fetched=item.records_fetched,
        records_written=item.records_written,
        network_route=_safe_string(item.network_route),
        provider_status=_safe_string(item.provider_status),
        http_status=item.http_status,
        parse_status=None if item.parse_status is None else _safe_string(item.parse_status),
        typed_record_count=item.typed_record_count,
    )


def _recent_source_health(
    db_path: str | Path,
    *,
    recent_limit: int,
) -> list[SourceHealthSnapshot]:
    records = ResearchDataStore(db_path).load_records(record_type="source_health")
    report = build_data_quality_report(records)
    return report.source_health[-recent_limit:]


def _paper_mapping(outcome: Any) -> dict[str, Any]:
    return {
        "strategy_family": outcome.strategy_family,
        "trade_id": outcome.outcome_id,
        "symbol": outcome.symbol,
        "status": outcome.status,
        "realized_net_pnl": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "notional_usd": outcome.notional_usd,
        "gross_pnl_usd": outcome.gross_pnl_usd,
        "fees_usd": outcome.fees_usd,
        "slippage_usd": outcome.slippage_usd,
        "cost_model_mode": outcome.cost_model_mode,
        "stale_signal_status": outcome.stale_signal_status,
        "fill_status": outcome.fill_status,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _blocked_parameter_sets(records: Iterable[MemoryRecord]) -> dict[str, list[dict[str, Any]]]:
    blocked: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if not record.rejected_reasons and "blocked" not in record.tags and "rejected" not in record.tags:
            continue
        family = _family_from_record(record)
        if family is None:
            continue
        for parameters in _record_parameter_sets(record):
            blocked.setdefault(family, []).append(parameters)
    return blocked


def _record_parameter_sets(record: MemoryRecord) -> list[dict[str, Any]]:
    parameter_sets: list[dict[str, Any]] = []
    for section in (record.opportunity, record.hypothesis, record.score, record.paper_trade_outcome):
        if not isinstance(section, Mapping):
            continue
        parameter_sets.extend(_parameters_from_mapping(section))
    return parameter_sets


def _parameters_from_mapping(section: Mapping[str, Any]) -> list[dict[str, Any]]:
    parameter_sets: list[dict[str, Any]] = []
    for key in ("parameter_changes", "parameters"):
        value = section.get(key)
        if isinstance(value, dict):
            parameter_sets.append(dict(value))
    proposal = section.get("proposal")
    if isinstance(proposal, Mapping):
        parameter_sets.extend(_parameters_from_mapping(proposal))
    return parameter_sets


def _family_from_record(record: MemoryRecord) -> str | None:
    for section in (record.opportunity, record.hypothesis, record.score, record.paper_trade_outcome):
        if not isinstance(section, Mapping):
            continue
        family = _family_from_mapping(section)
        if family is not None:
            return family
    return None


def _family_from_mapping(section: Mapping[str, Any]) -> str | None:
    family = section.get("strategy_family")
    if isinstance(family, str) and family.strip():
        return family.strip()
    proposal = section.get("proposal")
    if isinstance(proposal, Mapping):
        return _family_from_mapping(proposal)
    return None


def _safe_blocked_parameter_sets(value: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    safe: dict[str, list[dict[str, Any]]] = {}
    for family, parameter_sets in value.items():
        safe_family = _safe_string(family)
        if not safe_family:
            continue
        safe[safe_family] = [
            parameters
            for parameters in (_safe_context_value(item) for item in parameter_sets)
            if isinstance(parameters, dict)
        ]
    return safe


def _available_data_fields() -> dict[str, list[str]]:
    return {
        "market_candle": _model_fields(MarketCandle),
        "funding_rate": _model_fields(FundingRateRecord),
        "open_interest": _model_fields(OpenInterestRecord),
        "dex_pair": _model_fields(DexPairSnapshot),
        "defi_yield": _model_fields(DefiYieldSnapshot),
        "research_snapshot": ["source", "asset", "metric", "value", "observed_at"],
        "source_health": _model_fields(SourceHealthSnapshot),
    }


def _model_fields(model: type[BaseModel]) -> list[str]:
    return sorted(str(field) for field in model.model_fields)


def _registered_validator_summaries(current_capital_usd: float) -> list[AIRegisteredValidatorSummary]:
    registry = default_strategy_registry(current_capital_usd=current_capital_usd)
    summaries: list[AIRegisteredValidatorSummary] = []
    for family in registry.list_families():
        spec = registry.get(family)
        summaries.append(
            AIRegisteredValidatorSummary(
                strategy_family=spec.strategy_family,
                display_name=spec.display_name,
                validator_name=spec.validator_name,
                required_record_types=list(spec.required_record_types),
                required_symbols=list(spec.required_symbols),
                execution_role=spec.execution_role,
                supports_paper_simulation=spec.supports_paper_simulation,
                min_capital_usd=spec.min_capital_usd,
                max_notional_usd=spec.max_notional_usd,
            )
        )
    return summaries


def _safe_context_value(value: Any) -> Any:
    if isinstance(value, str):
        return _safe_string(value)
    if isinstance(value, Mapping):
        return {
            str(_safe_context_value(key)): _safe_context_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_safe_context_value(item) for item in value]
    return value


def _safe_string_list(values: Iterable[str]) -> list[str]:
    safe_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        safe_value = _safe_string(str(value))
        if not safe_value or safe_value in seen:
            continue
        safe_values.append(safe_value)
        seen.add(safe_value)
    return safe_values


def _safe_string(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped if guard_generated_idea(stripped).approved else "unsafe_text_omitted"
