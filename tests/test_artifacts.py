import hashlib
import zipfile

import pytest

from ebook_factory.artifacts import (
    build_cover_png,
    build_cover_svg,
    build_delivery_zip,
    build_epub,
    build_manifest,
    build_pdf,
)

CHAPTERS = [
    ("Rozdzial 1: Wprowadzenie", "<p>To jest przykladowy akapit numer jeden.</p>"),
    ("Rozdzial 2: Rozwiniecie", "<p>To jest przykladowy akapit numer dwa.</p>"),
]


def test_epub_starts_with_uncompressed_mimetype(tmp_path):
    output = tmp_path / "book.epub"
    build_epub(output, title="Tytul", author="Ebook Factory", language="pl", chapters=CHAPTERS)

    with zipfile.ZipFile(output) as zf:
        first_info = zf.infolist()[0]
        assert first_info.filename == "mimetype"
        assert first_info.compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"


def test_epub_contains_required_structural_files(tmp_path):
    output = tmp_path / "book.epub"
    build_epub(output, title="Tytul", author="Ebook Factory", language="pl", chapters=CHAPTERS)

    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
    assert "META-INF/container.xml" in names
    assert any(name.endswith("content.opf") for name in names)
    assert any(name.endswith("nav.xhtml") for name in names)
    chapter_files = [n for n in names if "chapter" in n and n.endswith(".xhtml")]
    assert len(chapter_files) == len(CHAPTERS)


def test_pdf_fallback_engine_starts_with_pdf_header_and_has_text(tmp_path):
    output = tmp_path / "book.pdf"
    result_path, engine = build_pdf(output, title="Tytul", chapters=CHAPTERS, typst_binary=None)
    assert result_path == output
    assert engine == "fallback-stdlib"
    data = output.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"/Page" in data


def test_pdf_typst_engine_when_binary_available(tmp_path):
    typst_binary = "/home/aibot/.local/bin/typst"
    import shutil

    if shutil.which(typst_binary) is None:
        pytest.skip("typst binary not installed in this environment")
    output = tmp_path / "book.pdf"
    result_path, engine = build_pdf(
        output, title="Tytul", chapters=CHAPTERS, typst_binary=typst_binary
    )
    assert result_path == output
    assert engine == "typst"
    assert output.read_bytes().startswith(b"%PDF")


def test_cover_svg_contains_title_and_no_external_refs():
    svg = build_cover_svg(title="Moj Ebook", subtitle="Podtytul", brand="Marka", mode="guide")
    assert "<svg" in svg
    assert "Moj Ebook" in svg
    assert "<image" not in svg
    assert "xlink:href=\"http" not in svg
    assert "@import" not in svg


def test_cover_png_is_valid_image(tmp_path):
    output = tmp_path / "cover.png"
    build_cover_png(output, title="Moj Ebook", subtitle="Podtytul", brand="Marka", mode="guide")
    data = output.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 500


def test_manifest_contains_sha256_for_every_file(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("hello")
    file_b.write_text("world")

    manifest = build_manifest({"a.txt": file_a, "b.txt": file_b})

    expected_a = hashlib.sha256(b"hello").hexdigest()
    by_name = {entry["name"]: entry for entry in manifest["files"]}
    assert by_name["a.txt"]["sha256"] == expected_a
    assert by_name["b.txt"]["sha256"] == hashlib.sha256(b"world").hexdigest()
    assert set(by_name) == {"a.txt", "b.txt"}


def test_delivery_zip_contains_required_filenames(tmp_path):
    delivery_dir = tmp_path / "delivery"
    delivery_dir.mkdir()
    required = ["book.pdf", "book.epub", "cover.png", "manifest.json"]
    for name in required:
        (delivery_dir / name).write_bytes(b"demo content")

    output_zip = tmp_path / "delivery.zip"
    build_delivery_zip(delivery_dir, output_zip, required)

    with zipfile.ZipFile(output_zip) as zf:
        names = set(zf.namelist())
    assert set(required).issubset(names)
