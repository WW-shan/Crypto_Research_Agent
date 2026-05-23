from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.data.quality import build_data_quality_report
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.memory.store import MemoryRecord, MemoryStore
from crypto_alpha_agent.orchestrator import DETERMINISTIC_EVENT_TIME_ISO
from crypto_alpha_agent.strategy import default_strategy_registry

PAPER_SAMPLE_TARGET = 30
OWNER_REVIEW_WALK_FORWARD_MIN = 0.70
PORTFOLIO_NOTIONAL_CAP_USD = 25.0
_DEGRADED_MARKERS = {
    "degraded",
    "degraded_expectancy",
    "fee_killed_edge",
    "slippage_killed_edge",
    "insufficient_evidence_progress",
    "drawdown_breach",
    "too_many_blocked_runs",
    "negative_expectancy",
}

GovernanceAction = Literal[
    "keep_collecting",
    "stop",
    "redesign_validator",
    "add_data",
    "owner_decision_review",
]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFiniteFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
RatioFloat = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class _GovernanceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        validate_assignment=True,
        frozen=True,
    )


class FamilyScoreboardRow(_GovernanceModel):
    strategy_family: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    net_pnl_usd: FiniteFloat
    cost_adjusted_expectancy_usd: FiniteFloat
    max_drawdown_usd: NonNegativeFiniteFloat
    hit_rate: RatioFloat
    failure_rate: RatioFloat
    source_health_quality: RatioFloat
    stale_signal_rate: RatioFloat
    walk_forward_stability: RatioFloat
    governance_action: GovernanceAction
    reason_codes: list[str] = Field(default_factory=list)
    validation_evidence_count: int = Field(ge=0)
    paper_outcome_count: int = Field(ge=0)


class ProfitReviewRow(_GovernanceModel):
    strategy_family: str = Field(min_length=1)
    is_improving: bool
    worth_more_data: bool
    should_stop: bool
    near_owner_decision_point: bool
    governance_action: GovernanceAction
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class StoppedFamilyLedgerRow(_GovernanceModel):
    strategy_family: str = Field(min_length=1)
    stopped_at: str = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    revival_conditions: list[str] = Field(default_factory=list)


class PaperOnlyPortfolioSelection(_GovernanceModel):
    rank: int = Field(ge=1)
    strategy_family: str = Field(min_length=1)
    paper_weight: RatioFloat
    score: FiniteFloat
    max_paper_notional_usd: NonNegativeFiniteFloat
    selection_reason_codes: list[str] = Field(default_factory=list)
    exclusion_reason_codes: list[str] = Field(default_factory=list)


class MonthlyOwnerReview(_GovernanceModel):
    best_paper_strategy: str | None = None
    best_strategy_net_pnl_usd: FiniteFloat
    do_nothing_pnl_usd: FiniteFloat
    total_fees_usd: NonNegativeFiniteFloat
    total_slippage_usd: NonNegativeFiniteFloat
    opportunity_cost_usd: NonNegativeFiniteFloat
    owner_capital_constraint_usd: NonNegativeFiniteFloat
    decision: GovernanceAction
    reason_codes: list[str] = Field(default_factory=list)
    comparison_notes: list[str] = Field(default_factory=list)


class ProfitGovernanceReport(_GovernanceModel):
    generated_at: str = Field(min_length=1)
    current_capital_usd: NonNegativeFiniteFloat
    family_scoreboard: list[FamilyScoreboardRow] = Field(default_factory=list)
    profit_reviews: list[ProfitReviewRow] = Field(default_factory=list)
    stopped_family_ledger: list[StoppedFamilyLedgerRow] = Field(default_factory=list)
    paper_only_portfolio: list[PaperOnlyPortfolioSelection] = Field(default_factory=list)
    monthly_owner_review: MonthlyOwnerReview
    reason_codes: list[str] = Field(default_factory=list)
    uses_real_capital: Literal[False] = False
    live_order_routing: Literal[False] = False


