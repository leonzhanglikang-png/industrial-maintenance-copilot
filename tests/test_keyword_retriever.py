import pytest

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.keyword_retriever import (
    InMemoryBM25Retriever,
)
from backend.app.ports.retrieval import ChunkIndexer, Retriever


def make_chunk(
    chunk_id: str,
    text: str,
    chunk_index: int,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="manual-001",
        text=text,
        chunk_index=chunk_index,
        source="manual.md",
    )


def test_bm25_retriever_matches_ports() -> None:
    retriever = InMemoryBM25Retriever([])

    assert isinstance(retriever, Retriever)
    assert isinstance(retriever, ChunkIndexer)


def test_bm25_retriever_ranks_exact_terms_first() -> None:
    chunks = [
        make_chunk(
            "chunk-pump",
            "Inspect pump suction pressure and inlet valve.",
            0,
        ),
        make_chunk(
            "chunk-motor",
            "Inspect motor bearing temperature and lubrication.",
            1,
        ),
    ]
    retriever = InMemoryBM25Retriever(chunks)

    results = retriever.search(
        "pump suction pressure",
        limit=2,
    )

    assert results[0].chunk.chunk_id == "chunk-pump"
    assert results[0].score > results[1].score


def test_bm25_retriever_is_case_insensitive() -> None:
    chunk = make_chunk(
        "chunk-pump",
        "Pump Pressure Alarm",
        0,
    )
    retriever = InMemoryBM25Retriever([chunk])

    lower_result = retriever.search("pump pressure", limit=1)
    upper_result = retriever.search("PUMP PRESSURE", limit=1)

    assert lower_result[0].score == upper_result[0].score


def test_bm25_retriever_adds_chunks_without_duplicates() -> None:
    pump_chunk = make_chunk(
        "chunk-pump",
        "pump pressure",
        0,
    )
    motor_chunk = make_chunk(
        "chunk-motor",
        "motor temperature",
        1,
    )
    retriever = InMemoryBM25Retriever([pump_chunk])

    added_count = retriever.add_chunks([pump_chunk, motor_chunk])
    results = retriever.search("motor temperature", limit=5)

    assert added_count == 1
    assert len(results) == 2
    assert results[0].chunk.chunk_id == "chunk-motor"


def test_bm25_retriever_returns_empty_results_for_empty_index() -> None:
    retriever = InMemoryBM25Retriever([])

    assert retriever.search("pump", limit=5) == []


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [
        ("", 1, "query"),
        ("pump", 0, "limit"),
    ],
)
def test_bm25_retriever_rejects_invalid_search(
    query: str,
    limit: int,
    message: str,
) -> None:
    retriever = InMemoryBM25Retriever([])

    with pytest.raises(ValueError, match=message):
        retriever.search(query, limit=limit)


@pytest.mark.parametrize(
    ("k1", "b", "message"),
    [
        (0.0, 0.75, "k1"),
        (1.5, -0.1, "b"),
        (1.5, 1.1, "b"),
    ],
)
def test_bm25_retriever_rejects_invalid_parameters(
    k1: float,
    b: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        InMemoryBM25Retriever([], k1=k1, b=b)
