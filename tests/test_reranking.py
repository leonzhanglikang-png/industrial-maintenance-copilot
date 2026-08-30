from collections.abc import Sequence

import pytest

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.reranking import (
    RerankingSearchIndex,
    TokenOverlapReranker,
)
from backend.app.ports.retrieval import (
    Reranker,
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


def make_result(
    chunk_id: str,
    text: str,
    index: int,
    score: float,
) -> SearchResult:
    chunk = Chunk(
        chunk_id=chunk_id,
        document_id="manual-001",
        text=text,
        chunk_index=index,
        source="manual.md",
    )
    return SearchResult(chunk=chunk, score=score)


def test_token_overlap_reranker_matches_port() -> None:
    reranker = TokenOverlapReranker()

    assert isinstance(reranker, Reranker)


def test_token_overlap_reranker_promotes_better_query_match() -> None:
    results = [
        make_result(
            "chunk-bearing",
            "Inspect motor bearing temperature.",
            0,
            0.95,
        ),
        make_result(
            "chunk-oil",
            "Never bypass the low oil pressure alarm.",
            1,
            0.80,
        ),
    ]
    reranker = TokenOverlapReranker()

    reranked = reranker.rerank(
        "low oil pressure",
        results,
        limit=2,
    )

    assert reranked[0].chunk.chunk_id == "chunk-oil"
    assert reranked[0].score > reranked[1].score


def test_reranking_index_overfetches_then_returns_requested_limit() -> None:
    results = [
        make_result("chunk-a", "pump", 0, 0.9),
        make_result("chunk-b", "pump pressure", 1, 0.8),
        make_result("chunk-c", "motor", 2, 0.7),
    ]
    source_index = StubSearchIndex(results)
    index = RerankingSearchIndex(
        source_index,
        TokenOverlapReranker(),
        candidate_multiplier=3,
    )

    reranked = index.search("pump pressure", limit=1)

    assert isinstance(index, SearchIndex)
    assert source_index.requested_limits == [3]
    assert len(reranked) == 1
    assert reranked[0].chunk.chunk_id == "chunk-b"


def test_reranking_index_forwards_new_chunks() -> None:
    source_index = StubSearchIndex([])
    index = RerankingSearchIndex(
        source_index,
        TokenOverlapReranker(),
    )
    chunk = make_result("chunk-new", "pump", 0, 1.0).chunk

    added_count = index.add_chunks([chunk])

    assert added_count == 1
    assert source_index.added_chunks == [chunk]


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [
        ("", 1, "query"),
        ("pump", 0, "limit"),
    ],
)
def test_token_overlap_reranker_rejects_invalid_request(
    query: str,
    limit: int,
    message: str,
) -> None:
    reranker = TokenOverlapReranker()

    with pytest.raises(ValueError, match=message):
        reranker.rerank(query, [], limit=limit)


def test_reranking_index_rejects_invalid_candidate_multiplier() -> None:
    with pytest.raises(ValueError, match="candidate_multiplier"):
        RerankingSearchIndex(
            StubSearchIndex([]),
            TokenOverlapReranker(),
            candidate_multiplier=0,
        )
