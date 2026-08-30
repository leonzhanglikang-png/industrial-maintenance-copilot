from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from backend.app.domain.documents import Chunk

Embedding = list[float]


class SearchResult(BaseModel):
    chunk: Chunk
    score: float


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[Embedding]: ...


@runtime_checkable
class ChunkIndexer(Protocol):
    def add_chunks(
        self,
        chunks: Sequence[Chunk],
    ) -> int: ...


@runtime_checkable
class Retriever(Protocol):
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]: ...


@runtime_checkable
class SearchIndex(Retriever, ChunkIndexer, Protocol):
    """A searchable index that also accepts new chunks."""


@runtime_checkable
class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        results: Sequence[SearchResult],
        *,
        limit: int = 5,
    ) -> list[SearchResult]: ...
