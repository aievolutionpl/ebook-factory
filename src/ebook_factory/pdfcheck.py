"""PDF acceptance check: pages exist and text is extractable.

Uses poppler (`pdfinfo` + `pdftotext`) when available for an authoritative
read, otherwise falls back to a small stdlib-only PDF parser that is good
enough to validate the uncompressed PDFs this project's fallback engine
produces (see artifacts.py::_build_pdf_fallback).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path

_PAGE_OBJECT_RE = re.compile(rb"/Type\s*/Page(?!s)\b")
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_TEXT_SHOW_RE = re.compile(rb"\(((?:\\.|[^\\()])*)\)\s*Tj")
_PDFINFO_PAGES_RE = re.compile(r"^Pages:\s+(\d+)", re.MULTILINE)


@dataclass
class PdfCheckResult:
    page_count: int
    has_text: bool
    method: str


def check_pdf(path: Path) -> PdfCheckResult:
    path = Path(path)
    if not path.is_file():
        return PdfCheckResult(page_count=0, has_text=False, method="missing")

    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        return PdfCheckResult(page_count=0, has_text=False, method="invalid")

    if shutil.which("pdfinfo") and shutil.which("pdftotext"):
        return _check_with_poppler(path)
    return _check_with_fallback(data)


def _check_with_poppler(path: Path) -> PdfCheckResult:
    try:
        info = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=True, timeout=10
        )
        text = subprocess.run(
            ["pdftotext", str(path), "-"], capture_output=True, text=True, check=True, timeout=10
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return _check_with_fallback(path.read_bytes())

    match = _PDFINFO_PAGES_RE.search(info.stdout)
    page_count = int(match.group(1)) if match else 0
    has_text = bool(text.stdout.strip())
    return PdfCheckResult(page_count=page_count, has_text=has_text, method="poppler")


def _check_with_fallback(data: bytes) -> PdfCheckResult:
    page_count = len(_PAGE_OBJECT_RE.findall(data))
    return PdfCheckResult(page_count=page_count, has_text=_fallback_has_text(data), method="fallback-parser")


def _fallback_has_text(data: bytes) -> bool:
    for stream_match in _STREAM_RE.finditer(data):
        content = stream_match.group(1)
        try:
            content = zlib.decompress(content)
        except zlib.error:
            pass  # stream is not Flate-compressed; use it raw
        if any(shown.strip() for shown in _TEXT_SHOW_RE.findall(content)):
            return True
    return False
