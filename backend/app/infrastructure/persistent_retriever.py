"""A durable chunk source with a replaceable, process-local search index."""

from collections.abc import Callable, Sequence
from threading import RLock

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.chunk_store import SQLiteChunkStore
from backend.app.ports.retrieval import SearchIndex, SearchResult


class PersistentSearchIndex:
    def __init__(
        self,
        store: SQLiteChunkStore,
        build_index: Callable[[Sequence[Chunk]], SearchIndex],
        seed_chunks: Sequence[Chunk] = (),
    ) -> None:
        self._store = store
        self._build_index = build_index
        self._lock = RLock()
        self._version = -1
        self._chunks: list[Chunk] = []
        self._index = build_index(())
        store.add_chunks(seed_chunks)
        self._refresh()

    def _refresh(self) -> None:
        snapshot = self._store.load_if_changed(self._version)
        if snapshot is not None:
            version, chunks = snapshot
            # Build both indexes before replacing the currently searchable snapshot.
            new_index = self._build_index(chunks)
            self._index, self._chunks, self._version = new_index, chunks, version

    def add_chunks(self, chunks: Sequence[Chunk]) -> int:
        with self._lock:
            added = self._store.add_chunks(chunks)
            self._refresh()
            return added

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        with self._lock:
            self._refresh()
            return self._index.search(query, limit=limit)

    def list_documents(self) -> list[dict[str, object]]:
        with self._lock:
            self._refresh()
            documents: dict[str, dict[str, object]] = {}
            counts: dict[str, int] = {}
            for chunk in self._chunks:
                counts[chunk.document_id] = counts.get(chunk.document_id, 0) + 1
                documents.setdefault(
                    chunk.document_id,
                    {"document_id": chunk.document_id, "source": chunk.source},
                )
            return [
                {**document, "chunk_count": counts[document_id]}
                for document_id, document in sorted(documents.items())
            ]
