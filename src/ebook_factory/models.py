"""Domain model for Ebook Factory: projects, stages, events."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NamedTuple, Optional

PROJECT_MODES: tuple[str, ...] = ("lead-magnet", "guide", "premium")
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


class StageDefinition(NamedTuple):
    name: str
    label: str


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition("strategy", "Strategia"),
    StageDefinition("research", "Research"),
    StageDefinition("outline", "Architektura"),
    StageDefinition("draft", "Draft"),
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

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.topic or not self.topic.strip():
            raise ValueError("topic must not be empty")
        if self.mode not in PROJECT_MODES:
            raise ValueError(
                f"invalid mode {self.mode!r}; expected one of {PROJECT_MODES}"
            )


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
