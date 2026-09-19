"""HTTP API for Ebook Factory: project CRUD, pipeline control, downloads."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .models import MAX_SOURCE_MATERIALS_CHARS, Event, Project, ProjectCreate, Stage
from .pipeline import PipelineRunner
from .sources import (
    MAX_SOURCE_FILES_PER_PROJECT,
    SourceUploadError,
    count_existing_source_files,
    extract_text,
    store_source_file,
    validate_source_upload,
)


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    mode: Literal["lead-magnet", "guide", "premium"]
    language: str = "pl"
    audience: str = ""
    brand: str = ""
    tone: str = ""
    source_materials: Optional[str] = Field(default=None, max_length=MAX_SOURCE_MATERIALS_CHARS)


def _project_dict(project: Project, stages: Optional[list[Stage]] = None) -> dict:
    data = {
        "id": project.id,
        "slug": project.slug,
        "title": project.title,
        "topic": project.topic,
        "mode": project.mode,
        "language": project.language,
        "audience": project.audience,
        "brand": project.brand,
        "tone": project.tone,
        "status": project.status,
        "progress": project.progress,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "error": project.error,
    }
    if stages is not None:
        data["stages"] = [_stage_dict(s) for s in stages]
    return data


def _stage_dict(stage: Stage) -> dict:
    return {
        "name": stage.name,
        "position": stage.position,
        "status": stage.status,
        "attempts": stage.attempts,
        "started_at": stage.started_at,
        "finished_at": stage.finished_at,
        "message": stage.message,
        "artifact_paths": stage.artifact_paths,
    }


def _event_dict(event: Event) -> dict:
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "level": event.level,
        "message": event.message,
    }


@dataclass
class _WorkerState:
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    cancel_requested: bool = False

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


class ProjectAlreadyRunningError(Exception):
    """Raised when start() is called for a project that already has a live worker."""


class WorkerRegistry:
    """Tracks one background pipeline thread per project.

    ``start()`` performs its "is it already running?" check and thread launch
    under a single lock so two near-simultaneous callers can never both pass
    the check and spawn two workers for the same project (see the Important
    finding in the 2026-09-19 review: the previous check-then-start was racy
    across the lock boundary).
    """

    def __init__(self) -> None:
        self._states: dict[str, _WorkerState] = {}
        self._lock = threading.Lock()

    def _get_or_create_locked(self, project_id: str) -> _WorkerState:
        if project_id not in self._states:
            self._states[project_id] = _WorkerState()
        return self._states[project_id]

    def is_running(self, project_id: str) -> bool:
        with self._lock:
            return self._get_or_create_locked(project_id).is_running()

    def start(self, project_id: str, runner: PipelineRunner, repository) -> None:
        with self._lock:
            state = self._get_or_create_locked(project_id)
            if state.is_running():
                raise ProjectAlreadyRunningError(project_id)

            state.stop_event.clear()
            state.cancel_requested = False

            def _worker() -> None:
                result = runner.run(project_id, stop_requested=state.stop_event.is_set)
                if state.cancel_requested and result.status == "paused":
                    repository.update_project(project_id, status="cancelled")

            thread = threading.Thread(target=_worker, daemon=True)
            state.thread = thread
            thread.start()

    def request_pause(self, project_id: str) -> None:
        with self._lock:
            self._get_or_create_locked(project_id).stop_event.set()

    def request_cancel(self, project_id: str) -> None:
        with self._lock:
            state = self._get_or_create_locked(project_id)
            state.cancel_requested = True
            state.stop_event.set()

    def join_all(self, timeout: Optional[float] = None) -> None:
        with self._lock:
            states = list(self._states.values())
        for state in states:
            if state.thread is not None:
                state.thread.join(timeout=timeout)


def build_router(
    repository,
    runner: PipelineRunner,
    projects_root: Path,
    registry: Optional[WorkerRegistry] = None,
) -> APIRouter:
    registry = registry or WorkerRegistry()
    router = APIRouter()

    def _get_project_or_404(project_id: str) -> Project:
        project = repository.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        return project

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreateRequest) -> dict:
        try:
            data = ProjectCreate(
                title=payload.title,
                topic=payload.topic,
                mode=payload.mode,
                language=payload.language,
                audience=payload.audience,
                brand=payload.brand,
                tone=payload.tone,
                source_materials=payload.source_materials,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        project = repository.create_project(data)
        stages = repository.list_stages(project.id)
        return _project_dict(project, stages)

    @router.get("/api/projects")
    def list_projects() -> list[dict]:
        return [_project_dict(p) for p in repository.list_projects()]

    @router.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict:
        project = _get_project_or_404(project_id)
        stages = repository.list_stages(project_id)
        return _project_dict(project, stages)

    @router.post("/api/projects/{project_id}/start", status_code=202)
    def start_project(project_id: str) -> dict:
        project = _get_project_or_404(project_id)
        if project.status == "completed":
            raise HTTPException(status_code=409, detail="project already completed")
        if project.status == "cancelled":
            raise HTTPException(status_code=409, detail="project was cancelled")
        try:
            registry.start(project_id, runner, repository)
        except ProjectAlreadyRunningError:
            raise HTTPException(status_code=409, detail="project is already running")
        return _project_dict(repository.get_project(project_id))

    @router.post("/api/projects/{project_id}/pause", status_code=202)
    def pause_project(project_id: str) -> dict:
        _get_project_or_404(project_id)
        if not registry.is_running(project_id):
            raise HTTPException(status_code=409, detail="project is not running")
        registry.request_pause(project_id)
        return _project_dict(repository.get_project(project_id))

    @router.post("/api/projects/{project_id}/resume", status_code=202)
    def resume_project(project_id: str) -> dict:
        project = _get_project_or_404(project_id)
        if registry.is_running(project_id):
            raise HTTPException(status_code=409, detail="project is already running")
        if project.status != "paused":
            raise HTTPException(status_code=409, detail="project is not paused")
        registry.start(project_id, runner, repository)
        return _project_dict(repository.get_project(project_id))

    @router.post("/api/projects/{project_id}/cancel", status_code=202)
    def cancel_project(project_id: str) -> dict:
        project = _get_project_or_404(project_id)
        if registry.is_running(project_id):
            registry.request_cancel(project_id)
        else:
            if project.status not in ("completed", "cancelled"):
                repository.update_project(project_id, status="cancelled")
        return _project_dict(repository.get_project(project_id))

    @router.post("/api/projects/{project_id}/sources", status_code=201)
    def upload_sources(
        project_id: str, files: list[UploadFile] = File(...)
    ) -> list[dict]:
        project = _get_project_or_404(project_id)
        project_dir = projects_root / project.slug

        uploads: list[tuple[str, bytes]] = []
        for upload in files:
            content = upload.file.read()
            try:
                validate_source_upload(upload.filename or "", content)
            except SourceUploadError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            uploads.append((upload.filename or "", content))

        existing_count = count_existing_source_files(project_dir)
        if existing_count + len(uploads) > MAX_SOURCE_FILES_PER_PROJECT:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"project may have at most {MAX_SOURCE_FILES_PER_PROJECT} "
                    "source files"
                ),
            )

        results: list[dict] = []
        appended_parts: list[str] = []
        for filename, content in uploads:
            dest = store_source_file(project_dir, filename, content)
            text, status = extract_text(dest)
            results.append(
                {
                    "filename": dest.name,
                    "stored_path": f"sources/{dest.name}",
                    "size_bytes": len(content),
                    "extraction_status": status,
                    "extracted_chars": len(text) if text else 0,
                }
            )
            if text:
                appended_parts.append(f"[{dest.name}]\n{text}")

        if appended_parts:
            current = project.source_materials or ""
            addition = "\n\n".join(appended_parts)
            combined = f"{current}\n\n{addition}" if current else addition
            repository.update_project(
                project_id, source_materials=combined[:MAX_SOURCE_MATERIALS_CHARS]
            )

        return results

    @router.get("/api/projects/{project_id}/events")
    def list_events(project_id: str) -> list[dict]:
        _get_project_or_404(project_id)
        return [_event_dict(e) for e in repository.list_events(project_id)]

    @router.get("/api/projects/{project_id}/download")
    def download_project(project_id: str):
        project = _get_project_or_404(project_id)
        if project.status != "completed":
            raise HTTPException(status_code=404, detail="delivery package not ready")
        delivery_dir = projects_root / project.slug / "delivery"
        zip_path = delivery_dir / "delivery.zip"
        manifest_path = delivery_dir / "manifest.json"
        if not zip_path.is_file() or not manifest_path.is_file():
            raise HTTPException(status_code=404, detail="delivery package not ready")
        safe_filename = f"{project.slug}-delivery.zip"
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=safe_filename,
        )

    return router
