from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.ccxt_collector import CcxtResearchCollector
from crypto_alpha_agent.data.ingestion import (
    ingest_ccxt_funding_rate_history,
    ingest_ccxt_ohlcv,
    ingest_defillama_yield_pools,
    ingest_dexscreener_pairs,
)
from crypto_alpha_agent.data.onchain_ingestion import (
    ingest_dune_query_result,
    ingest_thegraph_query_result,
)
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.pipeline.evidence_reports import (
    load_stopped_strategy_families,
    record_stopped_family_override_used,
)
from crypto_alpha_agent.pipeline.markdown import render_research_loop_markdown
from crypto_alpha_agent.pipeline.memory import (
    replace_paper_outcome_memory,
    replace_research_loop_memory,
    replace_validation_evidence_memory,
)
from crypto_alpha_agent.pipeline.paper_sim_loop import run_paper_sim_loop
from crypto_alpha_agent.pipeline.research_loop import ResearchLoopReport, run_stored_research_loop
from crypto_alpha_agent.strategy import default_strategy_registry

DEFAULT_STRATEGY_FAMILIES = ("funding_extremity_price_confirmation",)
OPTIONAL_SOURCES = frozenset({"dexscreener", "defillama", "dune", "thegraph"})
_URL_PATTERN = re.compile(r"https?://[^\s'\";,)}]+")


class EvidenceRunnerStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    name: str = Field(min_length=1)
    status: Literal["completed", "blocked", "failed", "skipped"]
    records_written: int = Field(default=0, ge=0)
    reason_code: str | None = None


class ResearchMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    loaded_records: int = Field(ge=0)
    signal_count: int = Field(ge=0)
    anomaly_count: int = Field(ge=0)
    hypothesis_count: int = Field(ge=0)
    reflection_count: int = Field(ge=0)
    accept_reject_reason_count: int = Field(ge=0)


class SourceHealthSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    source: str = Field(min_length=1)
    feed: str = Field(min_length=1)
    status: Literal["success", "failure", "blocked", "skipped", "not_configured"]
    records_written: int = Field(default=0, ge=0)
    reason_code: str | None = None
    failure: str | None = None


class SourceHealthReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    items: list[SourceHealthSummary]
    optional_source_skipped: int = Field(ge=0)
    optional_source_failures: int = Field(ge=0)
    failures: list[SourceHealthSummary]


class EvidenceRunnerReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    run_id: str
    started_at: datetime
    db_path: str
    memory_path: str
    strategy_families: list[str]
    skipped_strategy_families: list[str] = Field(default_factory=list)
    steps: list[EvidenceRunnerStep]
    records_written: int = Field(ge=0)
    validation_evidence_written: int = Field(ge=0)
    paper_outcomes_written: int = Field(ge=0)
    memory_records_written: int = Field(ge=0)
    report_artifact: str | None
    research_milestone: ResearchMilestone
    source_health: SourceHealthReport
    decision_reason_codes: list[str]
    stopped_family_override_used: bool = False
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_ccxt_collector(exchange_id: str) -> CcxtResearchCollector:
    return CcxtResearchCollector(exchange_id=exchange_id)


