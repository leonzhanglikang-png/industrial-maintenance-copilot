import re
from collections import Counter
from collections.abc import Sequence
from math import log

from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import SearchResult

TOKEN_PATTERN = re.compile(r"\w+")


class InMemoryBM25Retriever:
    def __init__(
        self,
        chunks: Sequence[Chunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0.0:
            raise ValueError("k1 must be positive")

        if not 0.0 <= b <= 1.0:
            raise ValueError("b must be between 0 and 1")

        self._k1 = k1
        self._b = b
        self._chunks: list[Chunk] = []
        self._token_counts: list[Counter[str]] = []
        self._document_frequencies: Counter[str] = Counter()
        self._total_token_count = 0
        self.add_chunks(chunks)

    def add_chunks(
        self,
        chunks: Sequence[Chunk],
    ) -> int:
        existing_ids = {chunk.chunk_id for chunk in self._chunks}
        new_chunks: list[Chunk] = []

        for chunk in chunks:
            if chunk.chunk_id not in existing_ids:
                new_chunks.append(chunk)
                existing_ids.add(chunk.chunk_id)

        for chunk in new_chunks:
            token_counts = Counter(_tokenize(chunk.text))
            self._chunks.append(chunk)
            self._token_counts.append(token_counts)
            self._document_frequencies.update(token_counts.keys())
            self._total_token_count += sum(token_counts.values())

        return len(new_chunks)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("query must not be blank")

        if limit < 1:
            raise ValueError("limit must be at least 1")

        if not self._chunks:
            return []

        query_tokens = _tokenize(query)
        results = [
            SearchResult(
                chunk=chunk,
                score=self._score(token_counts, query_tokens),
            )
            for chunk, token_counts in zip(
                self._chunks,
                self._token_counts,
                strict=True,
            )
        ]
        results.sort(
            key=lambda result: (
                -result.score,
                result.chunk.chunk_id,
            )
        )

        return results[:limit]

    def _score(
        self,
        token_counts: Counter[str],
        query_tokens: Sequence[str],
    ) -> float:
        document_count = len(self._chunks)
        document_length = sum(token_counts.values())
        average_document_length = self._total_token_count / document_count
        score = 0.0

        for token in query_tokens:
            term_frequency = token_counts[token]

            if term_frequency == 0:
                continue

            document_frequency = self._document_frequencies[token]
            inverse_document_frequency = log(
                1.0 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            length_normalization = 1.0 - self._b

            if average_document_length > 0.0:
                length_normalization += self._b * document_length / average_document_length

            denominator = term_frequency + self._k1 * length_normalization
            score += inverse_document_frequency * term_frequency * (self._k1 + 1.0) / denominator

        return score


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())
