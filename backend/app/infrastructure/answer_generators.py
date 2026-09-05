import re
from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.domain.answers import AnswerDraft
from backend.app.ports.retrieval import SearchResult

TOKEN_PATTERN = re.compile(r"\w+")
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])\s+")
MARKDOWN_HEADING_PATTERN = re.compile(r"(?:^|\s)#{1,6}\s+")
WHITESPACE_PATTERN = re.compile(r"\s+")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "before",
    "can",
    "do",
    "for",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "may",
    "must",
    "need",
    "of",
    "on",
    "should",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}

NO_EVIDENCE_ANSWER = (
    "I could not find enough supporting evidence in the indexed maintenance documents."
)


@dataclass(frozen=True)
class SentenceCandidate:
    text: str
    chunk_id: str
    query_coverage: float
    overlap_count: int
    retrieval_rank: int
    sentence_index: int


class ExtractiveAnswerGenerator:
    def __init__(
        self,
        *,
        max_citations: int = 2,
        max_sentence_characters: int = 320,
        minimum_query_coverage: float = 0.6,
    ) -> None:
        if max_citations < 1:
            raise ValueError("max_citations must be at least 1")

        if max_sentence_characters < 40:
            raise ValueError("max_sentence_characters must be at least 40")

        if not 0.0 < minimum_query_coverage <= 1.0:
            raise ValueError("minimum_query_coverage must be between 0 and 1")

        self._max_citations = max_citations
        self._max_sentence_characters = max_sentence_characters
        self._minimum_query_coverage = minimum_query_coverage

    def generate(
        self,
        query: str,
        evidence: Sequence[SearchResult],
    ) -> AnswerDraft:
        if not query.strip():
            raise ValueError("query must not be blank")

        query_tokens = _content_tokens(query)

        if not query_tokens or not evidence:
            return AnswerDraft(
                answer=NO_EVIDENCE_ANSWER,
                generation_method="extractive",
            )

        candidates = self._rank_sentence_candidates(
            query_tokens,
            evidence,
        )
        selected = candidates[: self._max_citations]

        if not selected:
            return AnswerDraft(
                answer=NO_EVIDENCE_ANSWER,
                generation_method="extractive",
            )

        statements = [
            f"{_truncate(candidate.text, self._max_sentence_characters)} [S{index}]"
            for index, candidate in enumerate(selected, start=1)
        ]

        return AnswerDraft(
            answer="Based on the indexed maintenance documents: " + " ".join(statements),
            cited_chunk_ids=[candidate.chunk_id for candidate in selected],
            generation_method="extractive",
        )

    def _rank_sentence_candidates(
        self,
        query_tokens: set[str],
        evidence: Sequence[SearchResult],
    ) -> list[SentenceCandidate]:
        candidates: list[SentenceCandidate] = []

        for retrieval_rank, result in enumerate(evidence, start=1):
            best_candidate: SentenceCandidate | None = None

            for sentence_index, sentence in enumerate(_sentences(result.chunk.text)):
                sentence_tokens = _content_tokens(sentence)
                overlap_count = len(query_tokens & sentence_tokens)
                query_coverage = overlap_count / len(query_tokens)

                if query_coverage < self._minimum_query_coverage:
                    continue

                candidate = SentenceCandidate(
                    text=sentence,
                    chunk_id=result.chunk.chunk_id,
                    query_coverage=query_coverage,
                    overlap_count=overlap_count,
                    retrieval_rank=retrieval_rank,
                    sentence_index=sentence_index,
                )

                if best_candidate is None or _candidate_sort_key(candidate) < _candidate_sort_key(
                    best_candidate
                ):
                    best_candidate = candidate

            if best_candidate is not None:
                candidates.append(best_candidate)

        candidates.sort(key=_candidate_sort_key)
        return candidates


def _content_tokens(text: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(text.casefold()) if token not in STOP_WORDS}


def _sentences(text: str) -> list[str]:
    without_headings = MARKDOWN_HEADING_PATTERN.sub(" ", text.strip())
    normalized = WHITESPACE_PATTERN.sub(" ", without_headings).strip()

    if not normalized:
        return []

    return [
        sentence.strip()
        for sentence in SENTENCE_BOUNDARY_PATTERN.split(normalized)
        if sentence.strip()
    ]


def _candidate_sort_key(candidate: SentenceCandidate) -> tuple[float, int, int, int]:
    return (
        -candidate.query_coverage,
        -candidate.overlap_count,
        candidate.retrieval_rank,
        candidate.sentence_index,
    )


def _truncate(text: str, max_characters: int) -> str:
    if len(text) <= max_characters:
        return text

    return text[: max_characters - 1].rstrip() + "…"
