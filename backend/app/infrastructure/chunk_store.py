"""Persist parsed chunks in SQLite; original uploaded files are not retained."""

import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from backend.app.domain.documents import Chunk


class SQLiteChunkStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS chunks "
                "(chunk_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS store_revision "
                "(singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL)"
            )
            connection.execute("INSERT OR IGNORE INTO store_revision VALUES (1, 0)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def add_chunks(self, chunks: Sequence[Chunk]) -> int:
        # Serialize before starting the transaction: malformed input cannot partly commit.
        rows = [(chunk.chunk_id, chunk.model_dump_json()) for chunk in chunks]
        with closing(self._connect()) as connection, connection:
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO chunks (chunk_id, payload) VALUES (?, ?)", rows
            )
            added = connection.total_changes - before
            if added:
                connection.execute("UPDATE store_revision SET version = version + 1")
        return added

    def load_if_changed(self, known_version: int) -> tuple[int, list[Chunk]] | None:
        with closing(self._connect()) as connection, connection:
            # Keep revision and payload reads in the same SQLite snapshot.
            connection.execute("BEGIN")
            version = connection.execute("SELECT version FROM store_revision").fetchone()[0]
            if version == known_version:
                return None
            rows = connection.execute("SELECT payload FROM chunks ORDER BY chunk_id").fetchall()
        return version, [Chunk.model_validate_json(row[0]) for row in rows]