def run_daily_evidence_pipeline(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    report_out: str | Path,
    current_capital_usd: float = 300.0,
    allow_network: bool = False,
    ccxt_exchange: str = "binance",
    symbol: str,
    funding_symbol: str,
    timeframe: str,
    limit: int = 200,
    strategy_families: Sequence[str] = DEFAULT_STRATEGY_FAMILIES,
    run_id: str | None = None,
    ccxt_collector: Any | None = None,
    dex_client: Any | None = None,
    defillama_client: Any | None = None,
    dune_client: Any | None = None,
    thegraph_client: Any | None = None,
    include_defillama: bool = False,
    include_dexscreener: bool = False,
    dex_query: str | None = None,
    min_tvl_usd: float | None = None,
    include_dune: bool = False,
    dune_query_id: int | None = None,
    dune_api_key: str | None = None,
    dune_params: dict[str, Any] | None = None,
    include_thegraph: bool = False,
    subgraph_url: str | None = None,
    graph_query: str | None = None,
    graph_variables: dict[str, Any] | None = None,
    allow_stopped_family: bool = False,
) -> EvidenceRunnerReport:
    started_at = datetime.now(tz=UTC)
    resolved_run_id = run_id or f"daily-evidence-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    family_list = _normalize_strategy_families(strategy_families)
    db = Path(db_path)
    memory = Path(memory_path)
    artifact = Path(report_out)
    stopped_family_set = set(load_stopped_strategy_families(memory))
    skipped_family_list = (
        []
        if allow_stopped_family
        else [family for family in family_list if family in stopped_family_set]
    )
    active_family_list = (
        family_list
        if allow_stopped_family
        else [family for family in family_list if family not in stopped_family_set]
    )
    stopped_family_override_used = allow_stopped_family and any(
        family in stopped_family_set for family in family_list
    )

    if not allow_network:
        return _blocked_network_report(
            db_path=db,
            memory_path=memory,
            report_out=artifact,
            started_at=started_at,
            run_id=resolved_run_id,
            strategy_families=family_list,
            skipped_strategy_families=skipped_family_list,
            stopped_family_override_used=stopped_family_override_used,
        )

    steps: list[EvidenceRunnerStep] = []
    source_health: list[SourceHealthSummary] = []
    decision_reason_codes: list[str] = []
    if skipped_family_list:
        decision_reason_codes.append("stopped_family_skipped")
        steps.append(
            EvidenceRunnerStep(
                name="stopped_strategy_family",
                status="skipped",
                records_written=len(skipped_family_list),
                reason_code="stopped_family_skipped",
            )
        )
    if stopped_family_override_used:
        decision_reason_codes.append("stopped_family_override_used")
    records_written = 0

    collector = ccxt_collector or build_ccxt_collector(ccxt_exchange)
    try:
        ohlcv_summary = ingest_ccxt_ohlcv(
            db,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            allow_network=True,
            exchange_id=ccxt_exchange,
            collector=collector,
        )
        records_written += ohlcv_summary.records_written
        steps.append(
            EvidenceRunnerStep(
                name="ingest_ccxt_ohlcv",
                status="completed",
                records_written=ohlcv_summary.records_written,
            )
        )
        source_health.append(
            _source_health_from_summary(ohlcv_summary.source, ohlcv_summary.feed, ohlcv_summary.records_written)
        )

        funding_summary = ingest_ccxt_funding_rate_history(
            db,
            symbol=funding_symbol,
            limit=limit,
            allow_network=True,
            exchange_id=ccxt_exchange,
            collector=collector,
        )
        records_written += funding_summary.records_written
        steps.append(
            EvidenceRunnerStep(
                name="ingest_ccxt_funding",
                status="completed",
                records_written=funding_summary.records_written,
            )
        )
        source_health.append(
            _source_health_from_summary(funding_summary.source, funding_summary.feed, funding_summary.records_written)
        )
    except Exception as exc:
        decision_reason_codes.append("core_source_failed")
        steps.append(
            EvidenceRunnerStep(
                name="ingest_ccxt_core",
                status="failed",
                reason_code="core_source_failed",
            )
        )
        source_health.append(
            SourceHealthSummary(
                source="ccxt",
                feed="core",
                status="failure",
                reason_code="core_source_failed",
                failure=str(exc),
            )
        )
        return _report(
            run_id=resolved_run_id,
            started_at=started_at,
            db_path=db,
            memory_path=memory,
            strategy_families=family_list,
            skipped_strategy_families=skipped_family_list,
            steps=steps,
            records_written=records_written,
            validation_evidence_written=0,
            paper_outcomes_written=0,
            memory_records_written=0,
            report_artifact=None,
            research_milestone=_empty_research_milestone(),
            source_health=source_health,
            decision_reason_codes=decision_reason_codes,
            stopped_family_override_used=stopped_family_override_used,
        )

    optional_records = _run_optional_sources(
        db_path=db,
        allow_network=True,
        include_defillama=include_defillama,
        include_dexscreener=include_dexscreener,
        dex_query=dex_query,
        min_tvl_usd=min_tvl_usd,
        include_dune=include_dune,
        dune_query_id=dune_query_id,
        dune_api_key=dune_api_key,
        dune_params=dune_params,
        include_thegraph=include_thegraph,
        subgraph_url=subgraph_url,
        graph_query=graph_query,
        graph_variables=graph_variables,
        dex_client=dex_client,
        defillama_client=defillama_client,
        dune_client=dune_client,
        thegraph_client=thegraph_client,
    )
    records_written += optional_records.records_written
    source_health.extend(optional_records.source_health)
    decision_reason_codes.extend(optional_records.decision_reason_codes)

    research_report = run_stored_research_loop(
        db,
        current_capital_usd=current_capital_usd,
        run_id=resolved_run_id,
        memory_path=memory,
        allow_stopped_family=allow_stopped_family,
    )
    steps.append(EvidenceRunnerStep(name="research_loop", status="completed"))

    validation_summaries = []
    validation_evidence_written = 0
    validation_memory_written = 0
    paper_packages = []
    paper_outcomes: list[PaperSimulationOutcome] = []
    registry = default_strategy_registry(current_capital_usd=current_capital_usd)

    for family in active_family_list:
        family_run_id = _family_run_id(resolved_run_id, family, family_list)
        validation_kwargs = _validation_parameter_kwargs(
            registry=registry,
            strategy_family=family,
            symbol=symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
        )
        validation_report = run_stored_research_loop(
            db,
            current_capital_usd=current_capital_usd,
            run_id=family_run_id,
            include_validation=True,
            strategy_family=family,
            memory_path=memory,
            allow_stopped_family=allow_stopped_family,
            **validation_kwargs,
        )
        decision_reason_codes.extend(validation_report.decision_reason_codes)
        validation_summaries.extend(validation_report.validation_summaries)
        evidence_items = ValidationEvidenceLedger(db).load_evidence(run_id=family_run_id)
        validation_evidence_written += len(evidence_items)
        validation_memory_written += len(
            replace_validation_evidence_memory(
                evidence_items,
                memory,
                run_id=family_run_id,
            )
        )

        if not _supports_paper_simulation(registry, family):
            continue
        paper_report = run_paper_sim_loop(
            db,
            strategy_family=family,
            price_symbol=symbol,
            funding_symbol=funding_symbol,
            timeframe=timeframe,
            run_id=family_run_id,
            current_capital_usd=current_capital_usd,
        )
        paper_outcomes.extend(paper_report.outcomes)
        paper_packages.extend(paper_report.paper_evidence_packages)

    steps.append(
        EvidenceRunnerStep(
            name="strategy_validation",
            status="completed",
            records_written=validation_evidence_written,
        )
    )
    steps.append(
        EvidenceRunnerStep(
            name="validation_memory",
            status="completed",
            records_written=validation_memory_written,
        )
    )
    steps.append(
        EvidenceRunnerStep(
            name="paper_simulation",
            status="completed",
            records_written=len(paper_outcomes),
        )
    )
    paper_run_ids = [_family_run_id(resolved_run_id, family, family_list) for family in active_family_list]
    paper_memory_records = replace_paper_outcome_memory(
        paper_outcomes,
        memory,
        run_ids=paper_run_ids,
    )
    steps.append(
        EvidenceRunnerStep(
            name="paper_memory",
            status="completed",
            records_written=len(paper_memory_records),
        )
    )

    final_research_report = research_report.model_copy(
        update={
            "validation_summaries": validation_summaries,
            "paper_evidence_packages": paper_packages,
            "notes": _dedupe([*research_report.notes, *decision_reason_codes]),
            "decision_reason_codes": _dedupe(
                [*research_report.decision_reason_codes, *decision_reason_codes]
            ),
        }
    )
    research_memory_records = replace_research_loop_memory(final_research_report, memory)
    override_memory_records = (
        [
            record_stopped_family_override_used(
                family,
                memory,
                run_id=resolved_run_id,
                command="evidence-run",
            )
            for family in family_list
            if family in stopped_family_set
        ]
        if stopped_family_override_used
        else []
    )

    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(render_research_loop_markdown(final_research_report), encoding="utf-8")
    steps.append(
        EvidenceRunnerStep(
            name="daily_report",
            status="completed",
        )
    )

    milestone = _research_milestone(final_research_report, paper_outcomes)
    return _report(
        run_id=resolved_run_id,
        started_at=started_at,
        db_path=db,
        memory_path=memory,
        strategy_families=family_list,
        skipped_strategy_families=skipped_family_list,
        steps=steps,
        records_written=records_written,
        validation_evidence_written=validation_evidence_written,
        paper_outcomes_written=len(paper_outcomes),
        memory_records_written=(
            len(research_memory_records)
            + validation_memory_written
            + len(paper_memory_records)
            + len(override_memory_records)
        ),
        report_artifact=str(artifact),
        research_milestone=milestone,
        source_health=source_health,
        decision_reason_codes=_dedupe(decision_reason_codes),
        stopped_family_override_used=stopped_family_override_used,
    )