def build_profit_governance_report(
    *,
    db_path: str | Path,
    memory_path: str | Path,
    current_capital_usd: float = 300.0,
) -> ProfitGovernanceReport:
    validation_evidence = ValidationEvidenceLedger(db_path).load_evidence()
    paper_outcomes = PaperOutcomeLedger(db_path).load_outcomes()
    memory_records = MemoryStore(memory_path).list_records()
    source_records = ResearchDataStore(db_path).load_records()
    data_quality = build_data_quality_report(source_records)
    source_health_quality = _source_health_quality(data_quality.source_health)

    packages = aggregate_paper_evidence(_paper_evidence_mapping(outcome) for outcome in paper_outcomes)
    packages_by_family = {package.strategy_family: package for package in packages}
    validation_by_family = _group_by_family(validation_evidence)
    outcomes_by_family = _group_by_family(paper_outcomes)
    memory_by_family = _group_memory_by_family(memory_records)
    families = sorted(
        {
            *validation_by_family,
            *outcomes_by_family,
            *memory_by_family,
            *packages_by_family,
            *default_strategy_registry(current_capital_usd=current_capital_usd).list_families(),
        }
    )

    scoreboard = [
        _scoreboard_row(
            family,
            package=packages_by_family.get(family),
            validation=validation_by_family.get(family, []),
            outcomes=outcomes_by_family.get(family, []),
            memory_records=memory_by_family.get(family, []),
            source_health_quality=source_health_quality,
        )
        for family in families
    ]
    profit_reviews = [
        _profit_review_row(
            row,
            validation=validation_by_family.get(row.strategy_family, []),
            outcomes=outcomes_by_family.get(row.strategy_family, []),
            memory_records=memory_by_family.get(row.strategy_family, []),
        )
        for row in scoreboard
    ]
    stopped_ledger = _stopped_family_ledger(
        scoreboard,
        validation_by_family=validation_by_family,
        outcomes_by_family=outcomes_by_family,
        memory_by_family=memory_by_family,
    )
    portfolio = _paper_only_portfolio(scoreboard, current_capital_usd=current_capital_usd)
    monthly_review = _monthly_owner_review(
        scoreboard,
        portfolio=portfolio,
        outcomes=paper_outcomes,
        current_capital_usd=current_capital_usd,
    )

    return ProfitGovernanceReport(
        generated_at=DETERMINISTIC_EVENT_TIME_ISO,
        current_capital_usd=_clean_float(current_capital_usd),
        family_scoreboard=scoreboard,
        profit_reviews=profit_reviews,
        stopped_family_ledger=stopped_ledger,
        paper_only_portfolio=portfolio,
        monthly_owner_review=monthly_review,
        reason_codes=_report_reason_codes(scoreboard, stopped_ledger, portfolio),
    )


def _scoreboard_row(
    family: str,
    *,
    package: PaperEvidencePackage | None,
    validation: list[ValidationEvidence],
    outcomes: list[PaperSimulationOutcome],
    memory_records: list[MemoryRecord],
    source_health_quality: float,
) -> FamilyScoreboardRow:
    sample_size = 0 if package is None else package.sample_size
    failed_count = 0 if package is None else package.failed_count
    net_pnl = 0.0 if package is None else package.net_pnl_usd
    expectancy = _ratio(net_pnl, sample_size)
    walk_forward = _walk_forward_stability(validation)
    hit_rate = 0.0 if package is None else package.hit_rate
    failure_rate = _ratio(failed_count, sample_size)
    stale_signal_rate = _ratio(0 if package is None else package.stale_signal_count, sample_size)
    max_drawdown_usd = 0.0 if package is None else package.max_drawdown_usd
    governance_action, reason_codes = _governance_action(
        sample_size=sample_size,
        cost_adjusted_expectancy_usd=expectancy,
        net_pnl_usd=net_pnl,
        failure_rate=failure_rate,
        source_health_quality=source_health_quality,
        walk_forward_stability=walk_forward,
        validation=validation,
        outcomes=outcomes,
        memory_records=memory_records,
    )
    return FamilyScoreboardRow(
        strategy_family=family,
        sample_size=sample_size,
        net_pnl_usd=_clean_float(net_pnl),
        cost_adjusted_expectancy_usd=_clean_float(expectancy),
        max_drawdown_usd=_clean_float(max_drawdown_usd),
        hit_rate=_clean_float(hit_rate),
        failure_rate=_clean_float(failure_rate),
        source_health_quality=_clean_float(source_health_quality),
        stale_signal_rate=_clean_float(stale_signal_rate),
        walk_forward_stability=_clean_float(walk_forward),
        governance_action=governance_action,
        reason_codes=reason_codes,
        validation_evidence_count=len(validation),
        paper_outcome_count=len(outcomes),
    )


