from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from crypto_alpha_agent.data.models import RecordType, SourceRecord


class ResearchDataStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def upsert_records(self, records: Iterable[SourceRecord]) -> int:
        inserted_at = datetime.now(tz=UTC).isoformat()
        rows = [
            (
                record.record_id,
                record.source,
                record.record_type,
                record.observed_at.isoformat(),
                json.dumps(record.payload, sort_keys=True),
                inserted_at,
            )
            for record in records
        ]
        if not rows:
            return 0

        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO source_records (
                    record_id,
                    source,
                    record_type,
                    observed_at,
                    payload_json,
                    inserted_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def load_records(
        self,
        record_type: RecordType | None = None,
        source: str | None = None,
        observed_at_start: datetime | None = None,
        observed_at_end: datetime | None = None,
    ) -> list[SourceRecord]:
        query = """
            SELECT record_id, source, record_type, observed_at, payload_json
            FROM source_records
        """
        clauses: list[str] = []
        parameters: list[str] = []

        if record_type is not None:
            clauses.append("record_type = ?")
            parameters.append(record_type)
        if source is not None:
            clauses.append("source = ?")
            parameters.append(source)
        if observed_at_start is not None:
            clauses.append("observed_at >= ?")
            parameters.append(observed_at_start.isoformat())
        if observed_at_end is not None:
            clauses.append("observed_at < ?")
            parameters.append(observed_at_end.isoformat())
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY observed_at, record_id"

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            SourceRecord(
                record_id=record_id,
                source=row_source,
                record_type=row_record_type,
                observed_at=datetime.fromisoformat(observed_at),
                payload=json.loads(payload_json),
            )
            for record_id, row_source, row_record_type, observed_at, payload_json in rows
        ]

    def _create_schema(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_records (
                    record_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                )
                """
            )
