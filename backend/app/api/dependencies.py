from collections.abc import Sequence
from functools import lru_cache, partial
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.core.errors import ModelConfigurationError
from backend.app.domain.documents import Chunk
from backend.app.infrastructure.answer_generators import (
    ExtractiveAnswerGenerator,
)
from backend.app.infrastructure.chat_answer_generator import ChatCompletionsAnswerGenerator
from backend.app.infrastructure.chunk_store import SQLiteChunkStore
from backend.app.infrastructure.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from backend.app.infrastructure.hybrid_retriever import (
    ReciprocalRankFusionIndex,
)
from backend.app.infrastructure.keyword_retriever import (
    InMemoryBM25Retriever,
)
from backend.app.infrastructure.local_embeddings import LocalSemanticEmbeddingProvider
from backend.app.infrastructure.maintenance_tools import (
    FaultHistoryLookupTool,
    SensorRangeAnalysisTool,
)
from backend.app.infrastructure.openai_answer_generator import (
    OpenAIResponsesAnswerGenerator,
)
from backend.app.infrastructure.openai_embeddings import OpenAIEmbeddingProvider
from backend.app.infrastructure.persistent_retriever import PersistentSearchIndex
from backend.app.infrastructure.reranking import (
    RerankingSearchIndex,
    TokenOverlapReranker,
)
from backend.app.infrastructure.vector_retriever import (
    InMemoryVectorRetriever,
)
from backend.app.ports.answering import AnswerGenerator
from backend.app.ports.retrieval import EmbeddingProvider
from backend.app.services.document_chunker import chunk_document
from backend.app.services.document_parser import parse_text_document
from backend.app.services.maintenance_agent import BoundedMaintenanceAgent
from backend.app.services.rag_answering import RagAnswerService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_MANUAL_PATH = PROJECT_ROOT / "data" / "raw" / "demo_pump_manual.md"
FAULT_HISTORY_PATH = PROJECT_ROOT / "data" / "demo" / "fault_history.json"


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
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> InMemoryVectorRetriever:
    if embedding_provider is None:
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
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> ReciprocalRankFusionIndex:
    return ReciprocalRankFusionIndex(
        [
            build_vector_retriever(chunks, embedding_provider=embedding_provider),
            build_keyword_retriever(chunks),
        ]
    )


def build_reranked_hybrid_index(
    chunks: Sequence[Chunk],
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> RerankingSearchIndex:
    return RerankingSearchIndex(
        build_hybrid_index(chunks, embedding_provider=embedding_provider),
        TokenOverlapReranker(),
    )


def build_embedding_provider(provider: str | None = None) -> EmbeddingProvider:
    settings = get_settings()
    selected = settings.embedding_provider if provider is None else provider
    if selected == "hash":
        return DeterministicHashEmbeddingProvider(dimension=128)
    if selected == "local":
        model_path = settings.embedding_local_path
        if not model_path.is_absolute():
            model_path = PROJECT_ROOT / model_path
        return LocalSemanticEmbeddingProvider(model_path)
    if selected != "openai":
        raise ModelConfigurationError("Unsupported embedding provider")
    api_key = (
        settings.embedding_api_key.get_secret_value().strip() if settings.embedding_api_key else ""
    )
    if (
        not api_key
        or not settings.embedding_model.strip()
        or not settings.embedding_base_url.strip()
    ):
        raise ModelConfigurationError(
            "EMBEDDING_API_KEY, EMBEDDING_MODEL and EMBEDDING_BASE_URL are required"
        )
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        base_url=settings.embedding_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


@lru_cache
def get_retriever() -> PersistentSearchIndex:
    provider = build_embedding_provider()
    store_path = get_settings().chunk_store_path
    if not store_path.is_absolute():
        store_path = PROJECT_ROOT / store_path
    return PersistentSearchIndex(
        SQLiteChunkStore(store_path),
        partial(build_reranked_hybrid_index, embedding_provider=provider),
        get_demo_chunks(),
    )


@lru_cache
def get_answer_generator() -> AnswerGenerator:
    settings = get_settings()

    if settings.answer_generator == "extractive":
        return ExtractiveAnswerGenerator()

    api_key = (
        settings.llm_api_key.get_secret_value().strip() if settings.llm_api_key is not None else ""
    )
    model = (settings.llm_model or "").strip()

    if not api_key or not model:
        raise ModelConfigurationError(
            "LLM_API_KEY and LLM_MODEL are required for remote answer generation"
        )

    if not settings.llm_base_url.strip():
        raise ModelConfigurationError("LLM_BASE_URL must not be blank")
    if settings.answer_generator == "chat_completions":
        return ChatCompletionsAnswerGenerator(
            api_key=api_key,
            model=model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.chat_max_tokens,
            disable_thinking=settings.chat_disable_thinking,
        )

    return OpenAIResponsesAnswerGenerator(
        api_key=api_key,
        model=model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def get_rag_answer_service() -> RagAnswerService:
    return RagAnswerService(
        get_retriever(),
        get_answer_generator(),
    )


@lru_cache
def get_fault_history_tool() -> FaultHistoryLookupTool:
    return FaultHistoryLookupTool.from_json_file(FAULT_HISTORY_PATH)


@lru_cache
def get_sensor_analysis_tool() -> SensorRangeAnalysisTool:
    return SensorRangeAnalysisTool()


def get_maintenance_agent() -> BoundedMaintenanceAgent:
    settings = get_settings()
    return BoundedMaintenanceAgent(
        get_rag_answer_service(),
        get_fault_history_tool(),
        get_sensor_analysis_tool(),
        max_steps=settings.agent_max_steps,
    )
