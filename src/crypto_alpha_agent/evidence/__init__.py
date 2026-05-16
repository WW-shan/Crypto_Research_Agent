"""Evidence aggregation helpers."""

from crypto_alpha_agent.evidence.live_readiness import (
    TinyLiveReadinessArtifact,
    TinyLiveReadinessChecklistItem,
    generate_tiny_live_readiness_artifact,
)
from crypto_alpha_agent.evidence.paper import (
    PaperEvidenceInput,
    PaperEvidencePackage,
    aggregate_paper_evidence,
)

__all__ = [
    "PaperEvidenceInput",
    "PaperEvidencePackage",
    "TinyLiveReadinessArtifact",
    "TinyLiveReadinessChecklistItem",
    "aggregate_paper_evidence",
    "generate_tiny_live_readiness_artifact",
]
