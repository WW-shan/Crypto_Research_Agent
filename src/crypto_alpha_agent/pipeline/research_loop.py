from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crypto_alpha_agent.agents.anomaly import AnomalyDetector, RankedAnomaly
from crypto_alpha_agent.agents.hypothesis import AlphaHypothesis, HypothesisGenerator
from crypto_alpha_agent.agents.scanner import ScannerSignal
from crypto_alpha_agent.data.models import RecordType, SourceRecord
from crypto_alpha_agent.data.scanner_bridge import records_to_scanner_signals
from crypto_alpha_agent.data.store import ResearchDataStore


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


def run_stored_research_loop(
    db_path: str | Path,
    *,
    current_capital_usd: float = 300.0,
    source: str | None = None,
    record_type: RecordType | None = None,
    limit: int | None = None,
    run_id: str | None = None,
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
