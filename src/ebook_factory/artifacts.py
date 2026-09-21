"""Real, dependency-light artifact generation: EPUB, PDF, cover, manifest, ZIP.

No paid external APIs. PDF uses Typst when a binary is available, otherwise a
minimal pure-stdlib PDF writer. Cover PNG uses Pillow (bundled bitmap font,
no network/font downloads).
"""

from __future__ import annotations

import hashlib
import html
import shutil
import subprocess
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont

Chapter = tuple[str, str]


# --------------------------------------------------------------------------
# EPUB
# --------------------------------------------------------------------------

_CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _chapter_filename(index: int) -> str:
    return f"chapter-{index + 1:02d}.xhtml"


def _chapter_xhtml(title: str, body_html: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{html.escape(title)}</title></head>
<body>
<h1>{html.escape(title)}</h1>
{body_html}
</body>
</html>
"""


def _content_opf(title: str, author: str, language: str, chapters: list[Chapter], book_id: str) -> str:
    manifest_items = "\n".join(
        f'    <item id="chap{i + 1}" href="{_chapter_filename(i)}" media-type="application/xhtml+xml"/>'
        for i in range(len(chapters))
    )
    spine_items = "\n".join(f'    <itemref idref="chap{i + 1}"/>' for i in range(len(chapters)))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{html.escape(book_id)}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:language>{html.escape(language)}</dc:language>
    <dc:creator>{html.escape(author)}</dc:creator>
    <meta property="dcterms:modified">{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
{manifest_items}
  </manifest>
  <spine>
{spine_items}
  </spine>
</package>
"""


def _nav_xhtml(title: str, chapters: list[Chapter]) -> str:
    entries = "\n".join(
        f'      <li><a href="{_chapter_filename(i)}">{html.escape(chap_title)}</a></li>'
        for i, (chap_title, _body) in enumerate(chapters)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>{html.escape(title)}</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{html.escape(title)}</h1>
    <ol>
{entries}
    </ol>
  </nav>
</body>
</html>
"""


def build_epub(
    output_path: Path,
    title: str,
    author: str,
    language: str,
    chapters: list[Chapter],
    book_id: Optional[str] = None,
) -> Path:
    """Build an EPUB 3 file with a correctly uncompressed `mimetype` entry."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    book_id = book_id or f"urn:uuid:{hashlib.sha1(title.encode('utf-8')).hexdigest()}"

    with zipfile.ZipFile(output_path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _CONTAINER_XML, zipfile.ZIP_DEFLATED)
        zf.writestr(
            "OEBPS/content.opf",
            _content_opf(title, author, language, chapters, book_id),
            zipfile.ZIP_DEFLATED,
        )
        zf.writestr("OEBPS/nav.xhtml", _nav_xhtml(title, chapters), zipfile.ZIP_DEFLATED)
        for i, (chap_title, body_html) in enumerate(chapters):
            zf.writestr(
                f"OEBPS/{_chapter_filename(i)}",
                _chapter_xhtml(chap_title, body_html),
                zipfile.ZIP_DEFLATED,
            )
    return output_path


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap_plain_text(body_html: str, width: int = 92) -> list[str]:
    plain = (
        body_html.replace("<p>", "")
        .replace("</p>", "\n")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
    )
    plain = html.unescape(plain)
    lines: list[str] = []
    for raw_line in plain.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw_line, width=width) or [""])
    return lines


#: Base-14 Helvetica can only carry latin-1, so Polish letters would come out
#: of the fallback writer as question marks. Folding them to their ASCII base
#: keeps the emergency PDF readable; the typst engine renders them properly.
_PDF_TRANSLITERATION = str.maketrans(
    {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o",
        "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O",
        "Ś": "S", "Ź": "Z", "Ż": "Z",
        "„": '"', "”": '"', "“": '"', "’": "'", "‘": "'",
        "—": "-", "–": "-", "…": "...", "\u00a0": " ",
    }
)


