from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import math
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts = []
        for key in sorted(value):
            parts.append(str(key))
            parts.append(_stringify(value[key]))
        return " ".join(parts)
    if isinstance(value, (list, tuple, set)):
        return " ".join(_stringify(item) for item in value)
    return str(value)


def _record_text(record: "MemoryRecord") -> str:
    parts = [
        record.record_id,
        _stringify(record.opportunity),
        _stringify(record.hypothesis),
        _stringify(record.score),
        _stringify(record.rejected_reasons),
        _stringify(record.backtest_artifacts),
        _stringify(record.paper_trade_outcome),
        _stringify(record.tags),
    ]
    return " ".join(part for part in parts if part)


def _vectorize_text(text: str, dimensions: int = 256) -> list[float]:
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dimensions

    counts = Counter(tokens)
    vector = [0.0] * dimensions
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        vector[index] += float(count)

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return [0.0] * dimensions
    return [value / norm for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimensionality")
    return float(sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True)))


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record_id: str
    created_at: str | None = None
    updated_at: str | None = None
    opportunity: dict[str, Any] | None = None
    hypothesis: dict[str, Any] | None = None
    score: dict[str, Any] | None = None
    rejected_reasons: list[str] = Field(default_factory=list)
    backtest_artifacts: dict[str, Any] | None = None
    paper_trade_outcome: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)


class MemorySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record: MemoryRecord
    score: float


class MemoryStore:
    def __init__(self, path: str | Path, dimensions: int = 256) -> None:
        self.path = Path(path)
        self.dimensions = dimensions
        self._records: list[MemoryRecord] = []
        self._index: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        self._records = []
        self._index = {}
        if not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            record = MemoryRecord.model_validate_json(line)
            self._index[record.record_id] = len(self._records)
            self._records.append(record)

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in self._records:
                handle.write(record.model_dump_json())
                handle.write("\n")

    def _prepare_record(self, record: MemoryRecord) -> MemoryRecord:
        timestamp = record.created_at or _now_iso()
        embedding = _vectorize_text(_record_text(record), self.dimensions)
        return record.model_copy(
            update={
                "created_at": timestamp,
                "updated_at": _now_iso(),
                "embedding": embedding,
            }
        )

    def append(self, record: MemoryRecord) -> MemoryRecord:
        stored = self._prepare_record(record)
        if stored.record_id in self._index:
            self._records[self._index[stored.record_id]] = stored
        else:
            self._index[stored.record_id] = len(self._records)
            self._records.append(stored)
        self._persist()
        return stored

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        return self.append(record)

    def list_records(self) -> list[MemoryRecord]:
        return list(self._records)

    def get(self, record_id: str) -> MemoryRecord | None:
        index = self._index.get(record_id)
        if index is None:
            return None
        return self._records[index]

    def retrieve_similar(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[MemorySearchResult]:
        query_vector = _vectorize_text(query, self.dimensions)
        results: list[MemorySearchResult] = []
        for record in self._records:
            if filters and not _matches_filters(record, filters):
                continue
            score = _cosine_similarity(query_vector, record.embedding)
            query_tokens = set(_tokenize(query))
            record_tokens = set(_tokenize(_record_text(record)))
            overlap = len(query_tokens & record_tokens)
            rejection_bonus = 0.05 if record.rejected_reasons else 0.0
            combined_score = score + (overlap * 0.03) + rejection_bonus
            results.append(MemorySearchResult(record=record, score=combined_score))
        results.sort(key=lambda result: (result.score, result.record.created_at or ""), reverse=True)
        return results[:top_k]


def _matches_filters(record: MemoryRecord, filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        if key == "has_rejected_reasons":
            if bool(record.rejected_reasons) is not bool(expected):
                return False
            continue
        value = getattr(record, key, None)
        if value != expected:
            return False
    return True
