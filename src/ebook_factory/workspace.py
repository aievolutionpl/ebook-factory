"""Read-only view over a project's on-disk workspace.

The UI used to display a hard-coded guess of what a finished project contains.
This module replaces the guess with the truth: it walks the project directory,
classifies every artifact, and hands back previews and metrics.

Every path that comes from a client passes through :func:`resolve_artifact`,
which resolves symlinks and refuses anything that lands outside the project
directory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

MAX_LISTED_ARTIFACTS = 500
MAX_PREVIEW_CHARS = 20_000
WORDS_PER_PAGE = 300
WORDS_PER_MINUTE = 200

#: Directory -> (category id, human label). Order defines display order.
CATEGORY_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("delivery", "delivery", "Paczka końcowa"),
    ("builds", "builds", "Pliki książki"),
    ("images", "images", "Okładka"),
    ("chapters", "chapters", "Rozdziały"),
    ("outline", "outline", "Strategia i struktura"),
    ("research", "research", "Research"),
    ("marketing", "marketing", "Marketing"),
    ("qa", "qa", "Kontrola jakości"),
    ("sources", "sources", "Źródła"),
    ("agent", "agent", "Wyjście agenta"),
)

_CATEGORY_BY_DIR = {directory: (cid, label) for directory, cid, label in CATEGORY_DEFINITIONS}
_CATEGORY_ORDER = {cid: index for index, (_d, cid, _l) in enumerate(CATEGORY_DEFINITIONS)}

TEXT_SUFFIXES = {".md", ".txt", ".json", ".html", ".xhtml", ".csv", ".typ", ".svg"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

_MEDIA_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
    ".typ": "text/plain; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".xhtml": "application/xhtml+xml",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".epub": "application/epub+zip",
    ".zip": "application/zip",
}


class ArtifactError(Exception):
    """Base class for artifact lookup failures."""


class ArtifactNotFound(ArtifactError):
    """The requested artifact does not exist inside the project workspace."""


class ArtifactAccessDenied(ArtifactError):
    """The requested path escapes the project workspace."""


@dataclass
class Artifact:
    path: str
    name: str
    category: str
    category_label: str
    bytes: int
    modified_at: float
    kind: str
    media_type: str
    previewable: bool

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "category": self.category,
            "category_label": self.category_label,
            "bytes": self.bytes,
            "modified_at": self.modified_at,
            "kind": self.kind,
            "media_type": self.media_type,
            "previewable": self.previewable,
        }


@dataclass
class ArtifactGroup:
    category: str
    label: str
    files: list[Artifact] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "label": self.label,
            "bytes": sum(f.bytes for f in self.files),
            "files": [f.to_dict() for f in self.files],
        }


def classify(path: Path) -> tuple[str, str, bool]:
    """Return ``(kind, media_type, previewable)`` for an artifact path."""
    suffix = path.suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix, "application/octet-stream")
    if suffix in IMAGE_SUFFIXES:
        return "image", media_type, True
    if suffix == ".pdf":
        return "pdf", media_type, False
    if suffix in (".epub", ".zip"):
        return "archive", media_type, False
    if suffix in TEXT_SUFFIXES:
        return "text", media_type, True
    return "binary", media_type, False


def _category_for(relative: Path) -> tuple[str, str]:
    top = relative.parts[0] if len(relative.parts) > 1 else ""
    return _CATEGORY_BY_DIR.get(top, ("other", "Pozostałe"))


def iter_artifacts(project_dir: Path) -> Iterable[Artifact]:
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return []
    root = project_dir.resolve()
    found: list[Artifact] = []
    for entry in sorted(project_dir.rglob("*")):
        if len(found) >= MAX_LISTED_ARTIFACTS:
            break
        if not entry.is_file() or entry.is_symlink():
            continue
        try:
            resolved = entry.resolve()
            resolved.relative_to(root)
            stat = entry.stat()
        except (OSError, ValueError):
            continue
        relative = entry.relative_to(project_dir)
        category, label = _category_for(relative)
        kind, media_type, previewable = classify(entry)
        found.append(
            Artifact(
                path=relative.as_posix(),
                name=entry.name,
                category=category,
                category_label=label,
                bytes=stat.st_size,
                modified_at=stat.st_mtime,
                kind=kind,
                media_type=media_type,
                previewable=previewable,
            )
        )
    return found


def group_artifacts(artifacts: Iterable[Artifact]) -> list[ArtifactGroup]:
    groups: dict[str, ArtifactGroup] = {}
    for artifact in artifacts:
        group = groups.get(artifact.category)
        if group is None:
            group = ArtifactGroup(artifact.category, artifact.category_label)
            groups[artifact.category] = group
        group.files.append(artifact)
    return sorted(
        groups.values(),
        key=lambda g: (_CATEGORY_ORDER.get(g.category, len(_CATEGORY_ORDER)), g.label),
    )


def list_artifact_groups(project_dir: Path) -> list[ArtifactGroup]:
    return group_artifacts(iter_artifacts(project_dir))


def resolve_artifact(project_dir: Path, relative_path: str) -> Path:
    """Resolve a client-supplied relative path inside the project workspace.

    Raises :class:`ArtifactAccessDenied` for absolute paths, traversal, and
    symlinks pointing outside the workspace; :class:`ArtifactNotFound` when no
    regular file lives there.
    """
    cleaned = (relative_path or "").strip().replace("\\", "/")
    if not cleaned:
        raise ArtifactNotFound("empty artifact path")
    if cleaned.startswith("/") or ".." in Path(cleaned).parts:
        raise ArtifactAccessDenied("artifact path escapes the project workspace")
    if Path(cleaned).is_absolute() or re.match(r"^[A-Za-z]:", cleaned):
        raise ArtifactAccessDenied("artifact path must be relative")

    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise ArtifactNotFound("project workspace does not exist")

    root = project_dir.resolve()
    candidate = (project_dir / cleaned).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ArtifactAccessDenied("artifact path escapes the project workspace") from exc
    if not candidate.is_file():
        raise ArtifactNotFound(f"no artifact at {cleaned!r}")
    return candidate


def read_preview(path: Path, max_chars: int = MAX_PREVIEW_CHARS) -> tuple[str, bool]:
    """Read a bounded UTF-8 preview without loading the whole file.

    Returns ``(text, truncated)``. Only ``max_chars * 4 + 1`` bytes are read,
    which is the worst case byte length of ``max_chars`` UTF-8 characters plus
    one probe byte that reveals whether more content follows.
    """
    path = Path(path)
    budget = max_chars * 4 + 1
    with open(path, "rb") as handle:
        raw = handle.read(budget)
    truncated = len(raw) >= budget
    text = raw.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, truncated


_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*|\d+", re.UNICODE)


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def compute_metrics(project_dir: Path) -> dict:
    """Derive live production metrics from the files on disk.

    Everything here is recomputed from the workspace so the numbers stay true
    after a resume, a retry, or a manual edit of a chapter file.
    """
    project_dir = Path(project_dir)
    chapters_dir = project_dir / "chapters"
    chapter_paths = sorted(chapters_dir.glob("chapter-*.md")) if chapters_dir.is_dir() else []

    words = 0
    characters = 0
    chapter_rows: list[dict] = []
    for path in chapter_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.strip().splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else path.stem
        chapter_words = count_words(text)
        words += chapter_words
        characters += len(text)
        chapter_rows.append(
            {"file": f"chapters/{path.name}", "title": title, "words": chapter_words}
        )

    artifacts = list(iter_artifacts(project_dir))
    total_bytes = sum(a.bytes for a in artifacts)

    engine_path = project_dir / "qa" / "engine.json"
    engine_info: dict = {}
    if engine_path.is_file():
        try:
            engine_info = json.loads(engine_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            engine_info = {}

    return {
        "chapters": len(chapter_rows),
        "words": words,
        "characters": characters,
        "estimated_pages": (words + WORDS_PER_PAGE - 1) // WORDS_PER_PAGE if words else 0,
        "reading_minutes": (words + WORDS_PER_MINUTE - 1) // WORDS_PER_MINUTE if words else 0,
        "artifacts": len(artifacts),
        "total_bytes": total_bytes,
        "pdf_engine": engine_info.get("pdf_engine"),
        "print_grade": bool(engine_info.get("print_grade", False)),
        "chapter_breakdown": chapter_rows,
    }


def source_file_entries(project_dir: Path) -> list[dict]:
    """List the uploaded source files for a project."""
    sources_dir = Path(project_dir) / "sources"
    if not sources_dir.is_dir():
        return []
    entries = []
    for path in sorted(sources_dir.iterdir()):
        if not path.is_file() or path.is_symlink():
            continue
        entries.append(
            {
                "name": path.name,
                "path": f"sources/{path.name}",
                "bytes": path.stat().st_size,
            }
        )
    return entries


def delete_project_workspace(project_dir: Path) -> bool:
    """Delete a project's workspace directory. Returns True when something went."""
    import shutil

    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return False
    shutil.rmtree(project_dir)
    return True


def artifact_groups_to_dicts(groups: Iterable[ArtifactGroup]) -> list[dict]:
    return [group.to_dict() for group in groups]


__all__ = [
    "Artifact",
    "ArtifactAccessDenied",
    "ArtifactError",
    "ArtifactGroup",
    "ArtifactNotFound",
    "MAX_PREVIEW_CHARS",
    "artifact_groups_to_dicts",
    "classify",
    "compute_metrics",
    "count_words",
    "delete_project_workspace",
    "group_artifacts",
    "iter_artifacts",
    "list_artifact_groups",
    "read_preview",
    "resolve_artifact",
    "source_file_entries",
]
