import pytest

from backend.app.domain.documents import Document, DocumentPage
from backend.app.services.document_chunker import chunk_document


def _make_text_document(text: str) -> Document:
    return Document(
        document_id="manual-001",
        source="pump_manual.md",
        content_type="text/markdown",
        text=text,
    )


def test_chunk_document_preserves_overlap_and_metadata() -> None:
    document = _make_text_document("one two three four five six seven")

    chunks = chunk_document(
        document,
        max_words=4,
        overlap_words=1,
    )

    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "four five six seven",
    ]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert all(chunk.source == "pump_manual.md" for chunk in chunks)
    assert all(chunk.page_number is None for chunk in chunks)


def test_chunk_ids_are_deterministic() -> None:
    document = _make_text_document("one two three four five six seven")

    first_result = chunk_document(
        document,
        max_words=4,
        overlap_words=1,
    )
    second_result = chunk_document(
        document,
        max_words=4,
        overlap_words=1,
    )

    assert [chunk.chunk_id for chunk in first_result] == [chunk.chunk_id for chunk in second_result]


def test_pdf_chunks_preserve_page_boundaries() -> None:
    document = Document(
        document_id="manual-001",
        source="pump_manual.pdf",
        content_type="application/pdf",
        text="one two three four five\n\nsix seven eight nine ten",
        pages=[
            DocumentPage(
                page_number=1,
                text="one two three four five",
            ),
            DocumentPage(
                page_number=3,
                text="six seven eight nine ten",
            ),
        ],
    )

    chunks = chunk_document(
        document,
        max_words=4,
        overlap_words=1,
    )

    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "four five",
        "six seven eight nine",
        "nine ten",
    ]
    assert [chunk.page_number for chunk in chunks] == [1, 1, 3, 3]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2, 3]


@pytest.mark.parametrize(
    ("max_words", "overlap_words", "message"),
    [
        (0, 0, "max_words"),
        (4, -1, "overlap_words"),
        (4, 4, "smaller"),
    ],
)
def test_chunk_document_rejects_invalid_settings(
    max_words: int,
    overlap_words: int,
    message: str,
) -> None:
    document = _make_text_document("one two three four")

    with pytest.raises(ValueError, match=message):
        chunk_document(
            document,
            max_words=max_words,
            overlap_words=overlap_words,
        )


def test_chunk_document_rejects_whitespace_only_text() -> None:
    document = _make_text_document("   \n   ")

    with pytest.raises(ValueError, match="no chunkable text"):
        chunk_document(document)
