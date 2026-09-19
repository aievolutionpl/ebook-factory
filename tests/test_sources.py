import shutil

import pytest

from ebook_factory.artifacts import build_pdf
from ebook_factory.sources import (
    MAX_SOURCE_FILE_BYTES,
    MAX_SOURCE_FILES_PER_PROJECT,
    SourceUploadError,
    count_existing_source_files,
    extract_text,
    sanitize_source_filename,
    store_source_file,
)

CHAPTERS = [("Rozdzial 1", "<p>Tresc akapitu z unikalnym fragmentem ZQX987.</p>")]


def _pdf_with_text(path):
    build_pdf(path, title="Tytul", chapters=CHAPTERS, typst_binary=None)
    return path


def test_sanitize_source_filename_strips_posix_traversal():
    assert sanitize_source_filename("../../etc/passwd.txt") == "passwd.txt"


def test_sanitize_source_filename_strips_windows_traversal():
    assert sanitize_source_filename("..\\..\\secrets.txt") == "secrets.txt"


def test_sanitize_source_filename_removes_unsafe_characters():
    result = sanitize_source_filename('weird name?*<>|.txt')
    assert "/" not in result
    assert "\\" not in result
    assert result.endswith(".txt")


def test_sanitize_source_filename_falls_back_when_name_is_only_dots():
    assert sanitize_source_filename("..") == "file"


def test_store_source_file_accepts_txt_and_writes_under_sources_dir(tmp_path):
    project_dir = tmp_path / "my-project"
    dest = store_source_file(project_dir, "notes.txt", b"hello world")

    assert dest.is_file()
    assert dest.parent == project_dir / "sources"
    assert dest.read_bytes() == b"hello world"


def test_store_source_file_accepts_md_extension(tmp_path):
    project_dir = tmp_path / "my-project"
    dest = store_source_file(project_dir, "notes.md", b"# heading")
    assert dest.suffix == ".md"


def test_store_source_file_accepts_pdf_extension(tmp_path):
    project_dir = tmp_path / "my-project"
    dest = store_source_file(project_dir, "notes.pdf", b"%PDF-1.4\n%%EOF")
    assert dest.suffix == ".pdf"


def test_store_source_file_rejects_fake_pdf_content(tmp_path):
    project_dir = tmp_path / "my-project"
    with pytest.raises(SourceUploadError, match="PDF signature"):
        store_source_file(project_dir, "notes.pdf", b"not really a pdf")


def test_store_source_file_rejects_binary_disguised_as_text(tmp_path):
    project_dir = tmp_path / "my-project"
    with pytest.raises(SourceUploadError, match="UTF-8 text"):
        store_source_file(project_dir, "notes.txt", b"\x00\xff\x00\xfe")


def test_store_source_file_rejects_unsupported_extension(tmp_path):
    project_dir = tmp_path / "my-project"
    with pytest.raises(SourceUploadError):
        store_source_file(project_dir, "script.exe", b"binary")
    assert not (project_dir / "sources").exists() or not any(
        (project_dir / "sources").iterdir()
    )


def test_store_source_file_rejects_empty_file(tmp_path):
    project_dir = tmp_path / "my-project"
    with pytest.raises(SourceUploadError):
        store_source_file(project_dir, "empty.txt", b"")


def test_store_source_file_rejects_oversize_file(tmp_path):
    project_dir = tmp_path / "my-project"
    too_big = b"a" * (MAX_SOURCE_FILE_BYTES + 1)
    with pytest.raises(SourceUploadError):
        store_source_file(project_dir, "big.txt", too_big)


def test_store_source_file_accepts_file_at_max_size(tmp_path):
    project_dir = tmp_path / "my-project"
    exactly_max = b"a" * MAX_SOURCE_FILE_BYTES
    dest = store_source_file(project_dir, "max.txt", exactly_max)
    assert dest.stat().st_size == MAX_SOURCE_FILE_BYTES


def test_store_source_file_confines_traversal_name_under_sources_dir(tmp_path):
    project_dir = tmp_path / "my-project"
    dest = store_source_file(project_dir, "../../etc/passwd.txt", b"content")

    assert dest.parent == project_dir / "sources"
    assert not (tmp_path / "etc").exists()


def test_store_source_file_avoids_overwriting_existing_file_with_same_name(tmp_path):
    project_dir = tmp_path / "my-project"
    first = store_source_file(project_dir, "notes.txt", b"first")
    second = store_source_file(project_dir, "notes.txt", b"second")

    assert first != second
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"


def test_count_existing_source_files_counts_files_in_sources_dir(tmp_path):
    project_dir = tmp_path / "my-project"
    assert count_existing_source_files(project_dir) == 0
    store_source_file(project_dir, "a.txt", b"one")
    store_source_file(project_dir, "b.txt", b"two")
    assert count_existing_source_files(project_dir) == 2


def test_max_source_files_per_project_constant_is_five():
    assert MAX_SOURCE_FILES_PER_PROJECT == 5


def test_extract_text_reads_utf8_txt(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Zażółć gęślą jaźń — unikalny fragment ZQX987", encoding="utf-8")

    text, status = extract_text(path)

    assert status == "extracted"
    assert "ZQX987" in text


def test_extract_text_reads_utf8_md(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# Heading\n\nUnikalny fragment ZQX987", encoding="utf-8")

    text, status = extract_text(path)

    assert status == "extracted"
    assert "ZQX987" in text


def test_extract_text_reports_empty_status_for_blank_file(tmp_path):
    path = tmp_path / "blank.txt"
    path.write_text("   \n\n  ", encoding="utf-8")

    text, status = extract_text(path)

    assert status == "empty"


def test_extract_text_pdf_uses_pdftotext_when_available(tmp_path):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not installed")
    path = _pdf_with_text(tmp_path / "book.pdf")

    text, status = extract_text(path)

    assert status == "extracted"
    assert "ZQX987" in text


def test_extract_text_pdf_returns_unavailable_when_pdftotext_missing(tmp_path, monkeypatch):
    path = _pdf_with_text(tmp_path / "book.pdf")
    monkeypatch.setattr(shutil, "which", lambda name: None)

    text, status = extract_text(path)

    assert text is None
    assert status == "unavailable"
