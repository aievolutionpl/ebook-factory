"""Application factory: wires repository, pipeline runner and HTTP API together."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import WorkerRegistry, build_router
from .auth import BasicAuthMiddleware, credentials_from_env
from .pipeline import PipelineRunner
from .repository import ProjectRepository
from .stages import DEFAULT_STAGE_HANDLERS

STATIC_DIR = Path(__file__).parent / "static"

_UNSET = object()


def create_app(data_dir: Path, auth_credentials: Optional[tuple[str, str]] = _UNSET) -> FastAPI:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    projects_root = data_dir / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)

    repository = ProjectRepository(data_dir / "factory.db")
    runner = PipelineRunner(repository, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    registry = WorkerRegistry()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        registry.join_all(timeout=30)
        repository.close()

    app = FastAPI(title="Ebook Factory", lifespan=lifespan)
    app.state.repository = repository
    app.state.runner = runner
    app.state.registry = registry

    router = build_router(repository, runner, projects_root, registry)
    app.include_router(router)

    if auth_credentials is _UNSET:
        auth_credentials = credentials_from_env()
    if auth_credentials is not None:
        app.add_middleware(BasicAuthMiddleware, credentials=auth_credentials)

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
