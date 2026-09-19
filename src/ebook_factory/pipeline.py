"""Resumable, idempotent stage pipeline for ebook production."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .models import MAX_STAGE_ATTEMPTS, STAGE_DEFINITIONS, Project, Stage, utcnow_iso
from .providers import AgentRequest, get_provider
from .repository import ProjectRepository

StageHandler = Callable[[Project, Path], "StageResult"]


@dataclass
class StageResult:
    success: bool
    message: str = ""
    artifact_paths: list[str] = field(default_factory=list)


class PipelineRunner:
    """Runs pipeline stages in order, persisting state after every step.

    Resumability comes from disk: a project's stage rows and its project
    directory are the only state a handler may rely on, so a fresh process
    can call run() again after a restart and continue where it left off.
    """

    def __init__(
        self,
        repository: ProjectRepository,
        projects_root: Path,
        stage_handlers: dict[str, StageHandler],
    ) -> None:
        self.repository = repository
        self.projects_root = Path(projects_root)
        self.stage_handlers = stage_handlers

    def project_dir(self, project: Project) -> Path:
        return self.projects_root / project.slug

    def _ensure_project_dir(self, project: Project) -> Path:
        project_dir = self.project_dir(project)
        for sub in (
            "agent",
            "research",
            "outline",
            "chapters",
            "images",
            "builds",
            "marketing",
            "qa",
            "delivery",
        ):
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        return project_dir

    def _build_agent_prompt(self, project: Project, stage: Stage) -> str:
        source = (project.source_materials or "").strip()
        if len(source) > 6000:
            source = source[:6000] + "\n...[source material truncated by Ebook Factory]..."
        return (
            "Jestes lokalnym agentem Ebook Factory. Wykonaj tylko wskazany etap "
            "i zapisz zwiezly wynik do pliku output przekazanego w argv.\n\n"
            f"Etap: {stage.name}\n"
            f"Tytul: {project.title}\n"
            f"Temat: {project.topic}\n"
            f"Tryb: {project.mode}\n"
            f"Jezyk: {project.language}\n"
            f"Odbiorcy: {project.audience or 'nie podano'}\n"
            f"Marka: {project.brand or 'nie podano'}\n"
            f"Ton: {project.tone or 'rzeczowy'}\n\n"
            "Kontrakt wyjscia: markdown, maksymalnie 1200 slow, bez sekretow, "
            "bez pelnego przepisywania materialow zrodlowych.\n\n"
            f"Materialy zrodlowe (skrocone):\n{source or 'brak'}\n"
        )

    def run(self, project_id: str, stop_requested: Callable[[], bool] = lambda: False) -> Project:
        project = self.repository.get_project(project_id)
        if project is None:
            raise KeyError(project_id)

        if project.status == "completed":
            return project

        project_dir = self._ensure_project_dir(project)
        stages = self.repository.list_stages(project_id)
        total = len(stages)
        provider = get_provider(project.provider)

        if not provider.available():
            message = f"provider {project.provider} is not available"
            self.repository.update_project(project_id, status="failed", error=message)
            self.repository.append_event(project_id, "error", message)
            return self.repository.get_project(project_id)  # type: ignore[return-value]

        self.repository.update_project(project_id, status="running", error=None)

        for stage in stages:
            if stage.status == "completed":
                continue

            success = self._run_stage_with_retries(project, project_dir, stage)
            if not success:
                error_message = f"{stage.name}: {stage.message}"
                self.repository.update_project(project_id, status="failed", error=error_message)
                self.repository.append_event(project_id, "error", f"project failed at {stage.name}")
                return self.repository.get_project(project_id)  # type: ignore[return-value]

            progress = round(((stage.position + 1) / total) * 100)
            self.repository.update_project(project_id, progress=progress)

            if stop_requested():
                self.repository.update_project(project_id, status="paused")
                return self.repository.get_project(project_id)  # type: ignore[return-value]

        self.repository.update_project(project_id, status="completed", progress=100)
        self.repository.append_event(project_id, "info", "project completed")
        return self.repository.get_project(project_id)  # type: ignore[return-value]

    def _run_stage_with_retries(self, project: Project, project_dir: Path, stage: Stage) -> bool:
        handler = self.stage_handlers[stage.name]
        provider = get_provider(project.provider)
        while stage.attempts < MAX_STAGE_ATTEMPTS:
            stage.status = "running"
            stage.attempts += 1
            stage.started_at = utcnow_iso()
            self.repository.upsert_stage(project.id, stage)

            try:
                agent_artifacts: list[str] = []
                if project.provider != "demo":
                    output_file = project_dir / "agent" / f"{stage.name}.md"
                    agent_result = provider.run(
                        AgentRequest(
                            stage=stage.name,
                            prompt=self._build_agent_prompt(project, stage),
                            workspace=project_dir,
                            output_file=output_file,
                            timeout_seconds=180,
                        )
                    )
                    if not agent_result.success:
                        result = StageResult(
                            success=False,
                            message=f"provider {project.provider} failed: {agent_result.message}",
                        )
                    else:
                        self.repository.append_event(
                            project.id,
                            "info",
                            f"provider={project.provider} stage={stage.name} completed",
                        )
                        agent_artifacts = [f"agent/{stage.name}.md"]
                        result = handler(project, project_dir)
                        result.artifact_paths = agent_artifacts + result.artifact_paths
                else:
                    result = handler(project, project_dir)
            except Exception as exc:  # demo adapter must never crash the worker
                result = StageResult(success=False, message=f"{type(exc).__name__}: {exc}")

            stage.finished_at = utcnow_iso()
            stage.message = result.message

            if result.success:
                stage.status = "completed"
                stage.artifact_paths = result.artifact_paths
                self.repository.upsert_stage(project.id, stage)
                self.repository.append_event(project.id, "info", f"{stage.name} completed")
                return True

            stage.status = "failed"
            self.repository.upsert_stage(project.id, stage)
            self.repository.append_event(
                project.id,
                "error",
                f"{stage.name} attempt {stage.attempts} failed: {result.message}",
            )

        return False
