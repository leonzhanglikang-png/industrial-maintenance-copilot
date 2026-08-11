from pathlib import Path

import pytest

from backend.app.services.document_parser import parse_text_document


def test_parse_markdown_document_normalizes_text(tmp_path: Path) -> None:
    path = tmp_path / "pump_manual.md"
    path.write_text(
        "# Pump\r\n\r\nCheck pressure.   \r\n",
        encoding="utf-8",
    )

    document = parse_text_document(path)

    assert document.source == "pump_manual.md"
    assert document.content_type == "text/markdown"
    assert document.text == "# Pump\n\nCheck pressure."
    assert document.document_id.startswith("doc-")


def test_parse_plain_text_document(tmp_path: Path) -> None:
    path = tmp_path / "inspection.txt"
    path.write_text("Inspect the motor bearing.", encoding="utf-8")

    document = parse_text_document(path)

    assert document.content_type == "text/plain"
    assert document.text == "Inspect the motor bearing."


def test_document_id_is_stable_and_content_sensitive(tmp_path: Path) -> None:
    path = tmp_path / "pump_manual.md"
    path.write_text("Check pressure.", encoding="utf-8")

    first_document = parse_text_document(path)
    second_document = parse_text_document(path)

    assert first_document.document_id == second_document.document_id

    path.write_text("Check temperature.", encoding="utf-8")
    changed_document = parse_text_document(path)

    assert changed_document.document_id != first_document.document_id


def test_parse_text_document_rejects_unsupported_extension(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pump_manual.pdf"
    path.write_text("PDF content", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported document type"):
        parse_text_document(path)


def test_parse_text_document_rejects_empty_text(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    path.write_text("\n   \n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not be empty"):
        parse_text_document(path)


def test_parse_text_document_rejects_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "invalid.txt"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(UnicodeDecodeError):
        parse_text_document(path)
