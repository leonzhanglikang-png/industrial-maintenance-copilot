from hashlib import sha256
from pathlib import Path

from backend.app.domain.documents import Document

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


def _normalize_text(text: str) -> str:
    normalized_lines = (line.rstrip() for line in text.splitlines())
    return "\n".join(normalized_lines).strip("\n")


def _build_document_id(source: str, text: str) -> str:
    payload = f"{source}\0{text}".encode()
    return f"doc-{sha256(payload).hexdigest()}"
