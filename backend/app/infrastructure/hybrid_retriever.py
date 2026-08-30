from collections import defaultdict
from collections.abc import Sequence

from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import SearchIndex, SearchResult


class ReciprocalRankFusionIndex:
    def __init__(
        self,
        indexes: Sequence[SearchIndex],
        *,
        rrf_k: int = 60,
        candidate_multiplier: int = 4,
    ) -> None:
        if len(indexes) < 2:
            raise ValueError("RRF requires at least two indexes")

        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")

        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be at least 1")

        self._indexes = tuple(indexes)
        self._rrf_k = rrf_k
        self._candidate_multiplier = candidate_multiplier

    def add_chunks(
        self,
        chunks: Sequence[Chunk],
    ) -> int:
        added_counts = [index.add_chunks(chunks) for index in self._indexes]
        return max(added_counts, default=0)

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

        candidate_limit = limit * self._candidate_multiplier
        fused_scores: defaultdict[str, float] = defaultdict(float)
        chunks_by_id: dict[str, Chunk] = {}

        for index in self._indexes:
            seen_chunk_ids: set[str] = set()
            source_results = index.search(
                query,
                limit=candidate_limit,
            )

            for rank, result in enumerate(source_results, start=1):
                chunk_id = result.chunk.chunk_id

                if chunk_id in seen_chunk_ids:
                    continue

                seen_chunk_ids.add(chunk_id)
                chunks_by_id.setdefault(chunk_id, result.chunk)
                fused_scores[chunk_id] += 1.0 / (self._rrf_k + rank)

        results = [
            SearchResult(
                chunk=chunks_by_id[chunk_id],
                score=score,
            )
            for chunk_id, score in fused_scores.items()
        ]
        results.sort(
            key=lambda result: (
                -result.score,
                result.chunk.chunk_id,
            )
        )

        return results[:limit]
