"""SQLite-backed persistence for Ebook Factory projects, stages and events."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Optional

from .models import (
    STAGE_DEFINITIONS,
    Event,
    Project,
    ProjectCreate,
    Stage,
    slugify,
    utcnow_iso,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    mode TEXT NOT NULL,
    language TEXT NOT NULL,
    audience TEXT NOT NULL,
    brand TEXT NOT NULL,
    tone TEXT NOT NULL,
    source_materials TEXT,
    provider TEXT NOT NULL DEFAULT 'demo',
    chapter_titles TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    progress INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS stages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    message TEXT NOT NULL,
    artifact_paths TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stages_project ON stages(project_id, position);
CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, timestamp);
"""


def _decode_chapter_titles(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        topic=row["topic"],
        mode=row["mode"],
        language=row["language"],
        audience=row["audience"],
        brand=row["brand"],
        tone=row["tone"],
        source_materials=row["source_materials"],
        provider=row["provider"],
        chapter_titles=_decode_chapter_titles(row["chapter_titles"]),
        status=row["status"],
        progress=row["progress"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error=row["error"],
    )


def _row_to_stage(row: sqlite3.Row) -> Stage:
    return Stage(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        position=row["position"],
        status=row["status"],
        attempts=row["attempts"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        message=row["message"],
        artifact_paths=json.loads(row["artifact_paths"]),
    )


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        project_id=row["project_id"],
        timestamp=row["timestamp"],
        level=row["level"],
        message=row["message"],
    )


class ProjectRepository:
    """SQLite repository. Safe to share across threads (one connection, serialized)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # Pipeline stages run on a background worker thread while the API
        # serves requests on another; a bare sqlite3 connection is not safe
        # under concurrent multi-threaded use, so every public method below
        # serializes access through this lock.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "provider" not in columns:
            self._conn.execute(
                "ALTER TABLE projects ADD COLUMN provider TEXT NOT NULL DEFAULT 'demo'"
            )
        if "chapter_titles" not in columns:
            self._conn.execute(
                "ALTER TABLE projects ADD COLUMN chapter_titles TEXT NOT NULL DEFAULT '[]'"
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _unique_slug(self, base_slug: str) -> str:
        cursor = self._conn.execute(
            "SELECT slug FROM projects WHERE slug = ? OR slug LIKE ?",
            (base_slug, f"{base_slug}-%"),
        )
        existing = {row["slug"] for row in cursor.fetchall()}
        if base_slug not in existing:
            return base_slug
        counter = 2
        while f"{base_slug}-{counter}" in existing:
            counter += 1
        return f"{base_slug}-{counter}"

    def create_project(self, data: ProjectCreate) -> Project:
        with self._lock:
            project_id = uuid.uuid4().hex
            slug = self._unique_slug(slugify(data.title))
            now = utcnow_iso()
            self._conn.execute(
                """
                INSERT INTO projects (
                    id, slug, title, topic, mode, language, audience, brand, tone,
                    source_materials, provider, chapter_titles, status, progress,
                    created_at, updated_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    slug,
                    data.title,
                    data.topic,
                    data.mode,
                    data.language,
                    data.audience,
                    data.brand,
                    data.tone,
                    data.source_materials,
                    data.provider,
                    json.dumps(data.chapter_titles, ensure_ascii=False),
                    "draft",
                    0,
                    now,
                    now,
                    None,
                ),
            )
            for position, definition in enumerate(STAGE_DEFINITIONS):
                self._conn.execute(
                    """
                    INSERT INTO stages (
                        id, project_id, name, position, status, attempts,
                        started_at, finished_at, message, artifact_paths
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        project_id,
                        definition.name,
                        position,
                        "pending",
                        0,
                        None,
                        None,
                        "",
                        "[]",
                    ),
                )
            self._conn.commit()
            return self.get_project(project_id)  # type: ignore[return-value]

    def get_project(self, project_id: str) -> Optional[Project]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return _row_to_project(row) if row else None

    def get_project_by_slug(self, slug: str) -> Optional[Project]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE slug = ?", (slug,)
            ).fetchone()
            return _row_to_project(row) if row else None

    def list_projects(self) -> list[Project]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY created_at ASC"
            ).fetchall()
            return [_row_to_project(row) for row in rows]

    def update_project(self, project_id: str, **fields) -> Project:
        with self._lock:
            if not fields:
                existing = self.get_project(project_id)
                if existing is None:
                    raise KeyError(project_id)
                return existing
            allowed = {
                "title",
                "topic",
                "mode",
                "language",
                "audience",
                "brand",
                "tone",
                "source_materials",
                "provider",
                "chapter_titles",
                "status",
                "progress",
                "error",
            }
            unknown = set(fields) - allowed
            if unknown:
                raise ValueError(f"cannot update unknown fields: {unknown}")
            if isinstance(fields.get("chapter_titles"), list):
                fields["chapter_titles"] = json.dumps(
                    fields["chapter_titles"], ensure_ascii=False
                )
            fields["updated_at"] = utcnow_iso()
            assignments = ", ".join(f"{key} = ?" for key in fields)
            values = list(fields.values()) + [project_id]
            self._conn.execute(
                f"UPDATE projects SET {assignments} WHERE id = ?", values
            )
            self._conn.commit()
            project = self.get_project(project_id)
            if project is None:
                raise KeyError(project_id)
            return project

    def list_stages(self, project_id: str) -> list[Stage]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM stages WHERE project_id = ? ORDER BY position ASC",
                (project_id,),
            ).fetchall()
            return [_row_to_stage(row) for row in rows]

    def get_stage(self, project_id: str, name: str) -> Optional[Stage]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM stages WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            return _row_to_stage(row) if row else None

    def upsert_stage(self, project_id: str, stage: Stage) -> Stage:
        with self._lock:
            self._conn.execute(
                """
                UPDATE stages SET
                    status = ?, attempts = ?, started_at = ?, finished_at = ?,
                    message = ?, artifact_paths = ?
                WHERE project_id = ? AND name = ?
                """,
                (
                    stage.status,
                    stage.attempts,
                    stage.started_at,
                    stage.finished_at,
                    stage.message,
                    json.dumps(stage.artifact_paths),
                    project_id,
                    stage.name,
                ),
            )
            self._conn.commit()
            updated = self.get_stage(project_id, stage.name)
            if updated is None:
                raise KeyError((project_id, stage.name))
            return updated

    def append_event(self, project_id: str, level: str, message: str) -> Event:
        with self._lock:
            event_id = uuid.uuid4().hex
            timestamp = utcnow_iso()
            self._conn.execute(
                """
                INSERT INTO events (id, project_id, timestamp, level, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, project_id, timestamp, level, message),
            )
            self._conn.commit()
            return Event(
                id=event_id,
                project_id=project_id,
                timestamp=timestamp,
                level=level,
                message=message,
            )

    def list_events(
        self,
        project_id: str,
        after_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        """List events oldest first.

        ``after_id`` returns only events appended after that event, which lets
        a polling client fetch deltas instead of the whole log every tick. An
        unknown ``after_id`` is treated as "from the beginning".
        """
        with self._lock:
            params: list = [project_id]
            query = "SELECT * FROM events WHERE project_id = ?"
            if after_id:
                row = self._conn.execute(
                    "SELECT rowid FROM events WHERE id = ? AND project_id = ?",
                    (after_id, project_id),
                ).fetchone()
                if row is not None:
                    query += " AND rowid > ?"
                    params.append(row["rowid"])
            query += " ORDER BY timestamp ASC, rowid ASC"
            if limit is not None and limit > 0:
                query += " LIMIT ?"
                params.append(limit)
            rows = self._conn.execute(query, params).fetchall()
            return [_row_to_event(row) for row in rows]

    def count_projects_by_status(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS total FROM projects GROUP BY status"
            ).fetchall()
            return {row["status"]: row["total"] for row in rows}

    def delete_project(self, project_id: str) -> bool:
        """Remove a project and its stage/event rows. Returns False if unknown."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if existing is None:
                return False
            self._conn.execute("DELETE FROM events WHERE project_id = ?", (project_id,))
            self._conn.execute("DELETE FROM stages WHERE project_id = ?", (project_id,))
            self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.commit()
            return True

    def reset_stages_from(self, project_id: str, position: int) -> int:
        """Reset every stage at or after ``position`` back to pending.

        Used by the retry endpoint so a failed run can be replayed from the
        first broken stage without rebuilding the earlier, still-valid ones.
        """
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE stages
                SET status = 'pending', attempts = 0, started_at = NULL,
                    finished_at = NULL, message = '', artifact_paths = '[]'
                WHERE project_id = ? AND position >= ?
                """,
                (project_id, position),
            )
            self._conn.commit()
            return cursor.rowcount
