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
            connection.execute(
                "CREATE TABLE IF NOT EXISTS deleted_documents (document_id TEXT PRIMARY KEY)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def add_chunks(self, chunks: Sequence[Chunk], *, restore: bool = True) -> int:
        # Serialize before starting the transaction: malformed input cannot partly commit.
        rows = [(chunk.chunk_id, chunk.model_dump_json()) for chunk in chunks]
        with closing(self._connect()) as connection, connection:
            if restore:
                connection.executemany(
                    "DELETE FROM deleted_documents WHERE document_id = ?",
                    [(chunk.document_id,) for chunk in chunks],
                )
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO chunks (chunk_id, payload) "
                "SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM deleted_documents "
                "WHERE document_id = json_extract(?, '$.document_id'))",
                [(chunk_id, payload, payload) for chunk_id, payload in rows],
            )
            added = connection.total_changes - before
            if added:
                connection.execute("UPDATE store_revision SET version = version + 1")
        return added

    def delete_document(self, document_id: str) -> int:
        with closing(self._connect()) as connection, connection:
            deleted = connection.execute(
                "DELETE FROM chunks WHERE json_extract(payload, '$.document_id') = ?",
                (document_id,),
            ).rowcount
            if deleted:
                connection.execute(
                    "INSERT OR IGNORE INTO deleted_documents VALUES (?)", (document_id,)
                )
                connection.execute("UPDATE store_revision SET version = version + 1")
        return deleted

    def load_if_changed(self, known_version: int) -> tuple[int, list[Chunk]] | None:
        with closing(self._connect()) as connection, connection:
            # Keep revision and payload reads in the same SQLite snapshot.
            connection.execute("BEGIN")
            version = connection.execute("SELECT version FROM store_revision").fetchone()[0]
            if version == known_version:
                return None
            rows = connection.execute("SELECT payload FROM chunks ORDER BY chunk_id").fetchall()
        return version, [Chunk.model_validate_json(row[0]) for row in rows]
