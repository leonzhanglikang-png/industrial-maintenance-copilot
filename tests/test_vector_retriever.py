from collections.abc import Sequence

import pytest

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from backend.app.infrastructure.vector_retriever import (
    InMemoryVectorRetriever,
    cosine_similarity,
)
from backend.app.ports.retrieval import ChunkIndexer, Retriever


def test_identical_vectors_have_maximum_similarity() -> None:
    score = cosine_similarity([1.0, 2.0], [1.0, 2.0])

    assert score == pytest.approx(1.0)


def test_orthogonal_vectors_have_zero_similarity() -> None:
    score = cosine_similarity([1.0, 0.0], [0.0, 1.0])

    assert score == pytest.approx(0.0)


def test_opposite_vectors_have_negative_similarity() -> None:
    score = cosine_similarity([1.0, 0.0], [-1.0, 0.0])

    assert score == pytest.approx(-1.0)


def test_zero_vector_has_zero_similarity() -> None:
    score = cosine_similarity([0.0, 0.0], [1.0, 2.0])

    assert score == 0.0


def test_vectors_must_have_same_dimension() -> None:
    with pytest.raises(ValueError, match="same dimension"):
        cosine_similarity([1.0], [1.0, 2.0])


class ControlledEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    @property
    def dimension(self) -> int:
        return 2

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]


def make_chunk(
    chunk_id: str,
    text: str,
    chunk_index: int,
    page_number: int,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="manual-001",
        text=text,
        chunk_index=chunk_index,
        source="pump_manual.pdf",
        page_number=page_number,
    )


def test_retriever_matches_protocol() -> None:
    provider = ControlledEmbeddingProvider({})
    retriever = InMemoryVectorRetriever([], provider)

    assert isinstance(retriever, Retriever)
    assert isinstance(retriever, ChunkIndexer)


def test_retriever_ranks_chunks_and_preserves_metadata() -> None:
    chunks = [
        make_chunk("chunk-pump", "pump alarm", 0, 1),
        make_chunk("chunk-motor", "motor temperature", 1, 2),
        make_chunk("chunk-pressure", "pressure warning", 2, 3),
    ]
    provider = ControlledEmbeddingProvider(
        {
            "pump alarm": [1.0, 0.0],
            "motor temperature": [0.0, 1.0],
            "pressure warning": [0.8, 0.2],
            "pump question": [1.0, 0.0],
        }
    )
    retriever = InMemoryVectorRetriever(chunks, provider)

    results = retriever.search("pump question", limit=2)

    assert [result.chunk.chunk_id for result in results] == [
        "chunk-pump",
        "chunk-pressure",
    ]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].chunk.source == "pump_manual.pdf"
    assert results[0].chunk.page_number == 1


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [
        ("", 1, "query"),
        ("pump", 0, "limit"),
    ],
)
def test_retriever_rejects_invalid_search(
    query: str,
    limit: int,
    message: str,
) -> None:
    provider = ControlledEmbeddingProvider(
        {
            "pump": [1.0, 0.0],
        }
    )
    retriever = InMemoryVectorRetriever([], provider)

    with pytest.raises(ValueError, match=message):
        retriever.search(query, limit=limit)


def test_retriever_integrates_with_hash_embedding_provider() -> None:
    chunks = [
        make_chunk(
            "chunk-pump",
            "pump pressure alarm",
            0,
            1,
        ),
        make_chunk(
            "chunk-motor",
            "motor temperature inspection",
            1,
            2,
        ),
    ]
    provider = DeterministicHashEmbeddingProvider(dimension=64)
    retriever = InMemoryVectorRetriever(chunks, provider)

    results = retriever.search("pump pressure alarm", limit=1)

    assert len(results) == 1
    assert results[0].chunk.chunk_id == "chunk-pump"
    assert results[0].score == pytest.approx(1.0)
    assert results[0].chunk.page_number == 1


def test_retriever_adds_chunks_after_initialization() -> None:
    pump_chunk = make_chunk(
        "chunk-pump",
        "pump alarm",
        0,
        1,
    )
    motor_chunk = make_chunk(
        "chunk-motor",
        "motor temperature",
        1,
        2,
    )
    provider = ControlledEmbeddingProvider(
        {
            "pump alarm": [1.0, 0.0],
            "motor temperature": [0.0, 1.0],
            "motor question": [0.0, 1.0],
        }
    )
    retriever = InMemoryVectorRetriever([pump_chunk], provider)

    added_count = retriever.add_chunks([motor_chunk])
    results = retriever.search("motor question", limit=1)

    assert added_count == 1
    assert results[0].chunk.chunk_id == "chunk-motor"


def test_retriever_ignores_duplicate_chunk_ids() -> None:
    chunk = make_chunk(
        "chunk-pump",
        "pump alarm",
        0,
        1,
    )
    provider = ControlledEmbeddingProvider(
        {
            "pump alarm": [1.0, 0.0],
            "pump question": [1.0, 0.0],
        }
    )
    retriever = InMemoryVectorRetriever([chunk], provider)

    added_count = retriever.add_chunks([chunk])
    results = retriever.search("pump question", limit=5)

    assert added_count == 0
    assert len(results) == 1
