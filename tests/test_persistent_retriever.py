import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.app.api.dependencies import build_reranked_hybrid_index
from backend.app.domain.documents import Chunk
from backend.app.infrastructure.chunk_store import SQLiteChunkStore
from backend.app.infrastructure.persistent_retriever import PersistentSearchIndex


def make_chunk(chunk_id: str = "compressor") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="manual-compressor",
        source="compressor.pdf",
        text="Inspect the compressor oil filter when oil pressure is low.",
        chunk_index=0,
        page_number=7,
        section="Oil pressure",
    )


def open_index(path: Path) -> PersistentSearchIndex:
    return PersistentSearchIndex(SQLiteChunkStore(path), build_reranked_hybrid_index)


def test_rebuilt_index_preserves_text_metadata_and_deduplication(tmp_path: Path) -> None:
    path = tmp_path / "documents.sqlite3"
    first = open_index(path)
    assert first.add_chunks([make_chunk()]) == 1
    second = open_index(path)
    hit = second.search("compressor oil filter", limit=1)[0]
    assert hit.chunk == make_chunk()
    assert second.add_chunks([make_chunk()]) == 0
    assert second.list_documents() == [
        {"document_id": "manual-compressor", "source": "compressor.pdf", "chunk_count": 1}
    ]


def test_existing_reader_refreshes_after_another_writer_commits(tmp_path: Path) -> None:
    path = tmp_path / "shared.sqlite3"
    reader, writer = open_index(path), open_index(path)
    assert reader.search("compressor") == []
    writer.add_chunks([make_chunk()])
    assert reader.search("compressor")[0].chunk.chunk_id == "compressor"


def test_failed_sql_batch_rolls_back_all_chunks_and_revision(tmp_path: Path) -> None:
    path = tmp_path / "atomic.sqlite3"
    store = SQLiteChunkStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_bad BEFORE INSERT ON chunks "
            "WHEN NEW.chunk_id = 'bad' BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        store.add_chunks([make_chunk("good"), make_chunk("bad")])
    assert store.load_if_changed(-1) == (0, [])


def test_concurrent_duplicate_writes_store_one_chunk(tmp_path: Path) -> None:
    store = SQLiteChunkStore(tmp_path / "concurrent.sqlite3")
    with ThreadPoolExecutor(max_workers=4) as executor:
        counts = list(executor.map(lambda _: store.add_chunks([make_chunk()]), range(4)))
    assert sum(counts) == 1
    assert store.load_if_changed(-1) == (1, [make_chunk()])


def test_failed_index_rebuild_can_recover_from_durable_data(tmp_path: Path) -> None:
    failing = False

    def builder(chunks):
        if failing:
            raise RuntimeError("injected build failure")
        return build_reranked_hybrid_index(chunks)

    index = PersistentSearchIndex(SQLiteChunkStore(tmp_path / "recover.sqlite3"), builder)
    failing = True
    with pytest.raises(RuntimeError, match="build failure"):
        index.add_chunks([make_chunk()])
    failing = False
    assert index.search("oil filter")[0].chunk == make_chunk()
