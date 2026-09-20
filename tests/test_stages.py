import json
import zipfile

import pytest

from ebook_factory.artifacts import build_pdf
from ebook_factory.models import MODE_CONFIG, Project, ProjectCreate
from ebook_factory.pipeline import PipelineRunner
from ebook_factory.repository import ProjectRepository
from ebook_factory.stages import DEFAULT_STAGE_HANDLERS, qa_stage, research_stage, strategy_stage

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


def _make_project(**overrides) -> Project:
    base = dict(
        id="p1",
        slug="p1",
        title="Tytul testowy",
        topic="Temat testowy",
        mode="guide",
        language="pl",
        audience="Odbiorcy",
        brand="Marka",
        tone="rzeczowy",
        source_materials=None,
        status="draft",
        progress=0,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        error=None,
    )
    base.update(overrides)
    return Project(**base)


def test_strategy_stage_includes_provided_source_materials(tmp_path):
    project = _make_project(source_materials="UNIKALNY-FRAGMENT-ZRODLOWY-12345")
    project_dir = tmp_path / "proj"
    (project_dir / "outline").mkdir(parents=True)

    result = strategy_stage(project, project_dir)

    assert result.success
    content = (project_dir / "outline" / "strategy.md").read_text(encoding="utf-8")
    assert "UNIKALNY-FRAGMENT-ZRODLOWY-12345" in content


def test_strategy_stage_omits_source_materials_section_when_absent(tmp_path):
    project = _make_project(source_materials=None)
    project_dir = tmp_path / "proj"
    (project_dir / "outline").mkdir(parents=True)

    strategy_stage(project, project_dir)

    content = (project_dir / "outline" / "strategy.md").read_text(encoding="utf-8")
    assert "Materiały źródłowe" not in content


def test_research_stage_includes_provided_source_materials(tmp_path):
    project = _make_project(source_materials="INNY-UNIKALNY-FRAGMENT-67890")
    project_dir = tmp_path / "proj"
    (project_dir / "research").mkdir(parents=True)

    result = research_stage(project, project_dir)

    assert result.success
    content = (project_dir / "research" / "notes.md").read_text(encoding="utf-8")
    assert "INNY-UNIKALNY-FRAGMENT-67890" in content


def test_research_stage_omits_source_materials_section_when_absent(tmp_path):
    project = _make_project(source_materials=None)
    project_dir = tmp_path / "proj"
    (project_dir / "research").mkdir(parents=True)

    research_stage(project, project_dir)

    content = (project_dir / "research" / "notes.md").read_text(encoding="utf-8")
    assert "Materiały źródłowe" not in content


def _prepare_qa_dirs(project_dir):
    for sub in ("builds", "images", "marketing", "qa", "chapters"):
        (project_dir / sub).mkdir(parents=True)


def test_qa_stage_fails_pdf_check_when_pdf_has_no_pages_or_text(tmp_path):
    project = _make_project(mode="lead-magnet")
    project_dir = tmp_path / "proj"
    _prepare_qa_dirs(project_dir)
    (project_dir / "builds" / "book.pdf").write_bytes(b"%PDF-1.4\n%%EOF")

    qa_stage(project, project_dir)

    report = (project_dir / "qa" / "qa-report.md").read_text(encoding="utf-8")
    pdf_lines = [line for line in report.splitlines() if "PDF" in line]
    assert pdf_lines, report
    assert all("[FAIL]" in line for line in pdf_lines), report


def test_qa_stage_passes_pdf_check_for_pdf_with_pages_and_text(tmp_path):
    project = _make_project(mode="lead-magnet")
    project_dir = tmp_path / "proj"
    _prepare_qa_dirs(project_dir)
    build_pdf(
        project_dir / "builds" / "book.pdf",
        title="Tytul",
        chapters=[("Rozdzial", "<p>Zdanie z prawdziwa trescia do odczytania.</p>")],
        typst_binary=None,
    )

    qa_stage(project, project_dir)

    report = (project_dir / "qa" / "qa-report.md").read_text(encoding="utf-8")
    pdf_lines = [line for line in report.splitlines() if "PDF" in line]
    assert pdf_lines, report
    assert all("[PASS]" in line for line in pdf_lines), report


# --------------------------------------------------------------- v2 stages


def test_custom_chapter_titles_replace_the_mode_preset(repo, projects_root):
    from ebook_factory.models import ProjectCreate
    from ebook_factory.pipeline import PipelineRunner
    from ebook_factory.stages import DEFAULT_STAGE_HANDLERS, resolve_chapter_titles

    project = repo.create_project(
        ProjectCreate(
            title="Wlasna struktura",
            topic="temat",
            mode="premium",
            chapter_titles=["Alfa", "Beta"],
        )
    )
    titles, source = resolve_chapter_titles(project)
    assert titles == ["Alfa", "Beta"]
    assert source == "custom"

    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    result = runner.run(project.id)
    assert result.status == "completed"

    outline = json.loads(
        (projects_root / project.slug / "outline" / "outline.json").read_text(encoding="utf-8")
    )
    assert [c["title"] for c in outline["chapters"]] == ["Alfa", "Beta"]
    assert outline["structure_source"] == "custom"
    assert len(list((projects_root / project.slug / "chapters").glob("chapter-*.md"))) == 2


