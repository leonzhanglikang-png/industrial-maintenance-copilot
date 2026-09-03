from collections.abc import Sequence

import pytest

from backend.app.domain.answers import AnswerDraft
from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import SearchResult
from backend.app.services.rag_answering import (
    SAFETY_NOTICE,
    RagAnswerService,
)


class FakeRetriever:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        self.calls.append((query, limit))
        return self.results[:limit]


class FakeAnswerGenerator:
    def __init__(self, draft: AnswerDraft) -> None:
        self.draft = draft
        self.calls: list[tuple[str, Sequence[SearchResult]]] = []

    def generate(
        self,
        query: str,
        evidence: Sequence[SearchResult],
    ) -> AnswerDraft:
        self.calls.append((query, evidence))
        return self.draft


def make_result() -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            chunk_id="chunk-pressure",
            document_id="manual-001",
            text="Inspect the suction line for blockage.",
            chunk_index=0,
            source="pump_manual.pdf",
            page_number=7,
            section="Low pressure",
        ),
        score=0.92,
    )


def test_rag_service_builds_verified_citation_metadata() -> None:
    evidence = [make_result()]
    retriever = FakeRetriever(evidence)
    generator = FakeAnswerGenerator(
        AnswerDraft(
            answer="Inspect the suction line. [S1]",
            cited_chunk_ids=["chunk-pressure"],
        )
    )
    service = RagAnswerService(retriever, generator)

    result = service.answer(
        "  low pump pressure  ",
        evidence_limit=3,
    )

    assert retriever.calls == [("low pump pressure", 3)]
    assert generator.calls[0][0] == "low pump pressure"
    assert result.grounded is True
    assert result.retrieved_evidence_count == 1
    assert result.safety_notice == SAFETY_NOTICE
    assert result.citations[0].citation_id == "S1"
    assert result.citations[0].source == "pump_manual.pdf"
    assert result.citations[0].page_number == 7
    assert result.citations[0].score == 0.92


def test_rag_service_rejects_unknown_generator_citation() -> None:
    retriever = FakeRetriever([make_result()])
    generator = FakeAnswerGenerator(
        AnswerDraft(
            answer="Unsupported claim. [S1]",
            cited_chunk_ids=["chunk-does-not-exist"],
        )
    )
    service = RagAnswerService(retriever, generator)

    with pytest.raises(ValueError, match="unknown chunk"):
        service.answer("pump pressure")


def test_rag_service_marks_uncited_answer_as_not_grounded() -> None:
    retriever = FakeRetriever([make_result()])
    generator = FakeAnswerGenerator(AnswerDraft(answer="Not enough evidence."))
    service = RagAnswerService(retriever, generator)

    result = service.answer("unrelated question")

    assert result.grounded is False
    assert result.citations == []
    assert result.retrieved_evidence_count == 1


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [
        ("", 1, "query"),
        ("pump", 0, "evidence_limit"),
    ],
)
def test_rag_service_rejects_invalid_request(
    query: str,
    limit: int,
    message: str,
) -> None:
    service = RagAnswerService(
        FakeRetriever([]),
        FakeAnswerGenerator(AnswerDraft(answer="No evidence.")),
    )

    with pytest.raises(ValueError, match=message):
        service.answer(query, evidence_limit=limit)