class _OptionalSourceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    records_written: int = Field(ge=0)
    source_health: list[SourceHealthSummary]
    decision_reason_codes: list[str]


def _run_optional_sources(
    *,
    db_path: Path,
    allow_network: bool,
    include_defillama: bool,
    include_dexscreener: bool,
    dex_query: str | None,
    min_tvl_usd: float | None,
    include_dune: bool,
    dune_query_id: int | None,
    dune_api_key: str | None,
    dune_params: dict[str, Any] | None,
    include_thegraph: bool,
    subgraph_url: str | None,
    graph_query: str | None,
    graph_variables: dict[str, Any] | None,
    dex_client: Any | None,
    defillama_client: Any | None,
    dune_client: Any | None,
    thegraph_client: Any | None,
) -> _OptionalSourceResult:
    records_written = 0
    health: list[SourceHealthSummary] = []
    reasons: list[str] = []

    records_written += _optional_dexscreener(
        db_path=db_path,
        allow_network=allow_network,
        include=include_dexscreener,
        dex_query=dex_query,
        dex_client=dex_client,
        health=health,
        reasons=reasons,
    )
    records_written += _optional_defillama(
        db_path=db_path,
        allow_network=allow_network,
        include=include_defillama,
        min_tvl_usd=min_tvl_usd,
        defillama_client=defillama_client,
        health=health,
        reasons=reasons,
    )
    records_written += _optional_dune(
        db_path=db_path,
        allow_network=allow_network,
        include=include_dune,
        query_id=dune_query_id,
        api_key=dune_api_key,
        params=dune_params,
        client=dune_client,
        health=health,
        reasons=reasons,
    )
    records_written += _optional_thegraph(
        db_path=db_path,
        allow_network=allow_network,
        include=include_thegraph,
        subgraph_url=subgraph_url,
        graph_query=graph_query,
        variables=graph_variables,
        client=thegraph_client,
        health=health,
        reasons=reasons,
    )

    return _OptionalSourceResult(
        records_written=records_written,
        source_health=health,
        decision_reason_codes=_dedupe(reasons),
    )


