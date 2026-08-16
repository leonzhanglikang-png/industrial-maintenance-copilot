from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import Retriever, SearchResult


class FakeRetriever:
    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        return self._results[:limit]


def make_search_result(index: int, score: float) -> SearchResult:
    chunk = Chunk(
        chunk_id=f"chunk-{index}",
        document_id="manual-001",
        text=f"Maintenance instruction {index}",
        chunk_index=index,
        source="pump_manual.pdf",
        page_number=index + 1,
    )
    return SearchResult(chunk=chunk, score=score)


def test_fake_retriever_matches_protocol() -> None:
    retriever = FakeRetriever([])

    assert isinstance(retriever, Retriever)


def test_search_result_preserves_chunk_and_score() -> None:
    result = make_search_result(index=0, score=0.92)

    assert result.score == 0.92
    assert result.chunk.chunk_id == "chunk-0"
    assert result.chunk.source == "pump_manual.pdf"
    assert result.chunk.page_number == 1


def test_fake_retriever_honors_limit() -> None:
    results = [
        make_search_result(index=0, score=0.9),
        make_search_result(index=1, score=0.8),
        make_search_result(index=2, score=0.7),
    ]
    retriever = FakeRetriever(results)

    returned_results = retriever.search("pump pressure", limit=2)

    assert len(returned_results) == 2
    assert returned_results == results[:2]