def _profit_review_row(
    row: FamilyScoreboardRow,
    *,
    validation: list[ValidationEvidence],
    outcomes: list[PaperSimulationOutcome],
    memory_records: list[MemoryRecord],
) -> ProfitReviewRow:
    should_stop = row.governance_action == "stop"
    is_improving = (
        not should_stop
        and row.cost_adjusted_expectancy_usd > 0.0
        and row.hit_rate >= row.failure_rate
        and row.walk_forward_stability >= 0.5
    )
    worth_more_data = (
        not should_stop
        and (
            row.sample_size < PAPER_SAMPLE_TARGET * 2
            or row.source_health_quality < 1.0
            or row.walk_forward_stability < 1.0
        )
    )
    return ProfitReviewRow(
        strategy_family=row.strategy_family,
        is_improving=is_improving,
        worth_more_data=worth_more_data,
        should_stop=should_stop,
        near_owner_decision_point=row.governance_action == "owner_decision_review",
        governance_action=row.governance_action,
        reason_codes=list(row.reason_codes),
        evidence_refs=_evidence_refs(validation=validation, outcomes=outcomes, memory_records=memory_records),
    )


def _stopped_family_ledger(
    scoreboard: list[FamilyScoreboardRow],
    *,
    validation_by_family: Mapping[str, list[ValidationEvidence]],
    outcomes_by_family: Mapping[str, list[PaperSimulationOutcome]],
    memory_by_family: Mapping[str, list[MemoryRecord]],
) -> list[StoppedFamilyLedgerRow]:
    ledger_rows: list[StoppedFamilyLedgerRow] = []
    for family, records in sorted(memory_by_family.items()):
        stopped_records = [record for record in records if _has_degraded_marker(record)]
        if not stopped_records:
            continue
        reason_codes = _dedupe(
            reason
            for record in stopped_records
            for reason in record.rejected_reasons
        ) or ["degraded"]
        stopped_at = min(
            (record.created_at or record.updated_at or DETERMINISTIC_EVENT_TIME_ISO)
            for record in stopped_records
        )
        ledger_rows.append(
            StoppedFamilyLedgerRow(
                strategy_family=family,
                stopped_at=stopped_at,
                reason_codes=reason_codes,
                evidence_refs=[f"memory:{record.record_id}" for record in stopped_records],
                revival_conditions=[
                    "fresh_validation_evidence",
                    "positive_cost_adjusted_expectancy",
                    "operator_review_required",
                ],
            )
        )
    ledger_families = {row.strategy_family for row in ledger_rows}
    for row in sorted(
        (
            item
            for item in scoreboard
            if item.governance_action == "stop" and item.strategy_family not in ledger_families
        ),
        key=lambda item: item.strategy_family,
    ):
        family = row.strategy_family
        outcomes = outcomes_by_family.get(family, [])
        validation = validation_by_family.get(family, [])
        memory_records = memory_by_family.get(family, [])
        ledger_rows.append(
            StoppedFamilyLedgerRow(
                strategy_family=family,
                stopped_at=_stopped_at_from_evidence(outcomes),
                reason_codes=list(row.reason_codes),
                evidence_refs=_evidence_refs(
                    validation=validation,
                    outcomes=outcomes,
                    memory_records=memory_records,
                ),
                revival_conditions=[
                    "fresh_validation_evidence",
                    "positive_cost_adjusted_expectancy",
                    "operator_review_required",
                ],
            )
        )
    return ledger_rows


def _paper_only_portfolio(
    rows: list[FamilyScoreboardRow],
    *,
    current_capital_usd: float,
) -> list[PaperOnlyPortfolioSelection]:
    candidates = [
        row
        for row in rows
        if row.governance_action in {"keep_collecting", "owner_decision_review"}
        and row.cost_adjusted_expectancy_usd > 0.0
        and row.source_health_quality > 0.0
    ]
    candidates.sort(
        key=lambda row: (
            _portfolio_score(row),
            row.walk_forward_stability,
            row.net_pnl_usd,
            row.strategy_family,
        ),
        reverse=True,
    )
    if not candidates:
        return []

    total_notional_cap = _clean_float(min(PORTFOLIO_NOTIONAL_CAP_USD, max(current_capital_usd, 0.0)))
    max_notional = _clean_float(total_notional_cap / len(candidates))
    weight = _clean_float(1.0 / len(candidates))
    return [
        PaperOnlyPortfolioSelection(
            rank=index,
            strategy_family=row.strategy_family,
            paper_weight=weight,
            score=_clean_float(_portfolio_score(row)),
            max_paper_notional_usd=max_notional,
            selection_reason_codes=_selection_reason_codes(row),
            exclusion_reason_codes=[],
        )
        for index, row in enumerate(candidates, start=1)
    ]


