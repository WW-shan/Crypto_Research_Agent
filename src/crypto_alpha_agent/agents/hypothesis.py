from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.agents.anomaly import AnomalyClassification, AnomalyDetector, RankedAnomaly
from crypto_alpha_agent.agents.scanner import ScannerSignal, SignalCategory
from crypto_alpha_agent.config import ActionMode

Actionability = Literal["executable", "blocked"]


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    category: SignalCategory
    asset: str
    metric: str
    value: float
    signal_evidence: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    anomaly_classification: AnomalyClassification
    anomaly_score: float
    executable: bool
    persistence_seconds: float = Field(ge=0)
    anomaly_reasons: list[str] = Field(default_factory=list)
    venue: str | None = None
    chain: str | None = None
    protocol: str | None = None
    z_score: float | None = None
    deviation: float | None = None

    @classmethod
    def from_anomaly(cls, anomaly: RankedAnomaly) -> EvidenceBundle:
        signal = anomaly.signal
        return cls(
            source=signal.source,
            category=signal.category,
            asset=signal.asset,
            metric=signal.metric,
            value=signal.value,
            signal_evidence=list(signal.evidence),
            raw=dict(signal.raw),
            anomaly_classification=anomaly.classification,
            anomaly_score=anomaly.score,
            executable=anomaly.executable,
            persistence_seconds=signal.persistence_seconds,
            anomaly_reasons=list(anomaly.reasons),
            venue=signal.venue,
            chain=signal.chain,
            protocol=signal.protocol,
            z_score=signal.z_score,
            deviation=signal.deviation,
        )


class AlphaHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    category: SignalCategory
    asset: str
    what_changed: str = Field(min_length=1)
    why_it_might_be_edge: str = Field(min_length=1)
    evidence: list[EvidenceBundle] = Field(min_length=1)
    expected_persistence_seconds: float = Field(ge=0)
    disconfirmation_tests: list[str] = Field(min_length=1)
    action_mode: ActionMode = "research_only"
    actionability: Actionability
    venue: str | None = None
    chain: str | None = None
    protocol: str | None = None


HypothesisInput = RankedAnomaly | ScannerSignal | dict[str, Any]


class HypothesisGenerator:
    def __init__(self, anomaly_detector: AnomalyDetector | None = None) -> None:
        self._anomaly_detector = anomaly_detector or AnomalyDetector()

    def generate(self, candidates: Iterable[HypothesisInput]) -> list[AlphaHypothesis]:
        return [self._from_anomaly(self._normalize_candidate(candidate)) for candidate in candidates]

    def _normalize_candidate(self, candidate: HypothesisInput) -> RankedAnomaly:
        if isinstance(candidate, RankedAnomaly):
            return candidate
        if isinstance(candidate, ScannerSignal):
            return self._anomaly_detector.score(candidate)
        return self._anomaly_detector.score(ScannerSignal.model_validate(candidate))

    def _from_anomaly(self, anomaly: RankedAnomaly) -> AlphaHypothesis:
        signal = anomaly.signal
        evidence = EvidenceBundle.from_anomaly(anomaly)

        return AlphaHypothesis(
            source=signal.source,
            category=signal.category,
            asset=signal.asset,
            what_changed=self._what_changed(anomaly),
            why_it_might_be_edge=self._edge_rationale(anomaly),
            evidence=[evidence],
            expected_persistence_seconds=signal.persistence_seconds,
            disconfirmation_tests=self._disconfirmation_tests(anomaly),
            action_mode="research_only",
            actionability="executable" if anomaly.executable else "blocked",
            venue=signal.venue,
            chain=signal.chain,
            protocol=signal.protocol,
        )

    @staticmethod
    def _what_changed(anomaly: RankedAnomaly) -> str:
        signal = anomaly.signal
        location = signal.venue or signal.protocol or signal.chain or signal.source
        return (
            f"{signal.asset} {signal.metric} changed to {signal.value} on {location}; "
            f"classified as {anomaly.classification}."
        )

    @staticmethod
    def _edge_rationale(anomaly: RankedAnomaly) -> str:
        if anomaly.classification == "mirage":
            return (
                "The observation may reveal a market structure gap, but execution is blocked "
                "until depth, capital, and timing constraints become plausible."
            )
        if anomaly.classification == "structural_discontinuity":
            return (
                "A structural break can indicate a new flow regime before prices or routing "
                "fully adjust."
            )
        if anomaly.classification == "one_off_noise":
            return (
                "A weak or fleeting signal is research-only unless repeat observations show "
                "that the change persists."
            )
        return (
            "A statistical outlier can become an edge if the deviation is caused by repeatable "
            "flows rather than transient noise."
        )

    @staticmethod
    def _disconfirmation_tests(anomaly: RankedAnomaly) -> list[str]:
        signal = anomaly.signal
        tests = [
            (
                f"Recompute {signal.metric} from {signal.source}; invalidate if the anomaly "
                "falls back inside normal bounds."
            ),
            (
                f"Invalidate if the signal disappears before roughly "
                f"{signal.persistence_seconds:.0f} seconds."
            ),
        ]
        if anomaly.classification == "mirage":
            tests.append(
                "Invalidate actionability while required capital remains above visible "
                "liquidity or timing dependencies stay high."
            )
        elif signal.z_score is not None:
            tests.append(f"Invalidate if absolute z_score drops below 2.0 from {signal.z_score}.")
        elif signal.deviation is not None:
            tests.append(f"Invalidate if deviation mean-reverts from {signal.deviation}.")
        else:
            tests.append("Invalidate if independent evidence cannot reproduce the observation.")
        return tests
