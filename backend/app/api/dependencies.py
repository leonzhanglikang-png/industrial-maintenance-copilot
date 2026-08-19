from functools import lru_cache
from pathlib import Path

from backend.app.infrastructure.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from backend.app.infrastructure.vector_retriever import (
    InMemoryVectorRetriever,
)
from backend.app.services.document_chunker import chunk_document
from backend.app.services.document_parser import parse_text_document

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_MANUAL_PATH = PROJECT_ROOT / "data" / "raw" / "demo_pump_manual.md"


@lru_cache
def get_retriever() -> InMemoryVectorRetriever:
    document = parse_text_document(DEMO_MANUAL_PATH)
    chunks = chunk_document(
        document,
        max_words=50,
        overlap_words=10,
    )
    embedding_provider = DeterministicHashEmbeddingProvider(dimension=128)

    return InMemoryVectorRetriever(
        chunks,
        embedding_provider,
    )