def _monthly_owner_review(
    rows: list[FamilyScoreboardRow],
    *,
    portfolio: list[PaperOnlyPortfolioSelection],
    outcomes: list[PaperSimulationOutcome],
    current_capital_usd: float,
) -> MonthlyOwnerReview:
    rows_by_family = {row.strategy_family: row for row in rows}
    best_strategy = portfolio[0].strategy_family if portfolio else None
    best_row = None if best_strategy is None else rows_by_family.get(best_strategy)
    best_pnl = 0.0 if best_row is None else best_row.net_pnl_usd
    total_fees = sum(outcome.fees_usd for outcome in outcomes)
    total_slippage = sum(outcome.slippage_usd for outcome in outcomes)
    do_nothing = 0.0
    opportunity_cost = max(0.0, do_nothing - best_pnl)

    if best_row is not None:
        decision: GovernanceAction = best_row.governance_action
        reason_codes = _dedupe(["best_paper_strategy", *best_row.reason_codes])
    elif rows and all(row.governance_action == "stop" for row in rows):
        decision = "stop"
        reason_codes = ["all_families_stopped"]
    else:
        decision = "add_data"
        reason_codes = ["no_paper_portfolio_candidate"]

    return MonthlyOwnerReview(
        best_paper_strategy=best_strategy,
        best_strategy_net_pnl_usd=_clean_float(best_pnl),
        do_nothing_pnl_usd=_clean_float(do_nothing),
        total_fees_usd=_clean_float(total_fees),
        total_slippage_usd=_clean_float(total_slippage),
        opportunity_cost_usd=_clean_float(opportunity_cost),
        owner_capital_constraint_usd=_clean_float(current_capital_usd),
        decision=decision,
        reason_codes=reason_codes,
        comparison_notes=[
            f"Best paper strategy net PnL USD: {_clean_float(best_pnl):g}",
            f"Doing nothing PnL USD: {_clean_float(do_nothing):g}",
            f"Fees USD: {_clean_float(total_fees):g}",
            f"Slippage USD: {_clean_float(total_slippage):g}",
            f"Owner capital constraint USD: {_clean_float(current_capital_usd):g}",
        ],
    )


def _governance_action(
    *,
    sample_size: int,
    cost_adjusted_expectancy_usd: float,
    net_pnl_usd: float,
    failure_rate: float,
    source_health_quality: float,
    walk_forward_stability: float,
    validation: list[ValidationEvidence],
    outcomes: list[PaperSimulationOutcome],
    memory_records: list[MemoryRecord],
) -> tuple[GovernanceAction, list[str]]:
    reasons = _base_reason_codes(
        sample_size=sample_size,
        cost_adjusted_expectancy_usd=cost_adjusted_expectancy_usd,
        source_health_quality=source_health_quality,
        walk_forward_stability=walk_forward_stability,
        validation=validation,
    )
    if any(_has_degraded_marker(record) for record in memory_records):
        return "stop", _dedupe(["degraded_family", *_degraded_reason_codes(memory_records)])
    if sample_size > 0 and (cost_adjusted_expectancy_usd <= 0.0 or net_pnl_usd <= 0.0):
        return "stop", _dedupe(["negative_cost_adjusted_expectancy", *reasons])
    if not validation or sample_size == 0:
        return "add_data", _dedupe(["missing_evidence", *reasons])
    if source_health_quality == 0.0:
        return "add_data", _dedupe(["source_health_missing", *reasons])
    if (
        failure_rate >= 0.5
        or any(item.blocked_reasons for item in validation)
        or _blocked_outcome_count(outcomes) >= 3
        or walk_forward_stability < 0.5
    ):
        return "redesign_validator", _dedupe(["validator_not_stable", *reasons])
    if (
        sample_size >= PAPER_SAMPLE_TARGET
        and cost_adjusted_expectancy_usd > 0.0
        and walk_forward_stability >= OWNER_REVIEW_WALK_FORWARD_MIN
    ):
        return "owner_decision_review", _dedupe(reasons)
    return "keep_collecting", _dedupe(reasons)


def _base_reason_codes(
    *,
    sample_size: int,
    cost_adjusted_expectancy_usd: float,
    source_health_quality: float,
    walk_forward_stability: float,
    validation: list[ValidationEvidence],
) -> list[str]:
    reasons: list[str] = []
    if cost_adjusted_expectancy_usd > 0.0:
        reasons.append("positive_cost_adjusted_expectancy")
    else:
        reasons.append("non_positive_cost_adjusted_expectancy")
    if sample_size >= PAPER_SAMPLE_TARGET:
        reasons.append("sample_target_met")
    else:
        reasons.append("sample_below_target")
    if not validation:
        reasons.append("missing_validation_evidence")
    if walk_forward_stability >= OWNER_REVIEW_WALK_FORWARD_MIN:
        reasons.append("walk_forward_supported")
    elif validation:
        reasons.append("weak_walk_forward")
    if source_health_quality >= 1.0:
        reasons.append("source_health_clean")
    elif source_health_quality > 0.0:
        reasons.append("source_health_partial")
    else:
        reasons.append("source_health_missing")
    return reasons


