from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from crypto_alpha_agent.evidence.models import ValidationEvidence


_CREATE_VALIDATION_EVIDENCE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS validation_evidence (
        evidence_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        strategy_family TEXT NOT NULL,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        approved INTEGER NOT NULL,
        blocked_reasons_json TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        inserted_at TEXT NOT NULL,
        PRIMARY KEY (run_id, evidence_id)
    )
"""

_REQUIRED_VALIDATION_EVIDENCE_COLUMNS = {
    "evidence_id",
    "run_id",
    "strategy_family",
    "symbol",
    "timeframe",
    "approved",
    "blocked_reasons_json",
    "payload_json",
    "inserted_at",
}


class ValidationEvidenceLedger:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def upsert_evidence(self, items: Iterable[ValidationEvidence]) -> int:
        rows = self._evidence_rows(items)
        if not rows:
            return 0

        with sqlite3.connect(self.db_path) as connection:
            self._insert_rows(connection, rows)
        return len(rows)

    def replace_run_evidence(
        self,
        run_id: str,
        items: Iterable[ValidationEvidence],
    ) -> int:
        normalized_run_id = _normalize_filter(run_id)
        if normalized_run_id is None:
            raise ValueError("run_id must be non-empty")

        evidence_list = list(items)
        mismatched_evidence_ids = [
            item.evidence_id for item in evidence_list if item.run_id != normalized_run_id
        ]
        if mismatched_evidence_ids:
            raise ValueError("all replacement evidence must match run_id")

        rows = self._evidence_rows(evidence_list)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                DELETE FROM validation_evidence
                WHERE run_id = ?
                """,
                (normalized_run_id,),
            )
            if rows:
                self._insert_rows(connection, rows)
        return len(rows)

    def load_evidence(
        self,
        strategy_family: str | None = None,
        symbol: str | None = None,
        run_id: str | None = None,
    ) -> list[ValidationEvidence]:
        query = """
            SELECT payload_json
            FROM validation_evidence
        """
        clauses: list[str] = []
        parameters: list[str] = []

        normalized_strategy_family = _normalize_filter(strategy_family)
        normalized_symbol = _normalize_filter(symbol)
        normalized_run_id = _normalize_filter(run_id)
        if (
            strategy_family is not None
            and normalized_strategy_family is None
            or symbol is not None
            and normalized_symbol is None
            or run_id is not None
            and normalized_run_id is None
        ):
            return []

        if normalized_strategy_family is not None:
            clauses.append("strategy_family = ?")
            parameters.append(normalized_strategy_family)
        if normalized_symbol is not None:
            clauses.append("symbol = ?")
            parameters.append(normalized_symbol)
        if normalized_run_id is not None:
            clauses.append("run_id = ?")
            parameters.append(normalized_run_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY run_id, strategy_family, symbol, timeframe, evidence_id"

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            ValidationEvidence.model_validate_json(payload_json)
            for (payload_json,) in rows
        ]

    def _create_schema(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            if _validation_evidence_table_exists(connection):
                missing_columns = _missing_required_columns(connection)
                if missing_columns:
                    missing_column_list = ", ".join(sorted(missing_columns))
                    raise ValueError(
                        "validation_evidence schema is incompatible: "
                        f"missing {missing_column_list}"
                    )
                if not _has_run_scoped_primary_key(connection):
                    try:
                        self._migrate_to_run_scoped_primary_key(connection)
                    except sqlite3.OperationalError as exc:
                        raise ValueError(
                            "validation_evidence schema is incompatible: "
                            "migration failed"
                        ) from exc
            else:
                connection.execute(_CREATE_VALIDATION_EVIDENCE_TABLE_SQL)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_validation_evidence_run_id
                ON validation_evidence (run_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_validation_evidence_strategy_family
                ON validation_evidence (strategy_family)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_validation_evidence_symbol
                ON validation_evidence (symbol)
                """
            )

    def _migrate_to_run_scoped_primary_key(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT run_id, payload_json
            FROM validation_evidence
            ORDER BY run_id, strategy_family, symbol, timeframe, evidence_id
            """
        ).fetchall()
        evidence = [
            ValidationEvidence.model_validate(_payload_with_run_id(run_id, payload_json))
            for run_id, payload_json in rows
        ]
        connection.execute("DROP TABLE validation_evidence")
        connection.execute(_CREATE_VALIDATION_EVIDENCE_TABLE_SQL)
        migrated_rows = self._evidence_rows(evidence)
        if migrated_rows:
            self._insert_rows(connection, migrated_rows)

    def _evidence_rows(
        self,
        items: Iterable[ValidationEvidence],
    ) -> list[tuple[str, str, str, str, str, int, str, str, str]]:
        inserted_at = datetime.now(tz=UTC).isoformat()
        rows = []
        for item in items:
            if item.run_id is None:
                raise ValueError("validation evidence run_id must be set before ledger persistence")
            rows.append(
                (
                    _ledger_evidence_id(item),
                    item.run_id,
                    item.strategy_family,
                    item.symbol,
                    item.timeframe,
                    int(item.approved),
                    json.dumps(list(item.blocked_reasons), sort_keys=True),
                    json.dumps(item.model_dump(mode="json"), sort_keys=True),
                    inserted_at,
                )
            )
        return rows

    def _insert_rows(
        self,
        connection: sqlite3.Connection,
        rows: list[tuple[str, str, str, str, str, int, str, str, str]],
    ) -> None:
        connection.executemany(
            """
            INSERT OR REPLACE INTO validation_evidence (
                evidence_id,
                run_id,
                strategy_family,
                symbol,
                timeframe,
                approved,
                blocked_reasons_json,
                payload_json,
                inserted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def _ledger_evidence_id(item: ValidationEvidence) -> str:
    return item.evidence_id


def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _payload_with_run_id(run_id: str, payload_json: str) -> dict[str, object]:
    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        raise ValueError("validation evidence payload must be an object")
    payload_run_id = payload.get("run_id")
    if payload_run_id is None:
        payload["run_id"] = run_id
    elif payload_run_id != run_id:
        raise ValueError("validation evidence payload run_id does not match table run_id")
    return payload


def _validation_evidence_table_exists(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'validation_evidence'
            """
        ).fetchone()
        is not None
    )


def _has_run_scoped_primary_key(connection: sqlite3.Connection) -> bool:
    primary_key_columns = [
        name
        for _, name in sorted(
            (pk_order, column_name)
            for _, column_name, _, _, _, pk_order in connection.execute(
                "PRAGMA table_info(validation_evidence)"
            ).fetchall()
            if pk_order
        )
    ]
    return primary_key_columns == ["run_id", "evidence_id"]


def _missing_required_columns(connection: sqlite3.Connection) -> set[str]:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(validation_evidence)").fetchall()
    }
    return _REQUIRED_VALIDATION_EVIDENCE_COLUMNS - existing_columns
