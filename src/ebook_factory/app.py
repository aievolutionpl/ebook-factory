"""Application factory: wires repository, pipeline runner and HTTP API together."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import WorkerRegistry, build_router
from .pipeline import PipelineRunner
from .repository import ProjectRepository
from .stages import DEFAULT_STAGE_HANDLERS

STATIC_DIR = Path(__file__).parent / "static"


def create_app(data_dir: Path) -> FastAPI:
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

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
