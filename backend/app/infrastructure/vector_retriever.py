from collections.abc import Sequence
from math import sqrt

from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import EmbeddingProvider, SearchResult


def cosine_similarity(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")

    dot_product = sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=True)
    )
    left_magnitude = sqrt(sum(value * value for value in left))
    right_magnitude = sqrt(sum(value * value for value in right))

    if left_magnitude == 0.0 or right_magnitude == 0.0:
        return 0.0

    return dot_product / (left_magnitude * right_magnitude)


class InMemoryVectorRetriever:
    def __init__(
        self,
        chunks: Sequence[Chunk],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._chunks = list(chunks)
        self._vectors = embedding_provider.embed([chunk.text for chunk in self._chunks])

        if len(self._vectors) != len(self._chunks):
            raise ValueError("embedding provider returned unexpected vector count")

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

        query_vector = self._embedding_provider.embed([query])[0]

        results = [
            SearchResult(
                chunk=chunk,
                score=cosine_similarity(query_vector, vector),
            )
            for chunk, vector in zip(
                self._chunks,
                self._vectors,
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
