from __future__ import annotations

from typing import Any

from crypto_alpha_agent.memory.store import MemorySearchResult, MemoryStore


def retrieve_similar(
    store: MemoryStore,
    query: str,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[MemorySearchResult]:
    return store.retrieve_similar(query=query, top_k=top_k, filters=filters)
