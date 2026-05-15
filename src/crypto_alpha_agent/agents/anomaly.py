from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.agents.scanner import ScannerSignal

AnomalyClassification = Literal[
    "statistical_outlier",
    "structural_discontinuity",
    "one_off_noise",
    "mirage",
]


class RankedAnomaly(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: ScannerSignal
    classification: AnomalyClassification
    score: float
    executable: bool
    reasons: list[str] = Field(default_factory=list)


class AnomalyDetector:
    def rank(self, signals: list[ScannerSignal]) -> list[RankedAnomaly]:
        ranked = [self.score(signal) for signal in signals]
        return sorted(ranked, key=lambda anomaly: (anomaly.executable, anomaly.score), reverse=True)

    def score(self, signal: ScannerSignal) -> RankedAnomaly:
        classification = self._classify(signal)
        executable = classification not in {"mirage", "one_off_noise"}
        score = self._base_score(signal)
        reasons = self._reasons(signal, classification)

        if classification == "structural_discontinuity":
            score += 20.0
        if classification == "one_off_noise":
            score -= 40.0
        if classification == "mirage":
            score = min(score, 0.0)
        if signal.weak_signal:
            score -= 25.0

        return RankedAnomaly(
            signal=signal,
            classification=classification,
            score=round(score, 4),
            executable=executable,
            reasons=reasons,
        )

    def _classify(self, signal: ScannerSignal) -> AnomalyClassification:
        if self._is_mirage(signal):
            return "mirage"
        if self._is_one_off_noise(signal):
            return "one_off_noise"
        if signal.structural_break:
            return "structural_discontinuity"
        return "statistical_outlier"

    @staticmethod
    def _is_mirage(signal: ScannerSignal) -> bool:
        capital_exceeds_depth = signal.capital_required_usd > 0 and (
            signal.liquidity_usd <= 0 or signal.capital_required_usd > signal.liquidity_usd
        )
        infrastructure_bound = signal.speed_dependency == "high" and signal.rpc_dependency == "high"
        return capital_exceeds_depth or infrastructure_bound

    @staticmethod
    def _is_one_off_noise(signal: ScannerSignal) -> bool:
        evidence_count = signal.evidence_count if signal.evidence_count is not None else len(signal.evidence)
        social_only = signal.category in {"social", "news"} or signal.weak_signal
        thin_evidence = evidence_count <= 1
        fleeting = signal.persistence_seconds < 120
        return social_only and (thin_evidence or fleeting)

    @staticmethod
    def _base_score(signal: ScannerSignal) -> float:
        z_component = abs(signal.z_score or 0.0) * 12.0
        deviation_component = abs(signal.deviation or 0.0) * 60.0
        persistence_component = min(signal.persistence_seconds / 300.0, 12.0)
        evidence_count = signal.evidence_count if signal.evidence_count is not None else len(signal.evidence)
        evidence_component = min(float(evidence_count) * 4.0, 16.0)
        liquidity_component = 0.0
        if signal.capital_required_usd > 0 and signal.liquidity_usd > 0:
            liquidity_component = min(signal.liquidity_usd / signal.capital_required_usd, 10.0)
        return z_component + deviation_component + persistence_component + evidence_component + liquidity_component

    @staticmethod
    def _reasons(signal: ScannerSignal, classification: AnomalyClassification) -> list[str]:
        reasons = [classification]
        if signal.z_score is not None:
            reasons.append(f"z_score={signal.z_score}")
        if signal.deviation is not None:
            reasons.append(f"deviation={signal.deviation}")
        if signal.persistence_seconds:
            reasons.append(f"persistence_seconds={signal.persistence_seconds}")
        if signal.weak_signal:
            reasons.append("weak_signal")
        if classification == "mirage":
            reasons.append("execution constraints exceed visible liquidity/timing")
        return reasons
