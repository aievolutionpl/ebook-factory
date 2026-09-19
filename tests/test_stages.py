import json
import zipfile

import pytest

from ebook_factory.models import MODE_CONFIG, ProjectCreate
from ebook_factory.pipeline import PipelineRunner
from ebook_factory.repository import ProjectRepository
from ebook_factory.stages import DEFAULT_STAGE_HANDLERS

REQUIRED_DELIVERY_FILES = {
    "book.pdf",
    "book.epub",
    "cover.png",
    "offer.md",
    "landing.html",
    "posts.md",
    "ads.md",
    "qa-report.md",
    "manifest.json",
}


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


def test_lead_magnet_runs_to_completion_with_full_delivery(repo, projects_root):
    project = repo.create_project(
        ProjectCreate(
            title="AI dla malych firm",
            topic="Automatyzacja AI w malej firmie",
            mode="lead-magnet",
            audience="wlasciciele malych firm",
            brand="Ebook Factory Demo",
            tone="rzeczowy",
        )
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)

    result = runner.run(project.id)

    assert result.status == "completed", result.error
    assert result.progress == 100

    delivery_dir = projects_root / project.slug / "delivery"
    present = {p.name for p in delivery_dir.iterdir()}
    assert REQUIRED_DELIVERY_FILES.issubset(present)
    assert (delivery_dir / "delivery.zip").exists()

    with zipfile.ZipFile(delivery_dir / "delivery.zip") as zf:
        zip_names = set(zf.namelist())
    assert REQUIRED_DELIVERY_FILES.issubset(zip_names)

    manifest = json.loads((delivery_dir / "manifest.json").read_text())
    manifest_names = {entry["name"] for entry in manifest["files"]}
    # manifest.json cannot hash itself; every other delivered file must be listed
    assert (REQUIRED_DELIVERY_FILES - {"manifest.json"}).issubset(manifest_names)

    assert (delivery_dir / "book.pdf").read_bytes().startswith(b"%PDF")

    with zipfile.ZipFile(delivery_dir / "book.epub") as zf:
        first = zf.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED

    landing_html = (delivery_dir / "landing.html").read_text()
    assert "viewport" in landing_html

    chapters_dir = projects_root / project.slug / "chapters"
    chapter_files = sorted(chapters_dir.glob("chapter-*.md"))
    assert len(chapter_files) >= MODE_CONFIG["lead-magnet"].chapter_count


@pytest.mark.parametrize("mode", ["lead-magnet", "guide", "premium"])
def test_every_mode_completes_with_minimum_chapter_count(repo, projects_root, mode):
    project = repo.create_project(
        ProjectCreate(title=f"Test {mode}", topic="Produktywnosc", mode=mode)
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)

    result = runner.run(project.id)

    assert result.status == "completed", result.error
    chapters_dir = projects_root / project.slug / "chapters"
    chapter_files = list(chapters_dir.glob("chapter-*.md"))
    assert len(chapter_files) == MODE_CONFIG[mode].chapter_count


def test_research_notes_are_clearly_marked_as_demo(repo, projects_root):
    project = repo.create_project(
        ProjectCreate(title="Demo marking", topic="Temat", mode="lead-magnet")
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    runner.run(project.id)

    notes = (projects_root / project.slug / "research" / "notes.md").read_text()
    assert "DEMO" in notes.upper()
