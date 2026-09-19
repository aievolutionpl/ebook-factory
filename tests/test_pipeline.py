import stat

import pytest

from ebook_factory.models import STAGE_DEFINITIONS, ProjectCreate
from ebook_factory.pipeline import PipelineRunner, StageResult
from ebook_factory.repository import ProjectRepository

STAGE_NAMES = [d.name for d in STAGE_DEFINITIONS]


def make_handlers(call_log, failing_stage=None, fail_forever=True):
    handlers = {}
    for name in STAGE_NAMES:
        def handler(project, project_dir, _name=name):
            call_log.append(_name)
            if _name == failing_stage:
                return StageResult(success=False, message=f"{_name} boom")
            (project_dir / f"{_name}.marker").write_text("ok")
            return StageResult(success=True, message="ok", artifact_paths=[f"{_name}.marker"])

        handlers[name] = handler
    return handlers


@pytest.fixture
def repo(tmp_path):
    r = ProjectRepository(tmp_path / "factory.db")
    yield r
    r.close()


@pytest.fixture
def projects_root(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    return root


def test_run_executes_stages_in_order(repo, projects_root):
    call_log = []
    project = repo.create_project(ProjectCreate(title="Order", topic="AI", mode="lead-magnet"))
    runner = PipelineRunner(repo, projects_root, stage_handlers=make_handlers(call_log))

    result = runner.run(project.id)

    assert call_log == STAGE_NAMES
    assert result.status == "completed"
    assert result.progress == 100


def test_completed_stages_are_skipped_on_rerun(repo, projects_root):
    call_log = []
    project = repo.create_project(ProjectCreate(title="Skip", topic="AI", mode="guide"))
    runner = PipelineRunner(repo, projects_root, stage_handlers=make_handlers(call_log))
    runner.run(project.id)

    call_log.clear()
    result = runner.run(project.id)

    assert call_log == []
    assert result.status == "completed"


def test_run_pauses_after_current_stage(repo, projects_root):
    call_log = []
    project = repo.create_project(ProjectCreate(title="Pause", topic="AI", mode="guide"))
    runner = PipelineRunner(repo, projects_root, stage_handlers=make_handlers(call_log))

    result = runner.run(project.id, stop_requested=lambda: True)

    assert call_log == [STAGE_NAMES[0]]
    assert result.status == "paused"
    stages = repo.list_stages(project.id)
    assert stages[0].status == "completed"
    assert stages[1].status == "pending"


def test_run_resumes_from_first_incomplete_stage(repo, projects_root):
    call_log = []
    project = repo.create_project(ProjectCreate(title="Resume", topic="AI", mode="guide"))
    runner = PipelineRunner(repo, projects_root, stage_handlers=make_handlers(call_log))
    runner.run(project.id, stop_requested=lambda: True)
    assert call_log == [STAGE_NAMES[0]]

    call_log.clear()
    result = runner.run(project.id)

    assert call_log == STAGE_NAMES[1:]
    assert result.status == "completed"


def test_stage_failure_retries_up_to_three_times_then_fails_project(repo, projects_root):
    call_log = []
    failing_stage = STAGE_NAMES[2]
    project = repo.create_project(ProjectCreate(title="Fail", topic="AI", mode="guide"))
    runner = PipelineRunner(
        repo, projects_root, stage_handlers=make_handlers(call_log, failing_stage=failing_stage)
    )

    result = runner.run(project.id)

    assert result.status == "failed"
    assert result.error is not None
    assert failing_stage in result.error
    failed_stage_calls = [name for name in call_log if name == failing_stage]
    assert len(failed_stage_calls) == 3
    stages = repo.list_stages(project.id)
    by_name = {s.name: s for s in stages}
    assert by_name[failing_stage].attempts == 3
    assert by_name[failing_stage].status == "failed"
    # stages after the failed one never ran
    failing_index = STAGE_NAMES.index(failing_stage)
    for name in STAGE_NAMES[failing_index + 1 :]:
        assert by_name[name].status == "pending"


def test_run_unknown_project_raises(repo, projects_root):
    runner = PipelineRunner(repo, projects_root, stage_handlers={})
    with pytest.raises(KeyError):
        runner.run("does-not-exist")


def test_project_directory_is_created_under_projects_root(repo, projects_root):
    call_log = []
    project = repo.create_project(ProjectCreate(title="Dir Test", topic="AI", mode="lead-magnet"))
    runner = PipelineRunner(repo, projects_root, stage_handlers=make_handlers(call_log))

    runner.run(project.id)

    project_dir = projects_root / project.slug
    assert project_dir.is_dir()
    assert (project_dir / f"{STAGE_NAMES[0]}.marker").exists()


def test_non_demo_provider_runs_before_stage_handler_and_keeps_artifacts(
    repo, projects_root, tmp_path, monkeypatch
):
    fake = tmp_path / "codex-fake"
    fake.write_text(
        """#!/usr/bin/env python3
import pathlib
import sys

args = sys.argv[1:]
output = pathlib.Path(args[args.index("--output-last-message") + 1])
output.write_text("agent output from codex", encoding="utf-8")
print("agent ran")
""",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("EBOOK_FACTORY_CODEX_CLI", str(fake))
    project = repo.create_project(
        ProjectCreate(title="Agent run", topic="AI", mode="lead-magnet", provider="codex-cli")
    )
    call_log = []
    runner = PipelineRunner(repo, projects_root, stage_handlers=make_handlers(call_log))

    result = runner.run(project.id, stop_requested=lambda: len(call_log) >= 1)

    assert result.status == "paused"
    project_dir = projects_root / project.slug
    assert (project_dir / "agent" / f"{STAGE_NAMES[0]}.md").read_text(
        encoding="utf-8"
    ) == "agent output from codex"
    first_stage = repo.get_stage(project.id, STAGE_NAMES[0])
    assert f"{STAGE_NAMES[0]}.marker" in first_stage.artifact_paths
    assert f"agent/{STAGE_NAMES[0]}.md" in first_stage.artifact_paths
    events = [event.message for event in repo.list_events(project.id)]
    assert any("provider=codex-cli stage=strategy" in message for message in events)
