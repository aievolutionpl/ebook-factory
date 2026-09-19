import shutil

import pytest

from ebook_factory.artifacts import build_pdf
from ebook_factory.pdfcheck import check_pdf

CHAPTERS = [
    ("Rozdzial 1", "<p>Pierwszy akapit z sensowna trescia do wyekstrahowania.</p>"),
    ("Rozdzial 2", "<p>Drugi akapit z inna trescia do sprawdzenia.</p>"),
]


def test_check_pdf_reports_pages_and_text_for_fallback_engine(tmp_path):
    output = tmp_path / "book.pdf"
    build_pdf(output, title="Tytul", chapters=CHAPTERS, typst_binary=None)

    result = check_pdf(output)

    assert result.page_count > 0
    assert result.has_text is True


def test_check_pdf_detects_zero_pages_and_no_text_for_broken_pdf(tmp_path):
    output = tmp_path / "broken.pdf"
    output.write_bytes(b"%PDF-1.4\n%%EOF")

    result = check_pdf(output)

    assert result.page_count == 0
    assert result.has_text is False


def test_check_pdf_falls_back_to_stdlib_parser_when_poppler_missing(tmp_path, monkeypatch):
    output = tmp_path / "book.pdf"
    build_pdf(output, title="Tytul", chapters=CHAPTERS, typst_binary=None)

    monkeypatch.setattr(shutil, "which", lambda name: None)

    result = check_pdf(output)

    assert result.method == "fallback-parser"
    assert result.page_count > 0
    assert result.has_text is True


@pytest.mark.skipif(
    shutil.which("pdfinfo") is None or shutil.which("pdftotext") is None,
    reason="poppler-utils not installed",
)
def test_check_pdf_uses_poppler_when_available(tmp_path):
    output = tmp_path / "book.pdf"
    build_pdf(output, title="Tytul", chapters=CHAPTERS, typst_binary=None)

    result = check_pdf(output)

    assert result.method == "poppler"
    assert result.page_count > 0
    assert result.has_text is True
