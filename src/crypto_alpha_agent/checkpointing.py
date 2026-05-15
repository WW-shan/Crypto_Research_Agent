from __future__ import annotations

import pickle
from collections import defaultdict
from collections.abc import Sequence
from os import PathLike
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

ThreadConfig = dict[str, dict[str, str]]


def create_thread_config(thread_id: str) -> ThreadConfig:
    return {"configurable": {"thread_id": thread_id}}


class FileCheckpointSaver(MemorySaver):
    """Small filesystem-backed saver for local durable workflow checkpoints."""

    def __init__(self, path: str | PathLike[str]) -> None:
        self.path = Path(path)
        self._lock = RLock()
        super().__init__()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self._lock, self.path.open("rb") as checkpoint_file:
            data = pickle.load(checkpoint_file)  # noqa: S301 - local trusted checkpoint file
        self.storage.update(_checkpoint_storage(data.get("storage", {})))
        self.writes.update(data.get("writes", {}))
        self.blobs.update(data.get("blobs", {}))

    def _dump(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "storage": _plain_dict(self.storage),
            "writes": _plain_dict(self.writes),
            "blobs": dict(self.blobs),
        }
        temporary_path = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
        with self._lock, temporary_path.open("wb") as checkpoint_file:
            pickle.dump(data, checkpoint_file)
        temporary_path.replace(self.path)

    def put(
        self,
        config: dict[str, Any],
        checkpoint: dict[str, Any],
        metadata: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            next_config = super().put(config, checkpoint, metadata, new_versions)
            self._dump()
            return next_config

    def put_writes(
        self,
        config: dict[str, Any],
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        with self._lock:
            super().put_writes(config, writes, task_id, task_path)
            self._dump()

    def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            super().delete_thread(thread_id)
            self._dump()


def _plain_dict(value: Any) -> Any:
    if isinstance(value, defaultdict):
        return {key: _plain_dict(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {key: _plain_dict(item) for key, item in value.items()}
    return value


def _checkpoint_storage(storage: dict[str, Any]) -> defaultdict[str, defaultdict[str, dict[str, Any]]]:
    restored: defaultdict[str, defaultdict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
    for thread_id, namespaces in storage.items():
        restored[thread_id].update(namespaces)
    return restored


def create_checkpointer(path: str | PathLike[str] | None = None) -> MemorySaver:
    if path is None:
        return MemorySaver()
    return FileCheckpointSaver(path)


def build_checkpointed_graph(
    *,
    checkpointer: Any | None = None,
    interrupt_before: str | list[str] | None = None,
    interrupt_after: str | list[str] | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    from crypto_alpha_agent.orchestrator import build_graph

    return build_graph(
        checkpointer=checkpointer or create_checkpointer(),
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
        debug=debug,
    )
