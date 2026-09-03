from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.answer_generators import (
    ExtractiveAnswerGenerator,
)
from backend.app.infrastructure.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from backend.app.infrastructure.hybrid_retriever import (
    ReciprocalRankFusionIndex,
)
from backend.app.infrastructure.keyword_retriever import (
    InMemoryBM25Retriever,
)
from backend.app.infrastructure.reranking import (
    RerankingSearchIndex,
    TokenOverlapReranker,
)
from backend.app.infrastructure.vector_retriever import (
    InMemoryVectorRetriever,
)
from backend.app.services.document_chunker import chunk_document
from backend.app.services.document_parser import parse_text_document
from backend.app.services.rag_answering import RagAnswerService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_MANUAL_PATH = PROJECT_ROOT / "data" / "raw" / "demo_pump_manual.md"


@lru_cache
def get_demo_chunks() -> tuple[Chunk, ...]:
    document = parse_text_document(DEMO_MANUAL_PATH)
    chunks = chunk_document(
        document,
        max_words=50,
        overlap_words=10,
    )

    return tuple(chunks)


def build_vector_retriever(
    chunks: Sequence[Chunk],
) -> InMemoryVectorRetriever:
    embedding_provider = DeterministicHashEmbeddingProvider(dimension=128)

    return InMemoryVectorRetriever(
        chunks,
        embedding_provider,
    )


def build_keyword_retriever(
    chunks: Sequence[Chunk],
) -> InMemoryBM25Retriever:
    return InMemoryBM25Retriever(chunks)


def build_hybrid_index(
    chunks: Sequence[Chunk],
) -> ReciprocalRankFusionIndex:
    return ReciprocalRankFusionIndex(
        [
            build_vector_retriever(chunks),
            build_keyword_retriever(chunks),
        ]
    )


def build_reranked_hybrid_index(
    chunks: Sequence[Chunk],
) -> RerankingSearchIndex:
    return RerankingSearchIndex(
        build_hybrid_index(chunks),
        TokenOverlapReranker(),
    )


@lru_cache
def get_retriever() -> RerankingSearchIndex:
    return build_reranked_hybrid_index(get_demo_chunks())


def get_rag_answer_service() -> RagAnswerService:
    return RagAnswerService(
        get_retriever(),
        ExtractiveAnswerGenerator(),
    )
