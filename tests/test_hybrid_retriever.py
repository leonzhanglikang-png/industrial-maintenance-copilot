from collections.abc import Sequence

import pytest

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.hybrid_retriever import (
    ReciprocalRankFusionIndex,
)
from backend.app.ports.retrieval import (
    ChunkIndexer,
    Retriever,
    SearchIndex,
    SearchResult,
)


class StubSearchIndex:
    def __init__(self, results: Sequence[SearchResult]) -> None:
        self.results = list(results)
        self.requested_limits: list[int] = []
        self.added_chunks: list[Chunk] = []

    def add_chunks(self, chunks: Sequence[Chunk]) -> int:
        self.added_chunks.extend(chunks)
        return len(chunks)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        self.requested_limits.append(limit)
        return self.results[:limit]


def make_chunk(chunk_id: str, index: int) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="manual-001",
        text=f"Maintenance instruction {index}",
        chunk_index=index,
        source="manual.md",
    )


def make_result(chunk: Chunk, score: float) -> SearchResult:
    return SearchResult(chunk=chunk, score=score)


def test_rrf_index_matches_search_and_index_ports() -> None:
    first = StubSearchIndex([])
    second = StubSearchIndex([])
    index = ReciprocalRankFusionIndex([first, second])

    assert isinstance(index, Retriever)
    assert isinstance(index, ChunkIndexer)
    assert isinstance(index, SearchIndex)


def test_rrf_fuses_rankings_and_ignores_raw_score_scales() -> None:
    chunk_a = make_chunk("chunk-a", 0)
    chunk_b = make_chunk("chunk-b", 1)
    chunk_c = make_chunk("chunk-c", 2)
    first = StubSearchIndex(
        [
            make_result(chunk_a, 0.01),
            make_result(chunk_b, 0.009),
            make_result(chunk_c, 0.008),
        ]
    )
    second = StubSearchIndex(
        [
            make_result(chunk_b, 900.0),
            make_result(chunk_c, 800.0),
            make_result(chunk_a, 700.0),
        ]
    )
    index = ReciprocalRankFusionIndex([first, second])

    results = index.search("pump pressure", limit=3)

    assert [result.chunk.chunk_id for result in results] == [
        "chunk-b",
        "chunk-a",
        "chunk-c",
    ]
    assert results[0].score == pytest.approx(1 / 61 + 1 / 62)


def test_rrf_overfetches_candidates_from_every_index() -> None:
    first = StubSearchIndex([])
    second = StubSearchIndex([])
    index = ReciprocalRankFusionIndex(
        [first, second],
        candidate_multiplier=3,
    )

    index.search("pump", limit=2)

    assert first.requested_limits == [6]
    assert second.requested_limits == [6]


def test_rrf_adds_chunks_to_every_underlying_index() -> None:
    first = StubSearchIndex([])
    second = StubSearchIndex([])
    index = ReciprocalRankFusionIndex([first, second])
    chunk = make_chunk("chunk-new", 0)

    added_count = index.add_chunks([chunk])

    assert added_count == 1
    assert first.added_chunks == [chunk]
    assert second.added_chunks == [chunk]


@pytest.mark.parametrize(
    ("indexes", "rrf_k", "candidate_multiplier", "message"),
    [
        ([StubSearchIndex([])], 60, 4, "two indexes"),
        ([StubSearchIndex([]), StubSearchIndex([])], 0, 4, "rrf_k"),
        ([StubSearchIndex([]), StubSearchIndex([])], 60, 0, "candidate_multiplier"),
    ],
)
def test_rrf_rejects_invalid_configuration(
    indexes: list[StubSearchIndex],
    rrf_k: int,
    candidate_multiplier: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ReciprocalRankFusionIndex(
            indexes,
            rrf_k=rrf_k,
            candidate_multiplier=candidate_multiplier,
        )


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [
        ("", 1, "query"),
        ("pump", 0, "limit"),
    ],
)
def test_rrf_rejects_invalid_search(
    query: str,
    limit: int,
    message: str,
) -> None:
    index = ReciprocalRankFusionIndex([StubSearchIndex([]), StubSearchIndex([])])

    with pytest.raises(ValueError, match=message):
        index.search(query, limit=limit)
