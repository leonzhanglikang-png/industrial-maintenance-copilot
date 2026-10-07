"""SQLite fault history shared by the workbench and the read-only Agent tool."""

import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from backend.app.domain.agent import FaultRecord


class SQLiteFaultStore:
    def __init__(self, path: Path, seeds: Sequence[FaultRecord] = ()) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS fault_records "
                "(fault_id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL, "
                "occurred_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS faults_equipment_date "
                "ON fault_records(equipment_id, occurred_at DESC, fault_id DESC)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS fault_seed_import (singleton INTEGER PRIMARY KEY)"
            )
            claimed = connection.execute(
                "INSERT OR IGNORE INTO fault_seed_import VALUES (1)"
            ).rowcount
            if claimed:
                connection.executemany(
                    "INSERT OR IGNORE INTO fault_records VALUES (?, ?, ?, ?)",
                    [self._row(record.model_copy(update={"is_demo": True})) for record in seeds],
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    @staticmethod
    def _row(record: FaultRecord) -> tuple[str, str, str, str]:
        return (
            record.fault_id,
            record.equipment_id.strip().casefold(),
            record.occurred_at.isoformat(),
            record.model_dump_json(),
        )

    def add(self, record: FaultRecord) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("INSERT INTO fault_records VALUES (?, ?, ?, ?)", self._row(record))

    def lookup(self, equipment_id: str, *, limit: int = 20) -> list[FaultRecord]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM fault_records WHERE equipment_id = ? "
                "ORDER BY occurred_at DESC, fault_id DESC LIMIT ?",
                (equipment_id.strip().casefold(), limit),
            ).fetchall()
        return [FaultRecord.model_validate_json(row[0]) for row in rows]
