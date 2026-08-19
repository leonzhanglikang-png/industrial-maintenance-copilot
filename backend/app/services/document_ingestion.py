from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.domain.documents import Document
from backend.app.ports.retrieval import ChunkIndexer
from backend.app.services.document_chunker import chunk_document
from backend.app.services.document_parser import (
    parse_pdf_document,
    parse_text_document,
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SUPPORTED_UPLOAD_SUFFIXES = {".txt", ".md", ".pdf"}


@dataclass(frozen=True)
class IngestionResult:
    document: Document
    chunk_count: int
    indexed_chunk_count: int


def ingest_document(
    filename: str,
    content: bytes,
    indexer: ChunkIndexer,
) -> IngestionResult:
    safe_filename = _sanitize_filename(filename)
    suffix = Path(safe_filename).suffix.lower()

    if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
        raise ValueError(f"Unsupported document type: {suffix or 'no extension'}")

    if not content:
        raise ValueError("Uploaded document must not be empty")

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Uploaded document exceeds size limit")

    with TemporaryDirectory(prefix="maintenance-upload-") as directory:
        document_path = Path(directory) / safe_filename
        document_path.write_bytes(content)

        if suffix == ".pdf":
            document = parse_pdf_document(document_path)
        else:
            document = parse_text_document(document_path)

    chunks = chunk_document(
        document,
        max_words=50,
        overlap_words=10,
    )
    indexed_chunk_count = indexer.add_chunks(chunks)

    return IngestionResult(
        document=document,
        chunk_count=len(chunks),
        indexed_chunk_count=indexed_chunk_count,
    )


def _sanitize_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    safe_filename = Path(normalized).name.strip()

    if not safe_filename or safe_filename in {".", ".."}:
        raise ValueError("filename must not be empty")

    return safe_filename
