"""Domain model for Ebook Factory: projects, stages, events."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NamedTuple, Optional

from .humanize import DEFAULT_HUMANIZE_LEVEL, HUMANIZE_LEVELS
from .prose import DEFAULT_WRITING_STYLE, WRITING_STYLES

PROJECT_MODES: tuple[str, ...] = ("lead-magnet", "guide", "premium")
PROJECT_PROVIDERS: tuple[str, ...] = ("demo", "codex-cli", "claude-code")
PROJECT_WRITING_STYLES: tuple[str, ...] = WRITING_STYLES
PROJECT_HUMANIZE_LEVELS: tuple[str, ...] = HUMANIZE_LEVELS
PROJECT_STATUSES: tuple[str, ...] = (
    "draft",
    "running",
    "paused",
    "completed",
    "failed",
    "cancelled",
)
STAGE_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
)
MAX_STAGE_ATTEMPTS = 3
MAX_SOURCE_MATERIALS_CHARS = 50_000
MAX_CHAPTER_TITLES = 40
MAX_CHAPTER_TITLE_CHARS = 160


class StageDefinition(NamedTuple):
    name: str
    label: str


class ModeConfig(NamedTuple):
    label: str
    page_range: tuple[int, int]
    chapter_count: int
    words_per_chapter: int


MODE_CONFIG: dict[str, ModeConfig] = {
    "lead-magnet": ModeConfig("Lead magnet", (15, 30), 5, 320),
    "guide": ModeConfig("Poradnik ekspercki", (40, 100), 8, 600),
    "premium": ModeConfig("Książka premium", (150, 300), 14, 900),
}


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition("strategy", "Strategia"),
    StageDefinition("research", "Research"),
    StageDefinition("outline", "Architektura"),
    StageDefinition("draft", "Draft"),
    StageDefinition("humanize", "Humanizacja"),
    StageDefinition("edit", "Redakcja"),
    StageDefinition("fact_check", "Fact-check"),
    StageDefinition("design", "Design"),
    StageDefinition("publish", "Publikacja"),
    StageDefinition("marketing", "Marketing"),
    StageDefinition("qa", "QA"),
    StageDefinition("delivery", "Delivery"),
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SLUG_TRANSLATION = str.maketrans({"ł": "l", "Ł": "L"})


def slugify(value: str) -> str:
    translated = value.translate(_SLUG_TRANSLATION)
    normalized = unicodedata.normalize("NFKD", translated)
    ascii_bytes = normalized.encode("ascii", "ignore")
    ascii_text = ascii_bytes.decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or "project"


def normalize_chapter_titles(titles: Optional[list[str]]) -> list[str]:
    """Trim, de-duplicate and bound a user-supplied chapter structure.

    An empty result means "let the mode preset decide"; the outline stage
    falls back to the built-in template list in that case.
    """
    if not titles:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in titles:
        title = " ".join(str(raw).split())
        if not title:
            continue
        if len(title) > MAX_CHAPTER_TITLE_CHARS:
            raise ValueError(
                f"chapter title must not exceed {MAX_CHAPTER_TITLE_CHARS} characters"
            )
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(title)
    if len(cleaned) > MAX_CHAPTER_TITLES:
        raise ValueError(f"at most {MAX_CHAPTER_TITLES} chapter titles are allowed")
    return cleaned


@dataclass
class ProjectCreate:
    title: str
    topic: str
    mode: str
    language: str = "pl"
    audience: str = ""
    brand: str = ""
    tone: str = ""
    source_materials: Optional[str] = None
    provider: str = "demo"
    chapter_titles: list[str] = field(default_factory=list)
    writing_style: str = DEFAULT_WRITING_STYLE
    humanize_level: str = DEFAULT_HUMANIZE_LEVEL

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.topic or not self.topic.strip():
            raise ValueError("topic must not be empty")
        if self.mode not in PROJECT_MODES:
            raise ValueError(
                f"invalid mode {self.mode!r}; expected one of {PROJECT_MODES}"
            )
        if self.provider not in PROJECT_PROVIDERS:
            raise ValueError(
                f"invalid provider {self.provider!r}; expected one of {PROJECT_PROVIDERS}"
            )
        if self.writing_style not in PROJECT_WRITING_STYLES:
            raise ValueError(
                f"invalid writing_style {self.writing_style!r}; "
                f"expected one of {PROJECT_WRITING_STYLES}"
            )
        if self.humanize_level not in PROJECT_HUMANIZE_LEVELS:
            raise ValueError(
                f"invalid humanize_level {self.humanize_level!r}; "
                f"expected one of {PROJECT_HUMANIZE_LEVELS}"
            )
        if self.source_materials is not None and len(self.source_materials) > MAX_SOURCE_MATERIALS_CHARS:
            raise ValueError(
                f"source_materials must not exceed {MAX_SOURCE_MATERIALS_CHARS} characters"
            )
        self.chapter_titles = normalize_chapter_titles(self.chapter_titles)


@dataclass
class Project:
    id: str
    slug: str
    title: str
    topic: str
    mode: str
    language: str
    audience: str
    brand: str
    tone: str
    source_materials: Optional[str]
    status: str
    progress: int
    created_at: str
    updated_at: str
    error: Optional[str] = None
    provider: str = "demo"
    chapter_titles: list[str] = field(default_factory=list)
    writing_style: str = DEFAULT_WRITING_STYLE
    humanize_level: str = DEFAULT_HUMANIZE_LEVEL


@dataclass
class Stage:
    id: str
    project_id: str
    name: str
    position: int
    status: str = "pending"
    attempts: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""
    artifact_paths: list[str] = field(default_factory=list)


@dataclass
class Event:
    id: str
    project_id: str
    timestamp: str
    level: str
    message: str
