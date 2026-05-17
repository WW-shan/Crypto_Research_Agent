from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.agents.anomaly import AnomalyDetector, RankedAnomaly
from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis, HypothesisGenerator
from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.data.models import MarketCandle, RecordType, SourceRecord
from crypto_alpha_agent.data.quality import DataQualityReport, build_data_quality_report
from crypto_alpha_agent.data.scanner_bridge import records_to_scanner_signals
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome, ValidationEvidence
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger
from crypto_alpha_agent.strategy import StrategyValidationRequest, default_strategy_registry
from crypto_alpha_agent.strategy.models import StrategyValidationReport
from crypto_alpha_agent.validation.market_history import CandleBar
from crypto_alpha_agent.validation.momentum import MomentumValidationResult, validate_close_momentum


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    asset: str
    timeframe: str
    status: Literal["passed", "blocked"]
    trade_count: int
    funding_symbol: str | None = None
    validator_name: str | None = None
    baseline_only: bool = False
    gross_expectancy: float | None = None
    net_return: float | None = None
    max_drawdown: float | None = None
    fee_adjusted_expectancy: float | None = None
    slippage_adjusted_expectancy: float | None = None
    walk_forward_split_count: int | None = None
    walk_forward_pass_rate: float | None = None
    fees: float | None = None
    slippage: float | None = None
    blocked_reasons: list[str] = Field(default_factory=list)


class ResearchLoopReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    run_id: str
    db_path: str
    source_filter: str | None
    record_type_filter: str | None
    current_capital_usd: float
    loaded_records: int
    signal_count: int
    anomaly_count: int
    hypothesis_count: int
    weak_signal_count: int
    blocked_hypothesis_count: int
    uses_real_capital: bool
    live_order_routing: bool
    records: list[SourceRecord]
    signals: list[ScannerSignal]
    anomalies: list[RankedAnomaly]
    hypotheses: list[AlphaHypothesis]
    notes: list[str]
    validation_summaries: list[ValidationSummary] = Field(default_factory=list)
    paper_evidence_packages: list[PaperEvidencePackage] = Field(default_factory=list)
    data_quality_reports: list[DataQualityReport] = Field(default_factory=list)


def run_stored_research_loop(
    db_path: str | Path,
    *,
    current_capital_usd: float = 300.0,
    source: str | None = None,
    record_type: RecordType | None = None,
    limit: int | None = None,
    run_id: str | None = None,
    include_validation: bool = False,
    strategy_family: str | None = None,
    price_symbol: str | None = None,
    funding_symbol: str | None = None,
    validation_timeframe: str | None = None,
    threshold_abs: float = 0.0005,
    hold_bars: int = 1,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    min_trades: int = 3,
    include_paper_evidence: bool = False,
    data_quality_now: datetime | None = None,
) -> ResearchLoopReport:
    store = ResearchDataStore(db_path)
    records = store.load_records(record_type=record_type, source=source)
    if limit is not None:
        records = records[-limit:] if limit > 0 else []

    signals = records_to_scanner_signals(records, current_capital_usd=current_capital_usd)
    anomalies = AnomalyDetector().rank(signals)
    hypotheses = HypothesisGenerator().generate(anomalies)
    notes = _notes(records, signals)
    resolved_run_id = run_id or "stored-research-loop"
    validation_summaries = (
        _validation_summaries(
            records,
            db_path=db_path,
            current_capital_usd=current_capital_usd,
            strategy_family=strategy_family,
            price_symbol=price_symbol,
            funding_symbol=funding_symbol,
            validation_timeframe=validation_timeframe,
            threshold_abs=threshold_abs,
            hold_bars=hold_bars,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
            min_trades=min_trades,
        )
        if include_validation
        else []
    )
    if include_validation:
        validation_evidence = [
            _validation_evidence_from_summary(summary, run_id=resolved_run_id)
            for summary in validation_summaries
            if _should_persist_validation_evidence(summary)
        ]
        ValidationEvidenceLedger(db_path).replace_run_evidence(
            resolved_run_id,
            validation_evidence,
        )

    return ResearchLoopReport(
        run_id=resolved_run_id,
        db_path=str(db_path),
        source_filter=source,
        record_type_filter=record_type,
        current_capital_usd=current_capital_usd,
        loaded_records=len(records),
        signal_count=len(signals),
        anomaly_count=len(anomalies),
        hypothesis_count=len(hypotheses),
        weak_signal_count=sum(1 for signal in signals if signal.weak_signal),
        blocked_hypothesis_count=sum(
            1 for hypothesis in hypotheses if hypothesis.actionability == "blocked"
        ),
        uses_real_capital=False,
        live_order_routing=False,
        records=records,
        signals=signals,
        anomalies=anomalies,
        hypotheses=hypotheses,
        notes=notes,
        validation_summaries=validation_summaries,
        paper_evidence_packages=(
            _paper_evidence_packages(db_path) if include_paper_evidence else []
        ),
        data_quality_reports=[build_data_quality_report(records, now=data_quality_now)],
    )


