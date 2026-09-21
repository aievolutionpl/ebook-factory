"""The humanize stage, its report, and how the rest of the pipeline uses it."""

import json

import pytest

from ebook_factory.humanize import HUMAN_SCORE_TARGET
from ebook_factory.models import ProjectCreate
from ebook_factory.pipeline import PipelineRunner
from ebook_factory.repository import ProjectRepository
from ebook_factory.stages import DEFAULT_STAGE_HANDLERS, humanize_stage
from ebook_factory.workspace import compute_metrics

SLOP_CHAPTER = """# Rozdział testowy

W dzisiejszych czasach marketing odgrywa kluczową rolę w rozwoju organizacji.
Warto pamiętać, że kompleksowe rozwiązania rewolucjonizują pracę zespołów.
Ponadto należy podkreślić, że solidny fundament strategii jest ważny dla zespołu.
"""


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


def _project(repo, **overrides):
    data = dict(title="Test humanizacji", topic="automatyzacja sprzedaży", mode="lead-magnet")
    data.update(overrides)
    return repo.create_project(ProjectCreate(**data))


def test_stage_rewrites_chapters_and_writes_a_report(repo, projects_root):
    project = _project(repo, humanize_level="standard")
    project_dir = projects_root / project.slug
    (project_dir / "chapters").mkdir(parents=True)
    (project_dir / "qa").mkdir(parents=True)
    chapter = project_dir / "chapters" / "chapter-01.md"
    chapter.write_text(SLOP_CHAPTER, encoding="utf-8")

    result = humanize_stage(project, project_dir)

    assert result.success, result.message
    assert "W dzisiejszych czasach" not in chapter.read_text(encoding="utf-8")
    report = json.loads((project_dir / "qa" / "humanize.json").read_text(encoding="utf-8"))
    assert report["after"]["ai_score"] < report["before"]["ai_score"]
    assert report["level"] == "standard"
    assert report["chapters"][0]["file"] == "chapters/chapter-01.md"
    markdown = (project_dir / "qa" / "humanize-report.md").read_text(encoding="utf-8")
    assert "Raport humanizacji" in markdown
    assert "Rozdział po rozdziale" in markdown


def test_level_off_leaves_the_text_alone_but_still_reports(repo, projects_root):
    project = _project(repo, humanize_level="off")
    project_dir = projects_root / project.slug
    (project_dir / "chapters").mkdir(parents=True)
    (project_dir / "qa").mkdir(parents=True)
    chapter = project_dir / "chapters" / "chapter-01.md"
    chapter.write_text(SLOP_CHAPTER, encoding="utf-8")

    result = humanize_stage(project, project_dir)

    assert result.success
    assert chapter.read_text(encoding="utf-8") == SLOP_CHAPTER
    report = json.loads((project_dir / "qa" / "humanize.json").read_text(encoding="utf-8"))
    assert report["total_changes"] == 0
    assert report["after"]["ai_score"] == report["before"]["ai_score"]


def test_stage_reports_a_missing_draft_instead_of_crashing(repo, projects_root):
    project = _project(repo)
    project_dir = projects_root / project.slug
    (project_dir / "chapters").mkdir(parents=True)
    (project_dir / "qa").mkdir(parents=True)

    result = humanize_stage(project, project_dir)

    assert not result.success
    assert "draft" in result.message


def test_full_run_produces_human_reading_chapters_and_ships_the_report(repo, projects_root):
    project = _project(repo, humanize_level="strong")
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)

    result = runner.run(project.id)

    assert result.status == "completed", result.error
    project_dir = projects_root / project.slug
    report = json.loads((project_dir / "qa" / "humanize.json").read_text(encoding="utf-8"))
    assert report["after"]["ai_score"] <= HUMAN_SCORE_TARGET
    assert (project_dir / "delivery" / "humanize-report.md").is_file()

    metrics = compute_metrics(project_dir)
    assert metrics["ai_score"] == report["after"]["ai_score"]
    assert metrics["readability_grade"]


def test_qa_reports_readability_without_failing_the_build(repo, projects_root):
    project = _project(repo, humanize_level="off")
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)

    result = runner.run(project.id)

    assert result.status == "completed", result.error
    report = (projects_root / project.slug / "qa" / "qa-report.md").read_text(encoding="utf-8")
    assert "Ślad AI w tekście" in report
    assert "Rytm zdań zróżnicowany" in report
    assert "Czytelność i ślad AI" in report


def test_manuscript_opens_with_a_reader_facing_preface(repo, projects_root):
    project = _project(repo)
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    runner.run(project.id)

    manuscript = (projects_root / project.slug / "builds" / "manuscript.md").read_text(
        encoding="utf-8"
    )
    assert "## Jak czytać tę książkę" in manuscript
    assert "AI" in manuscript
