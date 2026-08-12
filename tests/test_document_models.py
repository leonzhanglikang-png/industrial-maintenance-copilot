import pytest
from pydantic import ValidationError

from backend.app.domain.documents import Chunk, Document, DocumentPage


def test_document_accepts_valid_data() -> None:
    document = Document(
        document_id="manual-001",
        source="pump_manual.md",
        content_type="text/markdown",
        text="Check pump pressure.",
    )

    assert document.document_id == "manual-001"
    assert document.source == "pump_manual.md"


def test_document_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        Document(
            document_id="",
            source="pump_manual.md",
            content_type="text/markdown",
            text="Check pump pressure.",
        )


def test_document_rejects_unsupported_content_type() -> None:
    with pytest.raises(ValidationError):
        Document(
            document_id="manual-001",
            source="pump_manual.md",
            content_type="application/json",
            text="Check pump pressure.",
        )


def test_chunk_accepts_citation_metadata() -> None:
    chunk = Chunk(
        chunk_id="manual-001-chunk-0",
        document_id="manual-001",
        text="Check pump pressure.",
        chunk_index=0,
        source="pump_manual.pdf",
        page_number=3,
        section="Troubleshooting",
    )

    assert chunk.document_id == "manual-001"
    assert chunk.page_number == 3
    assert chunk.section == "Troubleshooting"


def test_chunk_rejects_negative_index() -> None:
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="manual-001-chunk-0",
            document_id="manual-001",
            text="Check pump pressure.",
            chunk_index=-1,
            source="pump_manual.md",
        )


def test_chunk_rejects_page_number_zero() -> None:
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="manual-001-chunk-0",
            document_id="manual-001",
            text="Check pump pressure.",
            chunk_index=0,
            source="pump_manual.pdf",
            page_number=0,
        )


def test_pdf_document_preserves_page_text() -> None:
    document = Document(
        document_id="manual-001",
        source="pump_manual.pdf",
        content_type="application/pdf",
        text="Page one.\n\nPage three.",
        pages=[
            DocumentPage(page_number=1, text="Page one."),
            DocumentPage(page_number=3, text="Page three."),
        ],
    )

    assert document.pages[0].page_number == 1
    assert document.pages[1].page_number == 3


def test_document_page_rejects_page_number_zero() -> None:
    with pytest.raises(ValidationError):
        DocumentPage(page_number=0, text="Invalid page.")
