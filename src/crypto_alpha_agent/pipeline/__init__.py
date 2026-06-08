from __future__ import annotations

from typing import Any

__all__ = ["ResearchLoopReport", "persist_research_loop_memory", "run_stored_research_loop"]


def __getattr__(name: str) -> Any:
    if name in {"ResearchLoopReport", "run_stored_research_loop"}:
        from crypto_alpha_agent.pipeline.research_loop import (
            ResearchLoopReport,
            run_stored_research_loop,
        )

        return {
            "ResearchLoopReport": ResearchLoopReport,
            "run_stored_research_loop": run_stored_research_loop,
        }[name]
    if name == "persist_research_loop_memory":
        from crypto_alpha_agent.pipeline.memory import persist_research_loop_memory

        return persist_research_loop_memory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