def _optional_dexscreener(
    *,
    db_path: Path,
    allow_network: bool,
    include: bool,
    dex_query: str | None,
    dex_client: Any | None,
    health: list[SourceHealthSummary],
    reasons: list[str],
) -> int:
    if not include:
        health.append(_not_configured("dexscreener", "pairs"))
        return 0
    if not _has_text(dex_query):
        health.append(_not_configured("dexscreener", "pairs", reason_code="missing_config"))
        return 0
    try:
        summary = ingest_dexscreener_pairs(
            db_path,
            query=dex_query,
            allow_network=allow_network,
            client=dex_client,
        )
    except Exception as exc:
        reasons.append("optional_source_failed")
        health.append(_optional_failure("dexscreener", "pairs", exc))
        return 0
    health.append(_source_health_from_summary(summary.source, summary.feed, summary.records_written))
    return summary.records_written


def _optional_defillama(
    *,
    db_path: Path,
    allow_network: bool,
    include: bool,
    min_tvl_usd: float | None,
    defillama_client: Any | None,
    health: list[SourceHealthSummary],
    reasons: list[str],
) -> int:
    if not include:
        health.append(_not_configured("defillama", "yield_pools"))
        return 0
    try:
        summary = ingest_defillama_yield_pools(
            db_path,
            min_tvl_usd=10000.0 if min_tvl_usd is None else min_tvl_usd,
            allow_network=allow_network,
            client=defillama_client,
        )
    except Exception as exc:
        reasons.append("optional_source_failed")
        health.append(_optional_failure("defillama", "yield_pools", exc))
        return 0
    health.append(_source_health_from_summary(summary.source, summary.feed, summary.records_written))
    return summary.records_written