def _notes(records: list[SourceRecord], signals: list[ScannerSignal]) -> list[str]:
    notes: list[str] = []
    if not records:
        notes.append("no_stored_records")
    elif not signals:
        notes.append("no_scanner_signals")
    if any(signal.weak_signal for signal in signals):
        notes.append("weak_signals_present")
    return notes


def _validation_summaries(
    records: list[SourceRecord],
    *,
    db_path: str | Path,
    current_capital_usd: float,
    strategy_family: str | None,
    price_symbol: str | None,
    funding_symbol: str | None,
    validation_timeframe: str | None,
    threshold_abs: float,
    hold_bars: int,
    fee_rate: float,
    slippage_rate: float,
    min_trades: int,
) -> list[ValidationSummary]:
    normalized_strategy_family = _nonblank_or_none(strategy_family)
    if normalized_strategy_family is not None:
        registry = default_strategy_registry(current_capital_usd=current_capital_usd)
        normalized_price_symbol = _nonblank_or_none(price_symbol)
        normalized_funding_symbol = _nonblank_or_none(funding_symbol)
        normalized_timeframe = _nonblank_or_none(validation_timeframe)
        if normalized_strategy_family not in registry.list_families():
            report = registry.validate(
                StrategyValidationRequest(
                    strategy_family=normalized_strategy_family,
                    records=[record.model_dump(mode="json") for record in records],
                    current_capital_usd=current_capital_usd,
                    parameters={},
                )
            )
            return [_summary_from_strategy_validation_report(report)]
        if (
            normalized_price_symbol is None
            or normalized_funding_symbol is None
            or normalized_timeframe is None
        ):
            return [
                _blocked_strategy_validation_summary(
                    strategy_family=normalized_strategy_family,
                    asset=normalized_price_symbol,
                    funding_symbol=normalized_funding_symbol,
                    timeframe=normalized_timeframe,
                    blocked_reasons=["missing_strategy_validation_parameters"],
                )
            ]

        try:
            report = registry.validate(
                StrategyValidationRequest(
                    strategy_family=normalized_strategy_family,
                    records=[record.model_dump(mode="json") for record in records],
                    current_capital_usd=current_capital_usd,
                    parameters={
                        "db_path": str(db_path),
                        "price_symbol": normalized_price_symbol,
                        "funding_symbol": normalized_funding_symbol,
                        "timeframe": normalized_timeframe,
                        "threshold_abs": threshold_abs,
                        "hold_bars": hold_bars,
                        "fee_rate": fee_rate,
                        "slippage_rate": slippage_rate,
                        "min_trades": min_trades,
                    },
                )
            )
        except ValueError:
            return [
                _blocked_strategy_validation_summary(
                    strategy_family=normalized_strategy_family,
                    asset=normalized_price_symbol,
                    funding_symbol=normalized_funding_symbol,
                    timeframe=normalized_timeframe,
                    blocked_reasons=["strategy_validation_error"],
                )
            ]
        return [_summary_from_strategy_validation_report(report)]

    groups: dict[tuple[str, str], list[CandleBar]] = defaultdict(list)
    for record in records:
        if record.record_type != "market_candle":
            continue
        candle = MarketCandle.model_validate_json(json.dumps(record.payload))
        groups[(candle.symbol, candle.timeframe)].append(_candle_bar(candle))

    summaries: list[ValidationSummary] = []
    for symbol, timeframe in sorted(groups):
        bars = sorted(
            groups[(symbol, timeframe)],
            key=lambda bar: (bar.timestamp, bar.source, bar.venue, bar.symbol),
        )
        if len(bars) < 2:
            continue

        summaries.append(
            _summary_from_momentum_result(
                validate_close_momentum(bars, lookback_bars=1, hold_bars=1, min_trades=2)
            )
        )
    return summaries


def _paper_evidence_packages(db_path: str | Path) -> list[PaperEvidencePackage]:
    outcomes = PaperOutcomeLedger(db_path).load_outcomes()
    return aggregate_paper_evidence(_paper_evidence_mapping(outcome) for outcome in outcomes)


def _paper_evidence_mapping(outcome: PaperSimulationOutcome) -> dict[str, object]:
    return {
        "strategy_family": outcome.strategy_family,
        "trade_id": outcome.outcome_id,
        "symbol": outcome.symbol,
        "status": outcome.status,
        "realized_net_pnl": outcome.net_pnl_usd,
        "max_drawdown_usd": outcome.max_drawdown_usd,
        "failure_reasons": list(outcome.failure_reasons),
    }


