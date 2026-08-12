from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.app.domain.documents import Document, DocumentPage

CONTENT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def parse_text_document(path: Path) -> Document:
    suffix = path.suffix.lower()
    if suffix not in CONTENT_TYPES:
        raise ValueError(f"Unsupported document type: {suffix or 'no extension'}")

    raw_text = path.read_text(encoding="utf-8")
    text = _normalize_text(raw_text)

    if not text:
        raise ValueError("Document text must not be empty")

    return Document(
        document_id=_build_document_id(path.name, text),
        source=path.name,
        content_type=CONTENT_TYPES[suffix],
        text=text,
    )


def parse_pdf_document(path: Path) -> Document:
    if path.suffix.lower() != ".pdf":
        raise ValueError("Expected a PDF document")

    try:
        reader = PdfReader(path)
        pages: list[DocumentPage] = []

        for page_number, pdf_page in enumerate(reader.pages, start=1):
            text = _normalize_text(pdf_page.extract_text() or "")

            if text:
                pages.append(
                    DocumentPage(
                        page_number=page_number,
                        text=text,
                    )
                )
    except (OSError, PdfReadError) as exc:
        raise ValueError("Unable to read PDF document") from exc

    if not pages:
        raise ValueError("PDF document contains no extractable text")

    full_text = "\n\n".join(page.text for page in pages)

    return Document(
        document_id=_build_document_id(path.name, full_text),
        source=path.name,
        content_type="application/pdf",
        text=full_text,
        pages=pages,
    )


def _normalize_text(text: str) -> str:
    normalized_lines = (line.rstrip() for line in text.splitlines())
    return "\n".join(normalized_lines).strip("\n")


def _build_document_id(source: str, text: str) -> str:
    payload = f"{source}\0{text}".encode()
    return f"doc-{sha256(payload).hexdigest()}"
