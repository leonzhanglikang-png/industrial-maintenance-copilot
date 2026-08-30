import re
from collections.abc import Sequence

from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import Reranker, SearchIndex, SearchResult

TOKEN_PATTERN = re.compile(r"\w+")


class TokenOverlapReranker:
    def rerank(
        self,
        query: str,
        results: Sequence[SearchResult],
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("query must not be blank")

        if limit < 1:
            raise ValueError("limit must be at least 1")

        query_tokens = _tokenize(query)

        if not query_tokens:
            return list(results[:limit])

        query_token_set = set(query_tokens)
        normalized_query = " ".join(query_tokens)
        reranked_results: list[SearchResult] = []

        for original_rank, result in enumerate(results, start=1):
            chunk_tokens = _tokenize(result.chunk.text)
            chunk_token_set = set(chunk_tokens)
            overlap_count = len(query_token_set & chunk_token_set)
            query_coverage = overlap_count / len(query_token_set)
            exact_phrase_bonus = 0.25 if normalized_query in " ".join(chunk_tokens) else 0.0
            rank_tiebreaker = 1.0 / (1000 + original_rank)

            reranked_results.append(
                SearchResult(
                    chunk=result.chunk,
                    score=query_coverage + exact_phrase_bonus + rank_tiebreaker,
                )
            )

        reranked_results.sort(
            key=lambda result: (
                -result.score,
                result.chunk.chunk_id,
            )
        )
        return reranked_results[:limit]


class RerankingSearchIndex:
    def __init__(
        self,
        index: SearchIndex,
        reranker: Reranker,
        *,
        candidate_multiplier: int = 4,
    ) -> None:
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be at least 1")

        self._index = index
        self._reranker = reranker
        self._candidate_multiplier = candidate_multiplier

    def add_chunks(
        self,
        chunks: Sequence[Chunk],
    ) -> int:
        return self._index.add_chunks(chunks)

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

        candidates = self._index.search(
            query,
            limit=limit * self._candidate_multiplier,
        )
        return self._reranker.rerank(
            query,
            candidates,
            limit=limit,
        )


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.casefold())
