from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crypto_alpha_agent.state import DependencyLevel

SignalCategory = Literal["cex", "dex", "chain", "social", "news"]


class ScannerSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    category: SignalCategory
    source: str
    asset: str
    metric: str
    value: float
    evidence: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    venue: str | None = None
    chain: str | None = None
    protocol: str | None = None
    z_score: float | None = None
    deviation: float | None = None
    persistence_seconds: float = Field(default=0.0, ge=0)
    liquidity_usd: float = Field(default=0.0, ge=0)
    capital_required_usd: float = Field(default=0.0, ge=0)
    speed_dependency: DependencyLevel = "none"
    rpc_dependency: DependencyLevel = "none"
    evidence_count: int | None = Field(default=None, ge=0)
    structural_break: bool = False
    weak_signal: bool = False


SignalProvider = Callable[[], Iterable[ScannerSignal | dict[str, Any]]]


class MarketScanner:
    def __init__(self, providers: Iterable[SignalProvider] | None = None) -> None:
        self._providers = list(providers or [])

    def scan(self) -> list[ScannerSignal]:
        signals: list[ScannerSignal] = []
        for provider in self._providers:
            for signal in provider():
                signals.append(self._normalize_signal(signal))
        return signals

    @staticmethod
    def _normalize_signal(signal: ScannerSignal | dict[str, Any]) -> ScannerSignal:
        if isinstance(signal, ScannerSignal):
            return signal
        return ScannerSignal.model_validate(signal)
