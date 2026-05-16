from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.agents.anomaly import AnomalyDetector, RankedAnomaly
from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis, HypothesisGenerator
from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.data.models import MarketCandle, RecordType, SourceRecord
from crypto_alpha_agent.data.scanner_bridge import records_to_scanner_signals
from crypto_alpha_agent.data.store import ResearchDataStore
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
from crypto_alpha_agent.evidence.models import PaperSimulationOutcome
from crypto_alpha_agent.evidence.paper import PaperEvidencePackage, aggregate_paper_evidence
from crypto_alpha_agent.validation.market_history import CandleBar
from crypto_alpha_agent.validation.momentum import MomentumValidationResult, validate_close_momentum


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    strategy_family: str
    asset: str
    timeframe: str
    status: Literal["passed", "blocked"]
    trade_count: int
    net_return: float | None = None
    max_drawdown: float | None = None
    fee_adjusted_expectancy: float | None = None
    slippage_adjusted_expectancy: float | None = None
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


def run_stored_research_loop(
    db_path: str | Path,
    *,
    current_capital_usd: float = 300.0,
    source: str | None = None,
    record_type: RecordType | None = None,
    limit: int | None = None,
    run_id: str | None = None,
    include_validation: bool = False,
    include_paper_evidence: bool = False,
) -> ResearchLoopReport:
    store = ResearchDataStore(db_path)
    records = store.load_records(record_type=record_type, source=source)
    if limit is not None:
        records = records[-limit:] if limit > 0 else []

    signals = records_to_scanner_signals(records, current_capital_usd=current_capital_usd)
    anomalies = AnomalyDetector().rank(signals)
    hypotheses = HypothesisGenerator().generate(anomalies)
    notes = _notes(records, signals)

    return ResearchLoopReport(
        run_id=run_id or "stored-research-loop",
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
        validation_summaries=_validation_summaries(records) if include_validation else [],
        paper_evidence_packages=(
            _paper_evidence_packages(db_path) if include_paper_evidence else []
        ),
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


def _validation_summaries(records: list[SourceRecord]) -> list[ValidationSummary]:
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
    )