def _pdf_safe(text: str) -> str:
    """Fold text into what the stdlib PDF writer can actually encode."""
    return text.translate(_PDF_TRANSLITERATION)


def _build_pdf_fallback(output_path: Path, title: str, chapters: list[Chapter]) -> Path:
    """Minimal valid multi-page PDF built with the stdlib only (Helvetica base14)."""
    page_width, page_height = 420, 595  # points, ~A5-ish
    lines_per_page = 34
    line_height = 14
    top_margin = page_height - 50

    pages_content: list[list[str]] = [[_pdf_safe(f"Tytul: {title}"), ""]]
    for chap_title, body_html in chapters:
        buffer = pages_content[-1]
        buffer.append(_pdf_safe(chap_title))
        buffer.append("")
        for line in _wrap_plain_text(_pdf_safe(body_html)):
            if len(buffer) >= lines_per_page:
                pages_content.append([])
                buffer = pages_content[-1]
            buffer.append(line)
        pages_content.append([])
    if not pages_content[-1]:
        pages_content.pop()
    if not pages_content:
        pages_content = [["(pusty rozdzial)"]]

    objects: list[bytes] = []

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog_num = add_object(b"")  # placeholder, object 1
    pages_num = add_object(b"")  # placeholder, object 2
    font_num = add_object(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )  # object 3

    page_nums: list[int] = []
    content_nums: list[int] = []
    for page_lines in pages_content:
        stream_lines = [f"BT /F1 11 Tf 40 {top_margin} Td 13 TL"]
        for line in page_lines:
            escaped = _pdf_escape(line)
            stream_lines.append(f"({escaped}) Tj T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", "replace")
        content_num = add_object(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        content_nums.append(content_num)

    for content_num in content_nums:
        page_body = (
            f"<< /Type /Page /Parent {pages_num} 0 R "
            f"/MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> "
            f"/Contents {content_num} 0 R >>"
        ).encode()
        page_num = add_object(page_body)
        page_nums.append(page_num)

    kids = " ".join(f"{n} 0 R" for n in page_nums)
    objects[pages_num - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_nums)} >>"
    ).encode()
    objects[catalog_num - 1] = (
        f"<< /Type /Catalog /Pages {pages_num} 0 R >>"
    ).encode()

    buffer = bytearray()
    buffer += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0] * (len(objects) + 1)
    for i, body in enumerate(objects, start=1):
        offsets[i] = len(buffer)
        buffer += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode()
    buffer += b"0000000000 65535 f \n"
    for i in range(1, len(objects) + 1):
        buffer += f"{offsets[i]:010d} 00000 n \n".encode()
    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(buffer))
    return output_path


def _typst_source(title: str, chapters: list[Chapter]) -> str:
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        '#set page(paper: "a5", margin: 2cm)',
        '#set text(font: "Liberation Serif", size: 11pt, lang: "pl")',
        f'#align(center)[#text(size: 22pt, weight: "bold")["{escape(title)}"]]',
        "#pagebreak()",
    ]
    for chap_title, body_html in chapters:
        plain_paragraphs = [p for p in _wrap_plain_text(body_html, width=1_000_000) if p]
        lines.append(f'== {escape(chap_title)}')
        for paragraph in plain_paragraphs:
            lines.append("")
            lines.append(escape(paragraph))
        lines.append("#pagebreak()")
    return "\n".join(lines)


def build_pdf(
    output_path: Path,
    title: str,
    chapters: list[Chapter],
    typst_binary: Optional[str] = None,
) -> tuple[Path, str]:
    """Build a PDF. Uses Typst when a working binary path is given, else stdlib fallback."""
    output_path = Path(output_path)
    if typst_binary and shutil.which(typst_binary):
        typ_source = _typst_source(title, chapters)
        typ_path = output_path.with_suffix(".typ")
        typ_path.parent.mkdir(parents=True, exist_ok=True)
        typ_path.write_text(typ_source, encoding="utf-8")
        subprocess.run(
            [typst_binary, "compile", str(typ_path), str(output_path)],
            check=True,
            capture_output=True,
        )
        return output_path, "typst"
    return _build_pdf_fallback(output_path, title, chapters), "fallback-stdlib"


