from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from crypto_alpha_agent.evidence.models import PaperSimulationOutcome


class PaperOutcomeLedger:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def upsert_outcomes(self, outcomes: Iterable[PaperSimulationOutcome]) -> int:
        inserted_at = datetime.now(tz=UTC).isoformat()
        rows = [
            (
                outcome.outcome_id,
                outcome.run_id,
                outcome.candidate_id,
                outcome.strategy_family,
                outcome.symbol,
                outcome.observed_at.isoformat(),
                outcome.status,
                json.dumps(outcome.model_dump(mode="json"), sort_keys=True),
                inserted_at,
            )
            for outcome in outcomes
        ]
        if not rows:
            return 0

        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO paper_outcomes (
                    outcome_id,
                    run_id,
                    candidate_id,
                    strategy_family,
                    symbol,
                    observed_at,
                    status,
                    payload_json,
                    inserted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def load_outcomes(
        self,
        strategy_family: str | None = None,
        symbol: str | None = None,
        run_id: str | None = None,
    ) -> list[PaperSimulationOutcome]:
        query = """
            SELECT payload_json
            FROM paper_outcomes
        """
        clauses: list[str] = []
        parameters: list[str] = []

        if strategy_family is not None:
            clauses.append("strategy_family = ?")
            parameters.append(strategy_family)
        if symbol is not None:
            clauses.append("symbol = ?")
            parameters.append(symbol)
        if run_id is not None:
            clauses.append("run_id = ?")
            parameters.append(run_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY observed_at, outcome_id"

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            PaperSimulationOutcome.model_validate_json(payload_json)
            for (payload_json,) in rows
        ]

    def _create_schema(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    strategy_family TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                )
                """
            )
