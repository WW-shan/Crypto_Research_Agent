from __future__ import annotations

import json
from datetime import UTC
import datetime as dt
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

JsonPrimitive = str | int | float | bool | None


class ObservabilityEvent(BaseModel):
    """A durable event record with enough context to replay decisions."""

    model_config = ConfigDict(extra="forbid")

    timestamp: dt.datetime
    date: dt.date | None = None
    event_type: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    opportunity_id: str | None = None
    idea_id: str | None = None
    decision: str | None = None
    action: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    details: dict[str, JsonPrimitive] = Field(default_factory=dict)

    @model_validator(mode="after")
    def default_event_date(self) -> Self:
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)
        if self.date is None:
            self.date = self.timestamp.date()
        return self


class EventLoadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[ObservabilityEvent]
    skipped_count: int = Field(ge=0)


class EventLogger:
    """Append-only JSONL writer for local deterministic event persistence."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._handle: Any | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def open(self) -> None:
        if self._handle is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def close(self) -> None:
        if self._handle is None:
            return
        self._handle.close()
        self._handle = None

    def record(self, **event_data: object) -> ObservabilityEvent:
        event = ObservabilityEvent.model_validate(event_data)
        if self._handle is None:
            self.open()
        assert self._handle is not None
        self._handle.write(event.model_dump_json() + "\n")
        self._handle.flush()
        return event


def load_events(path: str | Path) -> EventLoadResult:
    events: list[ObservabilityEvent] = []
    skipped_count = 0
    event_path = Path(path)
    if not event_path.exists():
        return EventLoadResult(events=events, skipped_count=0)

    with event_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                events.append(ObservabilityEvent.model_validate(payload))
            except (json.JSONDecodeError, TypeError, ValidationError):
                skipped_count += 1

    return EventLoadResult(events=events, skipped_count=skipped_count)