def _candle_bar(candle: MarketCandle) -> CandleBar:
    return CandleBar(
        source=candle.source,
        venue=candle.venue,
        symbol=candle.symbol,
        timestamp=candle.timestamp,
        timeframe=candle.timeframe,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def _summary_from_momentum_result(result: MomentumValidationResult) -> ValidationSummary:
    return ValidationSummary(
        strategy_family=result.strategy_family,
        asset=result.symbol,
        timeframe=result.timeframe,
        status="passed" if result.approved else "blocked",
        trade_count=result.trade_count,
        net_return=result.net_return,
        max_drawdown=result.max_drawdown,
        fee_adjusted_expectancy=result.fee_adjusted_expectancy,
        slippage_adjusted_expectancy=result.slippage_adjusted_expectancy,
        blocked_reasons=result.blocked_reasons,
        baseline_only=True,
        validator_name="close_momentum_baseline",
    )


def _summary_from_strategy_validation_report(
    report: StrategyValidationReport,
) -> ValidationSummary:
    metrics = report.metrics
    asset = _optional_string_metric(metrics, "symbol") or report.strategy_family
    timeframe = _optional_string_metric(metrics, "timeframe") or "unknown"
    return ValidationSummary(
        strategy_family=report.strategy_family,
        asset=asset,
        funding_symbol=_optional_string_metric(metrics, "funding_symbol"),
        timeframe=timeframe,
        status="passed" if report.approved else "blocked",
        trade_count=_int_metric(metrics, "trade_count"),
        validator_name=report.validator_name,
        gross_expectancy=_float_metric(metrics, "gross_expectancy"),
        net_return=_float_metric(metrics, "net_return"),
        max_drawdown=_float_metric(metrics, "max_drawdown"),
        fee_adjusted_expectancy=_float_metric(metrics, "fee_adjusted_expectancy"),
        slippage_adjusted_expectancy=_float_metric(metrics, "slippage_adjusted_expectancy"),
        walk_forward_split_count=_int_metric_or_none(metrics, "walk_forward_split_count"),
        walk_forward_pass_rate=_float_metric(metrics, "walk_forward_pass_rate"),
        fees=_float_metric(metrics, "fee_rate"),
        slippage=_float_metric(metrics, "slippage_rate"),
        blocked_reasons=list(report.blocked_reasons),
    )


def _validation_evidence_from_summary(
    summary: ValidationSummary,
    *,
    run_id: str,
) -> ValidationEvidence:
    return ValidationEvidence(
        run_id=run_id,
        strategy_family=summary.strategy_family,
        symbol=summary.asset,
        timeframe=summary.timeframe,
        validator_name=summary.validator_name or "strategy_registry",
        trade_count=summary.trade_count,
        net_return=summary.net_return or 0.0,
        gross_expectancy=summary.gross_expectancy or 0.0,
        fee_adjusted_expectancy=summary.fee_adjusted_expectancy or 0.0,
        slippage_adjusted_expectancy=summary.slippage_adjusted_expectancy or 0.0,
        max_drawdown=summary.max_drawdown or 0.0,
        walk_forward_split_count=summary.walk_forward_split_count or 0,
        walk_forward_pass_rate=summary.walk_forward_pass_rate or 0.0,
        approved=summary.status == "passed",
        blocked_reasons=summary.blocked_reasons,
    )


def _should_persist_validation_evidence(summary: ValidationSummary) -> bool:
    return (
        not summary.baseline_only
        and summary.validator_name != "unknown"
        and "unknown_strategy_family" not in summary.blocked_reasons
    )


def _optional_string_metric(metrics: dict[str, object], key: str) -> str | None:
    value = metrics.get(key)
    if value is None:
        return None
    return str(value)


def _int_metric(metrics: dict[str, object], key: str) -> int:
    value = metrics.get(key)
    return int(value) if value is not None else 0


def _int_metric_or_none(metrics: dict[str, object], key: str) -> int | None:
    value = metrics.get(key)
    return int(value) if value is not None else None


def _float_metric(metrics: dict[str, object], key: str) -> float | None:
    value = metrics.get(key)
    return float(value) if value is not None else None


def _nonblank_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _blocked_strategy_validation_summary(
    *,
    strategy_family: str,
    asset: str | None,
    funding_symbol: str | None,
    timeframe: str | None,
    blocked_reasons: list[str],
) -> ValidationSummary:
    return ValidationSummary(
        strategy_family=strategy_family,
        asset=asset or strategy_family,
        funding_symbol=funding_symbol,
        timeframe=timeframe or "unknown",
        status="blocked",
        trade_count=0,
        validator_name="strategy_registry",
        blocked_reasons=blocked_reasons,
    )
