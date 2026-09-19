"""Bounded, sanitized source-material file uploads for projects.

Uploaded files are confined to ``projects/<slug>/sources`` regardless of what
the client sent as a filename: only the basename survives sanitization, so a
crafted ``../../etc/passwd`` can never escape the project's sources folder.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Optional

ALLOWED_SOURCE_EXTENSIONS = (".txt", ".md", ".pdf")
MAX_SOURCE_FILE_BYTES = 5 * 1024 * 1024
MAX_SOURCE_FILES_PER_PROJECT = 5


class SourceUploadError(ValueError):
    """Raised when an uploaded source file fails validation."""


def sanitize_source_filename(filename: str) -> str:
    """Reduce an arbitrary client-supplied filename to a safe flat basename."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._")
    return safe or "file"


def validate_source_upload(filename: str, content: bytes) -> None:
    """Raise SourceUploadError if the extension, size, or content is invalid."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SOURCE_EXTENSIONS:
        raise SourceUploadError(
            f"unsupported file extension {suffix!r}; expected one of {ALLOWED_SOURCE_EXTENSIONS}"
        )
    if not content:
        raise SourceUploadError("uploaded file is empty")
    if len(content) > MAX_SOURCE_FILE_BYTES:
        raise SourceUploadError(
            f"file exceeds maximum size of {MAX_SOURCE_FILE_BYTES} bytes"
        )


def _unique_destination(sources_dir: Path, safe_name: str) -> Path:
    dest = sources_dir / safe_name
    if not dest.exists():
        return dest
    stem, suffix = Path(safe_name).stem, Path(safe_name).suffix
    counter = 2
    while dest.exists():
        dest = sources_dir / f"{stem}-{counter}{suffix}"
        counter += 1
    return dest


def store_source_file(project_dir: Path, filename: str, content: bytes) -> Path:
    """Validate, sanitize, and write an uploaded source file.

    Returns the absolute path of the stored file, always located under
    ``project_dir / "sources"``. Raises SourceUploadError on any invalid
    extension, oversize, or empty content.
    """
    validate_source_upload(filename, content)
    safe_name = sanitize_source_filename(filename)

    sources_dir = project_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    dest = _unique_destination(sources_dir, safe_name)
    resolved_sources_dir = sources_dir.resolve()
    resolved_dest = dest.resolve()
    if resolved_dest.parent != resolved_sources_dir:
        raise SourceUploadError("resolved path escapes the sources directory")

    dest.write_bytes(content)
    return dest


def count_existing_source_files(project_dir: Path) -> int:
    sources_dir = project_dir / "sources"
    if not sources_dir.is_dir():
        return 0
    return sum(1 for entry in sources_dir.iterdir() if entry.is_file())


def extract_text(path: Path) -> tuple[Optional[str], str]:
    """Extract text from a stored source file.

    Returns ``(text, status)`` where status is one of ``"extracted"``,
    ``"empty"`` (decoded fine but had no non-whitespace content), or
    ``"unavailable"`` (no extraction tool present for this file type).
    """
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        text = path.read_bytes().decode("utf-8", errors="replace")
        return (text, "extracted" if text.strip() else "empty")
    if suffix == ".pdf":
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            return (None, "unavailable")
        try:
            result = subprocess.run(
                [pdftotext, str(path), "-"],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return (None, "unavailable")
        if result.returncode != 0:
            return (None, "unavailable")
        text = result.stdout.decode("utf-8", errors="replace")
        return (text, "extracted" if text.strip() else "empty")
    return (None, "unavailable")
