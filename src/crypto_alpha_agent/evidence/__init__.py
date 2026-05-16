"""Evidence aggregation helpers."""

from crypto_alpha_agent.evidence.live_readiness import (
    TinyLiveReadinessArtifact,
    TinyLiveReadinessChecklistItem,
    generate_tiny_live_readiness_artifact,
)
from crypto_alpha_agent.evidence.models import (
    ExperimentRun,
    PaperSimulationOutcome,
    StrategyCandidate,
    ValidationEvidence,
)
from crypto_alpha_agent.evidence.paper import (
    PaperEvidenceInput,
    PaperEvidencePackage,
    aggregate_paper_evidence,
)

__all__ = [
    "ExperimentRun",
    "PaperEvidenceInput",
    "PaperEvidencePackage",
    "PaperSimulationOutcome",
    "StrategyCandidate",
    "TinyLiveReadinessArtifact",
    "TinyLiveReadinessChecklistItem",
    "ValidationEvidence",
    "aggregate_paper_evidence",
    "generate_tiny_live_readiness_artifact",
]