def _optional_dune(
    *,
    db_path: Path,
    allow_network: bool,
    include: bool,
    query_id: int | None,
    api_key: str | None,
    params: dict[str, Any] | None,
    client: Any | None,
    health: list[SourceHealthSummary],
    reasons: list[str],
) -> int:
    if not include:
        health.append(_not_configured("dune", "dune_query_result"))
        return 0
    if query_id is None or (client is None and not _has_text(api_key)):
        health.append(_not_configured("dune", "dune_query_result", reason_code="missing_config"))
        return 0
    try:
        summary = ingest_dune_query_result(
            db_path,
            query_id=query_id,
            allow_network=allow_network,
            api_key=api_key,
            client=client,
            params=params,
        )
    except Exception as exc:
        reasons.append("optional_source_failed")
        health.append(_optional_failure("dune", "dune_query_result", exc))
        return 0
    health.append(_source_health_from_summary(summary.source, summary.feed, summary.records_written))
    return summary.records_written


def _optional_thegraph(
    *,
    db_path: Path,
    allow_network: bool,
    include: bool,
    subgraph_url: str | None,
    graph_query: str | None,
    variables: dict[str, Any] | None,
    client: Any | None,
    health: list[SourceHealthSummary],
    reasons: list[str],
) -> int:
    if not include:
        health.append(_not_configured("thegraph", "thegraph_query_result"))
        return 0
    if not _has_text(subgraph_url) or not _has_text(graph_query):
        health.append(_not_configured("thegraph", "thegraph_query_result", reason_code="missing_config"))
        return 0
    try:
        summary = ingest_thegraph_query_result(
            db_path,
            subgraph_url=subgraph_url,
            query=graph_query,
            allow_network=allow_network,
            client=client,
            variables=variables,
        )
    except Exception as exc:
        reasons.append("optional_source_failed")
        health.append(_optional_failure("thegraph", "thegraph_query_result", exc))
        return 0
    health.append(_source_health_from_summary(summary.source, summary.feed, summary.records_written))
    return summary.records_written


def _blocked_network_report(
    *,
    db_path: Path,
    memory_path: Path,
    report_out: Path,
    started_at: datetime,
    run_id: str,
    strategy_families: list[str],
    skipped_strategy_families: list[str],
    stopped_family_override_used: bool,
) -> EvidenceRunnerReport:
    decision_reason_codes = ["network_not_allowed"]
    if skipped_strategy_families:
        decision_reason_codes.append("stopped_family_skipped")
    if stopped_family_override_used:
        decision_reason_codes.append("stopped_family_override_used")
    return _report(
        run_id=run_id,
        started_at=started_at,
        db_path=db_path,
        memory_path=memory_path,
        strategy_families=strategy_families,
        skipped_strategy_families=skipped_strategy_families,
        steps=[
            EvidenceRunnerStep(
                name="network_gate",
                status="blocked",
                reason_code="network_not_allowed",
            )
        ],
        records_written=0,
        validation_evidence_written=0,
        paper_outcomes_written=0,
        memory_records_written=0,
        report_artifact=None,
        research_milestone=_empty_research_milestone(),
        source_health=[
            SourceHealthSummary(
                source="ccxt",
                feed="core",
                status="blocked",
                reason_code="network_not_allowed",
            ),
            _not_configured("dexscreener", "pairs"),
            _not_configured("defillama", "yield_pools"),
            _not_configured("dune", "dune_query_result"),
            _not_configured("thegraph", "thegraph_query_result"),
        ],
        decision_reason_codes=decision_reason_codes,
        stopped_family_override_used=stopped_family_override_used,
    )


def _report(
    *,
    run_id: str,
    started_at: datetime,
    db_path: Path,
    memory_path: Path,
    strategy_families: list[str],
    skipped_strategy_families: list[str] | None = None,
    steps: list[EvidenceRunnerStep],
    records_written: int,
    validation_evidence_written: int,
    paper_outcomes_written: int,
    memory_records_written: int,
    report_artifact: str | None,
    research_milestone: ResearchMilestone,
    source_health: list[SourceHealthSummary],
    decision_reason_codes: list[str],
    stopped_family_override_used: bool = False,
) -> EvidenceRunnerReport:
    return EvidenceRunnerReport(
        run_id=run_id,
        started_at=started_at,
        db_path=str(db_path),
        memory_path=str(memory_path),
        strategy_families=strategy_families,
        skipped_strategy_families=skipped_strategy_families or [],
        steps=steps,
        records_written=records_written,
        validation_evidence_written=validation_evidence_written,
        paper_outcomes_written=paper_outcomes_written,
        memory_records_written=memory_records_written,
        report_artifact=report_artifact,
        research_milestone=research_milestone,
        source_health=_source_health_report(source_health),
        decision_reason_codes=_dedupe(decision_reason_codes),
        stopped_family_override_used=stopped_family_override_used,
    )


