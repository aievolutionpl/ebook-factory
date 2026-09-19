import pytest

from ebook_factory.models import ProjectCreate, STAGE_DEFINITIONS
from ebook_factory.repository import ProjectRepository


MODES = ["lead-magnet", "guide", "premium"]


@pytest.fixture
def repo(tmp_path):
    r = ProjectRepository(tmp_path / "factory.db")
    yield r
    r.close()


def test_create_project_generates_sanitized_slug(repo):
    created = repo.create_project(
        ProjectCreate(title="AI dla Firm! Żółć & Ćma", topic="AI", mode="guide")
    )
    assert created.slug == "ai-dla-firm-zolc-cma"


def test_slug_is_unique_when_titles_collide(repo):
    first = repo.create_project(ProjectCreate(title="Same Title", topic="A", mode="guide"))
    second = repo.create_project(ProjectCreate(title="Same Title", topic="B", mode="guide"))
    assert first.slug != second.slug
    assert second.slug.startswith(first.slug)


@pytest.mark.parametrize("mode", MODES)
def test_create_project_accepts_all_three_modes(repo, mode):
    created = repo.create_project(ProjectCreate(title=f"Test {mode}", topic="X", mode=mode))
    assert created.mode == mode
    assert created.provider == "demo"
    assert created.status == "draft"
    assert created.progress == 0


def test_invalid_mode_is_rejected(repo):
    with pytest.raises(ValueError):
        ProjectCreate(title="Bad", topic="X", mode="not-a-real-mode")


def test_provider_is_validated(repo):
    created = repo.create_project(
        ProjectCreate(title="Provider", topic="X", mode="guide", provider="codex-cli")
    )
    assert created.provider == "codex-cli"
    with pytest.raises(ValueError):
        ProjectCreate(title="Bad provider", topic="X", mode="guide", provider="remote-api")


def test_source_materials_at_max_length_is_accepted(repo):
    materials = "x" * 50_000
    created = repo.create_project(
        ProjectCreate(title="Max source", topic="X", mode="guide", source_materials=materials)
    )
    assert created.source_materials == materials


def test_source_materials_over_max_length_is_rejected():
    materials = "x" * 50_001
    with pytest.raises(ValueError):
        ProjectCreate(title="Too long", topic="X", mode="guide", source_materials=materials)


def test_project_has_ordered_stages_matching_pipeline_definition(repo):
    created = repo.create_project(ProjectCreate(title="Stages", topic="X", mode="lead-magnet"))
    stages = repo.list_stages(created.id)
    assert [s.name for s in stages] == [d.name for d in STAGE_DEFINITIONS]
    assert [s.position for s in stages] == list(range(len(STAGE_DEFINITIONS)))
    assert all(s.status == "pending" for s in stages)
    assert all(s.attempts == 0 for s in stages)


def test_project_survives_repository_reopen(tmp_path):
    repo = ProjectRepository(tmp_path / "factory.db")
    created = repo.create_project(ProjectCreate(title="AI dla firm", topic="AI", mode="guide"))
    repo.close()
    reopened = ProjectRepository(tmp_path / "factory.db")
    assert reopened.get_project(created.id).title == "AI dla firm"
    reopened.close()


def test_old_database_without_provider_column_migrates_to_demo(tmp_path):
    import sqlite3

    db_path = tmp_path / "factory.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE projects (
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
            status TEXT NOT NULL,
            progress INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error TEXT
        );
        CREATE TABLE stages (
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
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        );
        INSERT INTO projects (
            id, slug, title, topic, mode, language, audience, brand, tone,
            source_materials, status, progress, created_at, updated_at, error
        ) VALUES (
            'old-id', 'old-project', 'Old Project', 'AI', 'guide', 'pl',
            '', '', '', NULL, 'draft', 0, '2026-01-01T00:00:00+00:00',
            '2026-01-01T00:00:00+00:00', NULL
        );
        """
    )
    conn.commit()
    conn.close()

    repo = ProjectRepository(db_path)
    try:
        migrated = repo.get_project("old-id")
        assert migrated.provider == "demo"
        created = repo.create_project(ProjectCreate(title="New", topic="AI", mode="guide"))
        assert created.provider == "demo"
    finally:
        repo.close()


def test_stages_survive_repository_reopen(tmp_path):
    repo = ProjectRepository(tmp_path / "factory.db")
    created = repo.create_project(ProjectCreate(title="Stages persist", topic="AI", mode="premium"))
    stage = repo.list_stages(created.id)[0]
    stage.status = "completed"
    stage.attempts = 1
    stage.message = "done"
    stage.artifact_paths = ["builds/x.txt"]
    repo.upsert_stage(created.id, stage)
    repo.close()

    reopened = ProjectRepository(tmp_path / "factory.db")
    stages = reopened.list_stages(created.id)
    assert stages[0].status == "completed"
    assert stages[0].attempts == 1
    assert stages[0].message == "done"
    assert stages[0].artifact_paths == ["builds/x.txt"]
    reopened.close()


def test_get_unknown_project_returns_none(repo):
    assert repo.get_project("does-not-exist") is None


def test_list_projects_returns_all_created(repo):
    repo.create_project(ProjectCreate(title="One", topic="A", mode="guide"))
    repo.create_project(ProjectCreate(title="Two", topic="B", mode="premium"))
    projects = repo.list_projects()
    assert len(projects) == 2
    assert {p.title for p in projects} == {"One", "Two"}


def test_update_project_persists_status_and_progress(repo):
    created = repo.create_project(ProjectCreate(title="Update me", topic="A", mode="guide"))
    updated = repo.update_project(created.id, status="running", progress=42)
    assert updated.status == "running"
    assert updated.progress == 42
    fetched = repo.get_project(created.id)
    assert fetched.status == "running"
    assert fetched.progress == 42
    assert fetched.updated_at >= created.updated_at


def test_append_event_and_list_events(repo):
    created = repo.create_project(ProjectCreate(title="Events", topic="A", mode="guide"))
    repo.append_event(created.id, level="info", message="started")
    repo.append_event(created.id, level="error", message="stage failed")
    events = repo.list_events(created.id)
    assert [e.message for e in events] == ["started", "stage failed"]
    assert events[0].level == "info"
    assert events[1].level == "error"


def test_events_survive_repository_reopen(tmp_path):
    repo = ProjectRepository(tmp_path / "factory.db")
    created = repo.create_project(ProjectCreate(title="Events persist", topic="A", mode="guide"))
    repo.append_event(created.id, level="info", message="hello")
    repo.close()

    reopened = ProjectRepository(tmp_path / "factory.db")
    events = reopened.list_events(created.id)
    assert len(events) == 1
    assert events[0].message == "hello"
    reopened.close()
