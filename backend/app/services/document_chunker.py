from hashlib import sha256

from backend.app.domain.documents import Chunk, Document


def chunk_document(
    document: Document,
    *,
    max_words: int = 120,
    overlap_words: int = 20,
) -> list[Chunk]:
    _validate_chunk_settings(max_words, overlap_words)

    text_sources = (
        [(page.page_number, page.text) for page in document.pages]
        if document.pages
        else [(None, document.text)]
    )

    chunks: list[Chunk] = []

    for page_number, text in text_sources:
        for chunk_text in _split_text(text, max_words, overlap_words):
            chunk_index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=_build_chunk_id(
                        document.document_id,
                        chunk_index,
                        chunk_text,
                    ),
                    document_id=document.document_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    source=document.source,
                    page_number=page_number,
                )
            )

    if not chunks:
        raise ValueError("Document contains no chunkable text")

    return chunks


def _split_text(
    text: str,
    max_words: int,
    overlap_words: int,
) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))

        if end == len(words):
            break

        start = end - overlap_words

    return chunks


def _validate_chunk_settings(
    max_words: int,
    overlap_words: int,
) -> None:
    if max_words < 1:
        raise ValueError("max_words must be at least 1")

    if overlap_words < 0:
        raise ValueError("overlap_words must not be negative")

    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")


def _build_chunk_id(
    document_id: str,
    chunk_index: int,
    text: str,
) -> str:
    payload = f"{document_id}\0{chunk_index}\0{text}".encode()
    return f"chunk-{sha256(payload).hexdigest()}"