def _selection_reason_codes(row: FamilyScoreboardRow) -> list[str]:
    reasons: list[str] = []
    if row.cost_adjusted_expectancy_usd > 0.0:
        reasons.append("positive_cost_adjusted_expectancy")
    if row.walk_forward_stability >= OWNER_REVIEW_WALK_FORWARD_MIN:
        reasons.append("walk_forward_supported")
    if row.source_health_quality >= 1.0:
        reasons.append("source_health_clean")
    elif row.source_health_quality > 0.0:
        reasons.append("source_health_partial")
    else:
        reasons.append("source_health_missing")
    return reasons


def _report_reason_codes(
    scoreboard: list[FamilyScoreboardRow],
    stopped_ledger: list[StoppedFamilyLedgerRow],
    portfolio: list[PaperOnlyPortfolioSelection],
) -> list[str]:
    codes = ["profit_governance"]
    if scoreboard:
        codes.append("family_scoreboard")
    if stopped_ledger:
        codes.append("stopped_family_ledger")
    if portfolio:
        codes.append("paper_only_portfolio")
    codes.extend(row.governance_action for row in scoreboard)
    return _dedupe(codes)


def _paper_evidence_mapping(outcome: PaperSimulationOutcome) -> dict[str, Any]:
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


def _source_health_quality(source_health: Iterable[Any]) -> float:
    snapshots = list(source_health)
    if not snapshots:
        return 0.0
    return _ratio(sum(1 for snapshot in snapshots if snapshot.success), len(snapshots))


def _walk_forward_stability(validation: list[ValidationEvidence]) -> float:
    if not validation:
        return 0.0
    return sum(item.walk_forward_pass_rate for item in validation) / len(validation)


def _portfolio_score(row: FamilyScoreboardRow) -> float:
    return (
        row.net_pnl_usd
        + (row.walk_forward_stability * 10.0)
        + (row.hit_rate * 5.0)
        - (row.failure_rate * 10.0)
        - row.max_drawdown_usd
    )


def _group_by_family(items: Iterable[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for item in items:
        family = _item_strategy_family(item)
        if family is not None:
            grouped[family].append(item)
    return dict(grouped)


def _stopped_at_from_evidence(outcomes: list[PaperSimulationOutcome]) -> str:
    if not outcomes:
        return DETERMINISTIC_EVENT_TIME_ISO
    return min(outcome.observed_at for outcome in outcomes).isoformat()


def _group_memory_by_family(records: Iterable[MemoryRecord]) -> dict[str, list[MemoryRecord]]:
    grouped: dict[str, list[MemoryRecord]] = defaultdict(list)
    for record in records:
        family = _record_strategy_family(record)
        if family is not None:
            grouped[family].append(record)
    return dict(grouped)


def _item_strategy_family(item: Any) -> str | None:
    value = getattr(item, "strategy_family", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(item, Mapping):
        value = item.get("strategy_family")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _record_strategy_family(record: MemoryRecord) -> str | None:
    for payload in (
        record.opportunity,
        record.hypothesis,
        record.score,
        record.backtest_artifacts,
        record.paper_trade_outcome,
    ):
        if isinstance(payload, dict):
            family = payload.get("strategy_family")
            if isinstance(family, str) and family.strip():
                return family.strip()
    return None


def _has_degraded_marker(record: MemoryRecord) -> bool:
    tokens = {
        str(token).strip().lower()
        for token in [*record.tags, *record.rejected_reasons]
        if str(token).strip()
    }
    return bool(tokens.intersection(_DEGRADED_MARKERS))


def _degraded_reason_codes(records: list[MemoryRecord]) -> list[str]:
    return _dedupe(
        reason
        for record in records
        if _has_degraded_marker(record)
        for reason in record.rejected_reasons
    )


def _blocked_outcome_count(outcomes: list[PaperSimulationOutcome]) -> int:
    return sum(1 for outcome in outcomes if outcome.status.strip().lower() == "blocked")


def _evidence_refs(
    *,
    validation: list[ValidationEvidence],
    outcomes: list[PaperSimulationOutcome],
    memory_records: list[MemoryRecord],
) -> list[str]:
    return _dedupe(
        [
            *[f"validation:{item.evidence_id}" for item in validation],
            *[f"paper:{outcome.outcome_id}" for outcome in outcomes],
            *[f"memory:{record.record_id}" for record in memory_records],
        ]
    )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _clean_float(value: float) -> float:
    return float(round(value, 10))


def _dedupe(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped
