"""Evidence aggregation helpers."""

from crypto_alpha_agent.evidence.live_readiness import (
    TinyLiveReadinessArtifact,
    TinyLiveReadinessChecklistItem,
    generate_tiny_live_readiness_artifact,
)
from crypto_alpha_agent.evidence.ledger import PaperOutcomeLedger
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
from crypto_alpha_agent.evidence.validation_ledger import ValidationEvidenceLedger

__all__ = [
    "ExperimentRun",
    "PaperEvidenceInput",
    "PaperEvidencePackage",
    "PaperOutcomeLedger",
    "PaperSimulationOutcome",
    "StrategyCandidate",
    "TinyLiveReadinessArtifact",
    "TinyLiveReadinessChecklistItem",
    "ValidationEvidence",
    "ValidationEvidenceLedger",
    "aggregate_paper_evidence",
    "generate_tiny_live_readiness_artifact",
]
