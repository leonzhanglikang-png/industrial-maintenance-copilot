import pytest
from backend.app.services.document_ingestion import (
    MAX_UPLOAD_BYTES,
    ingest_document,
)

from backend.app.infrastructure.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from backend.app.infrastructure.vector_retriever import (
    InMemoryVectorRetriever,
)


def make_retriever() -> InMemoryVectorRetriever:
    provider = DeterministicHashEmbeddingProvider(dimension=64)
    return InMemoryVectorRetriever([], provider)


def test_ingest_document_indexes_markdown_content() -> None:
    retriever = make_retriever()

    result = ingest_document(
        "compressor_manual.md",
        b"Check compressor oil pressure before startup.",
        retriever,
    )
    search_results = retriever.search(
        "compressor oil pressure",
        limit=1,
    )

    assert result.document.source == "compressor_manual.md"
    assert result.document.content_type == "text/markdown"
    assert result.chunk_count == 1
    assert result.indexed_chunk_count == 1
    assert search_results[0].chunk.source == "compressor_manual.md"


def test_ingest_document_does_not_duplicate_chunks() -> None:
    retriever = make_retriever()
    content = b"Inspect the cooling fan before startup."

    first = ingest_document(
        "cooling_manual.txt",
        content,
        retriever,
    )
    second = ingest_document(
        "cooling_manual.txt",
        content,
        retriever,
    )

    assert first.indexed_chunk_count == 1
    assert second.chunk_count == 1
    assert second.indexed_chunk_count == 0


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("manual.csv", b"unsupported", "Unsupported"),
        ("manual.md", b"", "empty"),
        (
            "manual.md",
            b"x" * (MAX_UPLOAD_BYTES + 1),
            "size limit",
        ),
    ],
)
def test_ingest_document_rejects_invalid_upload(
    filename: str,
    content: bytes,
    message: str,
) -> None:
    retriever = make_retriever()

    with pytest.raises(ValueError, match=message):
        ingest_document(
            filename,
            content,
            retriever,
        )
