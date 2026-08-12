from pathlib import Path

import pytest
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from backend.app.services.document_parser import parse_pdf_document


def _write_pdf_with_blank_middle_page(path: Path) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 720, "Page one: check pump pressure.")
    pdf.showPage()

    pdf.showPage()

    pdf.drawString(72, 720, "Page three: inspect the seal.")
    pdf.save()


def test_parse_pdf_document_preserves_real_page_numbers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pump_manual.pdf"
    _write_pdf_with_blank_middle_page(path)

    document = parse_pdf_document(path)

    assert document.source == "pump_manual.pdf"
    assert document.content_type == "application/pdf"
    assert document.text == ("Page one: check pump pressure.\n\nPage three: inspect the seal.")
    assert [page.page_number for page in document.pages] == [1, 3]
    assert document.pages[0].text == "Page one: check pump pressure."
    assert document.pages[1].text == "Page three: inspect the seal."


def test_pdf_document_id_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "pump_manual.pdf"
    _write_pdf_with_blank_middle_page(path)

    first_document = parse_pdf_document(path)
    second_document = parse_pdf_document(path)

    assert first_document.document_id == second_document.document_id


def test_parse_pdf_document_rejects_blank_pdf(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    with path.open("wb") as output:
        writer.write(output)

    with pytest.raises(ValueError, match="no extractable text"):
        parse_pdf_document(path)


def test_parse_pdf_document_rejects_corrupted_pdf(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is not a valid PDF")

    with pytest.raises(ValueError, match="Unable to read PDF"):
        parse_pdf_document(path)


def test_parse_pdf_document_rejects_non_pdf_extension(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manual.txt"
    path.write_text("Not a PDF", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a PDF"):
        parse_pdf_document(path)