def test_preset_structure_repeats_templates_for_long_modes():
    from ebook_factory.models import Project
    from ebook_factory.stages import CHAPTER_TEMPLATES, resolve_chapter_titles

    project = Project(
        id="x", slug="x", title="t", topic="t", mode="premium", language="pl",
        audience="", brand="", tone="", source_materials=None, status="draft",
        progress=0, created_at="", updated_at="",
    )
    titles, source = resolve_chapter_titles(project)
    assert source == "preset"
    assert len(titles) == 14
    assert len(set(titles)) == 14
    assert titles[0] == CHAPTER_TEMPLATES[0]


def test_published_book_carries_title_page_toc_and_colophon(repo, projects_root):
    from ebook_factory.models import ProjectCreate
    from ebook_factory.pipeline import PipelineRunner
    from ebook_factory.stages import DEFAULT_STAGE_HANDLERS

    project = repo.create_project(
        ProjectCreate(title="Front matter", topic="temat", mode="lead-magnet", brand="Marka")
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    assert runner.run(project.id).status == "completed"

    with zipfile.ZipFile(projects_root / project.slug / "builds" / "book.epub") as zf:
        nav = zf.read("OEBPS/nav.xhtml").decode("utf-8")
        first = zf.read("OEBPS/chapter-01.xhtml").decode("utf-8")
    assert "Strona tytulowa" in nav
    assert "Spis tresci" in nav
    assert "Nota o powstaniu materialu" in nav
    assert "Marka" in first


def test_delivery_package_includes_manuscript_outline_and_readme(repo, projects_root):
    from ebook_factory.models import ProjectCreate
    from ebook_factory.pipeline import PipelineRunner
    from ebook_factory.stages import DEFAULT_STAGE_HANDLERS

    project = repo.create_project(
        ProjectCreate(title="Pelna paczka", topic="temat", mode="lead-magnet")
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    assert runner.run(project.id).status == "completed"

    delivery_dir = projects_root / project.slug / "delivery"
    with zipfile.ZipFile(delivery_dir / "delivery.zip") as zf:
        names = set(zf.namelist())
    assert {
        "book.pdf",
        "book.epub",
        "manuscript.md",
        "outline.json",
        "strategy.md",
        "research-notes.md",
        "fact-check.md",
        "metrics.json",
        "cover.svg",
        "README.md",
        "manifest.json",
    } <= names

    manifest = json.loads((delivery_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_names = {entry["name"] for entry in manifest["files"]}
    assert "manuscript.md" in manifest_names
    assert all(entry["sha256"] for entry in manifest["files"])

    readme = (delivery_dir / "README.md").read_text(encoding="utf-8")
    assert "Pelna paczka" in readme
    assert "Przed publikacja" in readme


def test_qa_report_records_material_metrics(repo, projects_root):
    from ebook_factory.models import ProjectCreate
    from ebook_factory.pipeline import PipelineRunner
    from ebook_factory.stages import DEFAULT_STAGE_HANDLERS

    project = repo.create_project(
        ProjectCreate(title="Metryki", topic="temat", mode="lead-magnet")
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    assert runner.run(project.id).status == "completed"

    qa_dir = projects_root / project.slug / "qa"
    report = (qa_dir / "qa-report.md").read_text(encoding="utf-8")
    assert "Metryki materialu" in report
    metrics = json.loads((qa_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["chapters"] == 5
    assert metrics["words"] > 0


def test_qa_chapter_check_follows_the_outline_not_the_mode_preset(repo, projects_root):
    """A three-chapter custom structure must not fail the guide-mode check."""
    from ebook_factory.models import ProjectCreate
    from ebook_factory.pipeline import PipelineRunner
    from ebook_factory.stages import DEFAULT_STAGE_HANDLERS

    project = repo.create_project(
        ProjectCreate(
            title="Krotka struktura",
            topic="temat",
            mode="guide",
            chapter_titles=["Jeden", "Dwa", "Trzy"],
        )
    )
    runner = PipelineRunner(repo, projects_root, stage_handlers=DEFAULT_STAGE_HANDLERS)
    assert runner.run(project.id).status == "completed"
    report = (projects_root / project.slug / "qa" / "qa-report.md").read_text(encoding="utf-8")
    assert "[PASS] Liczba rozdzialow >= 3" in report