def _normalize_strategy_families(strategy_families: Sequence[str]) -> list[str]:
    normalized = [family.strip() for family in strategy_families if family.strip()]
    return normalized or list(DEFAULT_STRATEGY_FAMILIES)


def _source_health_from_summary(
    source: str,
    feed: str,
    records_written: int,
) -> SourceHealthSummary:
    return SourceHealthSummary(
        source=source,
        feed=feed,
        status="success",
        records_written=records_written,
    )


def _not_configured(
    source: str,
    feed: str,
    *,
    reason_code: str = "not_configured",
) -> SourceHealthSummary:
    return SourceHealthSummary(
        source=source,
        feed=feed,
        status="skipped",
        reason_code=reason_code,
    )


def _optional_failure(source: str, feed: str, exc: Exception) -> SourceHealthSummary:
    return SourceHealthSummary(
        source=source,
        feed=feed,
        status="failure",
        reason_code="optional_source_failed",
        failure=_redact_failure(str(exc)),
    )


def _redact_failure(message: str) -> str:
    return _URL_PATTERN.sub("[REDACTED_URL]", message)


def _validation_parameter_kwargs(
    *,
    registry: Any,
    strategy_family: str,
    symbol: str,
    funding_symbol: str,
    timeframe: str,
) -> dict[str, str]:
    if strategy_family not in registry.list_families():
        return {}
    spec = registry.get(strategy_family)
    required_types = set(spec.required_record_types)
    if {"market_candle", "funding_rate"}.issubset(required_types):
        return {
            "price_symbol": symbol,
            "funding_symbol": funding_symbol,
            "validation_timeframe": timeframe,
        }
    return {}


def _supports_paper_simulation(registry: Any, strategy_family: str) -> bool:
    if strategy_family not in registry.list_families():
        return False
    return bool(registry.get(strategy_family).supports_paper_simulation)


def _family_run_id(run_id: str, strategy_family: str, strategy_families: list[str]) -> str:
    if len(strategy_families) == 1:
        return run_id
    return f"{run_id}:{strategy_family}"


def _research_milestone(
    report: ResearchLoopReport,
    paper_outcomes: Sequence[PaperSimulationOutcome],
) -> ResearchMilestone:
    reflection_count = len(report.validation_summaries) + len(report.paper_evidence_packages)
    accept_reject_reason_count = sum(
        len(hypothesis.disconfirmation_tests) for hypothesis in report.hypotheses
    )
    accept_reject_reason_count += sum(
        len(summary.blocked_reasons) for summary in report.validation_summaries
    )
    accept_reject_reason_count += sum(
        len(outcome.failure_reasons) for outcome in paper_outcomes
    )
    return ResearchMilestone(
        loaded_records=report.loaded_records,
        signal_count=report.signal_count,
        anomaly_count=report.anomaly_count,
        hypothesis_count=report.hypothesis_count,
        reflection_count=reflection_count,
        accept_reject_reason_count=accept_reject_reason_count,
    )


def _empty_research_milestone() -> ResearchMilestone:
    return ResearchMilestone(
        loaded_records=0,
        signal_count=0,
        anomaly_count=0,
        hypothesis_count=0,
        reflection_count=0,
        accept_reject_reason_count=0,
    )


def _source_health_report(items: list[SourceHealthSummary]) -> SourceHealthReport:
    failures = [item for item in items if item.status == "failure"]
    return SourceHealthReport(
        items=items,
        optional_source_skipped=sum(
            1
            for item in items
            if item.source in OPTIONAL_SOURCES and item.status in {"skipped", "not_configured"}
        ),
        optional_source_failures=sum(1 for item in failures if item.reason_code == "optional_source_failed"),
        failures=failures,
    )


def _has_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _dedupe(values: Sequence[str]) -> list[str]:
    seen = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
