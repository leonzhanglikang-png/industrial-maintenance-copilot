import re

from backend.app.domain.answers import (
    AnswerCitation,
    GroundedAnswer,
)
from backend.app.ports.answering import AnswerGenerator
from backend.app.ports.retrieval import Retriever, SearchResult

WHITESPACE_PATTERN = re.compile(r"\s+")
MAX_EXCERPT_CHARACTERS = 360
SAFETY_NOTICE = "Maintenance recommendations require qualified human verification before action."


class RagAnswerService:
    def __init__(
        self,
        retriever: Retriever,
        generator: AnswerGenerator,
    ) -> None:
        self._retriever = retriever
        self._generator = generator

    def answer(
        self,
        query: str,
        *,
        evidence_limit: int = 5,
    ) -> GroundedAnswer:
        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("query must not be blank")

        if evidence_limit < 1:
            raise ValueError("evidence_limit must be at least 1")

        evidence = self._retriever.search(
            normalized_query,
            limit=evidence_limit,
        )
        draft = self._generator.generate(
            normalized_query,
            evidence,
        )
        citations = _build_citations(
            draft.cited_chunk_ids,
            evidence,
        )

        return GroundedAnswer(
            query=normalized_query,
            answer=draft.answer,
            grounded=bool(citations),
            retrieved_evidence_count=len(evidence),
            citations=citations,
            generation_method=draft.generation_method,
            safety_notice=SAFETY_NOTICE,
        )


def _build_citations(
    cited_chunk_ids: list[str],
    evidence: list[SearchResult],
) -> list[AnswerCitation]:
    evidence_by_chunk_id = {result.chunk.chunk_id: result for result in evidence}
    citations: list[AnswerCitation] = []

    for index, chunk_id in enumerate(cited_chunk_ids, start=1):
        result = evidence_by_chunk_id.get(chunk_id)

        if result is None:
            raise ValueError(f"generator cited unknown chunk: {chunk_id}")

        chunk = result.chunk
        citations.append(
            AnswerCitation(
                citation_id=f"S{index}",
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source=chunk.source,
                page_number=chunk.page_number,
                section=chunk.section,
                excerpt=_excerpt(chunk.text),
                score=result.score,
            )
        )

    return citations


def _excerpt(text: str) -> str:
    normalized = WHITESPACE_PATTERN.sub(" ", text).strip()

    if len(normalized) <= MAX_EXCERPT_CHARACTERS:
        return normalized

    return normalized[: MAX_EXCERPT_CHARACTERS - 1].rstrip() + "…"