# --------------------------------------------------------------------------
# Cover art
# --------------------------------------------------------------------------


def _palette_from_seed(seed: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    base_hue = digest[0] / 255
    r1, g1, b1 = [int(30 + digest[i] % 80) for i in range(3)]
    r2, g2, b2 = [int(90 + digest[i + 3] % 140) for i in range(3)]
    return (r1, g1, b1), (r2, g2, b2)


def build_cover_svg(title: str, subtitle: str, brand: str, mode: str) -> str:
    (r1, g1, b1), (r2, g2, b2) = _palette_from_seed(title + mode)
    width, height = 900, 1350
    title_esc = html.escape(title)
    subtitle_esc = html.escape(subtitle)
    brand_esc = html.escape(brand or "Ebook Factory")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="rgb({r1},{g1},{b1})"/>
      <stop offset="100%" stop-color="rgb({r2},{g2},{b2})"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <rect x="60" y="60" width="{width - 120}" height="{height - 120}" fill="none" stroke="white" stroke-opacity="0.35" stroke-width="2"/>
  <text x="{width / 2}" y="{height * 0.42}" font-family="Georgia, 'Liberation Serif', serif" font-size="64" font-weight="700" fill="white" text-anchor="middle">{title_esc}</text>
  <text x="{width / 2}" y="{height * 0.42 + 70}" font-family="Helvetica, Arial, sans-serif" font-size="30" fill="white" fill-opacity="0.85" text-anchor="middle">{subtitle_esc}</text>
  <text x="{width / 2}" y="{height - 90}" font-family="Helvetica, Arial, sans-serif" font-size="26" letter-spacing="2" fill="white" fill-opacity="0.7" text-anchor="middle">{brand_esc.upper()}</text>
</svg>
"""


def build_cover_png(
    output_path: Path, title: str, subtitle: str, brand: str, mode: str
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 900, 1350
    (r1, g1, b1), (r2, g2, b2) = _palette_from_seed(title + mode)

    image = Image.new("RGB", (width, height), (r1, g1, b1))
    for y in range(height):
        t = y / height
        row_color = (
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t),
        )
        for x in range(0, width, 4):
            image.paste(row_color, (x, y, min(x + 4, width), y + 1))

    draw = ImageDraw.Draw(image)
    draw.rectangle([60, 60, width - 60, height - 60], outline=(255, 255, 255), width=2)

    title_font = ImageFont.load_default(size=54)
    subtitle_font = ImageFont.load_default(size=28)
    brand_font = ImageFont.load_default(size=22)

    def draw_centered(text: str, y: int, font, opacity: int = 255) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) / 2, y), text, font=font, fill=(255, 255, 255, opacity))

    wrapped_title = textwrap.wrap(title, width=18) or [title]
    y_cursor = height * 0.38
    for line in wrapped_title:
        draw_centered(line, int(y_cursor), title_font)
        y_cursor += 64
    draw_centered(subtitle, int(y_cursor + 20), subtitle_font)
    draw_centered((brand or "Ebook Factory").upper(), height - 110, brand_font)

    image.save(output_path, format="PNG")
    return output_path


# --------------------------------------------------------------------------
# Manifest and delivery ZIP
# --------------------------------------------------------------------------


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(files: dict[str, Path]) -> dict:
    entries = []
    for name, path in sorted(files.items()):
        path = Path(path)
        entries.append(
            {
                "name": name,
                "sha256": compute_sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }


def build_delivery_zip(delivery_dir: Path, output_zip: Path, filenames: Iterable[str]) -> Path:
    delivery_dir = Path(delivery_dir)
    output_zip = Path(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in filenames:
            zf.write(delivery_dir / name, arcname=name)
    return output_zip
