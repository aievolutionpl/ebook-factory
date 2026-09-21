import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from ebook_factory.models import STAGE_DEFINITIONS
from ebook_factory.api import ProjectAlreadyRunningError, WorkerRegistry
from ebook_factory.app import create_app
from ebook_factory.repository import ProjectRepository


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        yield c


def wait_for_status(client, project_id, target_statuses, timeout=30):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = client.get(f"/api/projects/{project_id}")
        last = r.json()
        if last["status"] in target_statuses:
            return last
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {target_statuses}, last={last}")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_and_fetch_project(client):
    r = client.post("/api/projects", json={"title": "AI dla firm", "topic": "AI", "mode": "guide"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "AI dla firm"
    assert body["provider"] == "demo"
    assert body["status"] == "draft"
    assert "stages" in body
    assert len(body["stages"]) == len(STAGE_DEFINITIONS)
    pid = body["id"]
    detail = client.get(f"/api/projects/{pid}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "AI dla firm"


def test_create_project_invalid_mode_returns_422(client):
    r = client.post("/api/projects", json={"title": "X", "topic": "Y", "mode": "not-a-mode"})
    assert r.status_code == 422


def test_create_project_accepts_and_returns_provider(client):
    r = client.post(
        "/api/projects",
        json={"title": "Agent", "topic": "AI", "mode": "guide", "provider": "claude-code"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider"] == "claude-code"
    detail = client.get(f"/api/projects/{body['id']}")
    assert detail.json()["provider"] == "claude-code"


def test_create_project_invalid_provider_returns_422(client):
    r = client.post(
        "/api/projects",
        json={"title": "Bad Agent", "topic": "AI", "mode": "guide", "provider": "remote-api"},
    )
    assert r.status_code == 422


def test_providers_endpoint_lists_availability(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    by_name = {entry["name"]: entry for entry in r.json()}
    assert set(by_name) == {"demo", "codex-cli", "claude-code"}
    assert by_name["demo"]["available"] is True
    assert by_name["codex-cli"]["label"] == "Codex CLI"


def test_create_project_missing_title_returns_422(client):
    r = client.post("/api/projects", json={"topic": "Y", "mode": "guide"})
    assert r.status_code == 422


def test_get_unknown_project_returns_404(client):
    r = client.get("/api/projects/does-not-exist")
    assert r.status_code == 404


def test_list_projects_returns_created_projects(client):
    client.post("/api/projects", json={"title": "One", "topic": "A", "mode": "guide"})
    client.post("/api/projects", json={"title": "Two", "topic": "B", "mode": "lead-magnet"})
    r = client.get("/api/projects")
    assert r.status_code == 200
    titles = {p["title"] for p in r.json()}
    assert titles == {"One", "Two"}


def test_start_unknown_project_returns_404(client):
    r = client.post("/api/projects/does-not-exist/start")
    assert r.status_code == 404


def test_start_runs_pipeline_to_completion(client):
    r = client.post("/api/projects", json={"title": "Run me", "topic": "Temat", "mode": "lead-magnet"})
    pid = r.json()["id"]

    start = client.post(f"/api/projects/{pid}/start")
    assert start.status_code == 202

    final = wait_for_status(client, pid, {"completed", "failed"}, timeout=60)
    assert final["status"] == "completed", final
    assert final["progress"] == 100


def test_start_twice_while_running_returns_409(client):
    r = client.post("/api/projects", json={"title": "Double start", "topic": "T", "mode": "lead-magnet"})
    pid = r.json()["id"]
    first = client.post(f"/api/projects/{pid}/start")
    assert first.status_code == 202
    second = client.post(f"/api/projects/{pid}/start")
    assert second.status_code == 409
    wait_for_status(client, pid, {"completed", "failed"}, timeout=60)


def test_pause_and_resume_completes_project(client):
    r = client.post("/api/projects", json={"title": "Pause me", "topic": "T", "mode": "guide"})
    pid = r.json()["id"]
    client.post(f"/api/projects/{pid}/start")

    pause_resp = client.post(f"/api/projects/{pid}/pause")
    assert pause_resp.status_code == 202

    paused = wait_for_status(client, pid, {"paused", "completed"}, timeout=60)
    if paused["status"] == "completed":
        pytest.skip("pipeline finished before pause could take effect")

    resume_resp = client.post(f"/api/projects/{pid}/resume")
    assert resume_resp.status_code == 202

    final = wait_for_status(client, pid, {"completed", "failed"}, timeout=60)
    assert final["status"] == "completed", final


def test_pause_when_not_running_returns_409(client):
    r = client.post("/api/projects", json={"title": "Not running", "topic": "T", "mode": "guide"})
    pid = r.json()["id"]
    resp = client.post(f"/api/projects/{pid}/pause")
    assert resp.status_code == 409


def test_cancel_draft_project_marks_cancelled(client):
    r = client.post("/api/projects", json={"title": "Cancel me", "topic": "T", "mode": "guide"})
    pid = r.json()["id"]
    resp = client.post(f"/api/projects/{pid}/cancel")
    assert resp.status_code == 202
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["status"] == "cancelled"


def test_events_endpoint_lists_events_after_run(client):
    r = client.post("/api/projects", json={"title": "Events", "topic": "T", "mode": "lead-magnet"})
    pid = r.json()["id"]
    client.post(f"/api/projects/{pid}/start")
    wait_for_status(client, pid, {"completed", "failed"}, timeout=60)

    events = client.get(f"/api/projects/{pid}/events")
    assert events.status_code == 200
    assert len(events.json()) > 0


def test_events_unknown_project_returns_404(client):
    r = client.get("/api/projects/does-not-exist/events")
    assert r.status_code == 404


def test_download_before_completion_returns_404(client):
    r = client.post("/api/projects", json={"title": "No download yet", "topic": "T", "mode": "guide"})
    pid = r.json()["id"]
    resp = client.get(f"/api/projects/{pid}/download")
    assert resp.status_code == 404


def test_download_after_completion_returns_zip_with_safe_filename(client):
    r = client.post("/api/projects", json={"title": "Download me", "topic": "T", "mode": "lead-magnet"})
    pid = r.json()["id"]
    client.post(f"/api/projects/{pid}/start")
    wait_for_status(client, pid, {"completed", "failed"}, timeout=60)

    resp = client.get(f"/api/projects/{pid}/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    disposition = resp.headers["content-disposition"]
    assert "attachment" in disposition
    assert ".." not in disposition
    assert "/" not in disposition.split("filename=")[-1]
    assert resp.content[:2] == b"PK"


def test_download_unknown_project_returns_404(client):
    r = client.get("/api/projects/does-not-exist/download")
    assert r.status_code == 404


def test_download_rejects_stale_zip_when_project_not_completed(client, tmp_path):
    r = client.post("/api/projects", json={"title": "Stale zip", "topic": "T", "mode": "guide"})
    pid = r.json()["id"]
    slug = client.get(f"/api/projects/{pid}").json()["slug"]

    # Simulate leftover/residue artifacts from a prior failed or duplicate run:
    # a delivery.zip exists on disk even though the project never completed.
    delivery_dir = tmp_path / "projects" / slug / "delivery"
    delivery_dir.mkdir(parents=True)
    (delivery_dir / "delivery.zip").write_bytes(b"PK\x03\x04stale")
    (delivery_dir / "manifest.json").write_text("{}")

    resp = client.get(f"/api/projects/{pid}/download")
    assert resp.status_code == 404


def test_create_project_rejects_source_materials_over_max_length(client):
    r = client.post(
        "/api/projects",
        json={
            "title": "Too long",
            "topic": "T",
            "mode": "guide",
            "source_materials": "x" * 50_001,
        },
    )
    assert r.status_code == 422


def test_create_project_accepts_source_materials_at_max_length(client):
    r = client.post(
        "/api/projects",
        json={
            "title": "Just right",
            "topic": "T",
            "mode": "guide",
            "source_materials": "x" * 50_000,
        },
    )
    assert r.status_code == 201


def test_worker_registry_start_is_atomic_under_concurrency():
    starts = []
    starts_lock = threading.Lock()
    barrier = threading.Barrier(25)

    class FakeResult:
        status = "completed"

    class FakeRunner:
        def run(self, project_id, stop_requested=lambda: False):
            with starts_lock:
                starts.append(project_id)
            time.sleep(0.05)
            return FakeResult()

    class FakeRepository:
        def update_project(self, *args, **kwargs):
            pass

    registry = WorkerRegistry()
    runner = FakeRunner()
    repository = FakeRepository()
    outcomes = []
    outcomes_lock = threading.Lock()

    def attempt_start():
        barrier.wait()
        try:
            registry.start("shared-project", runner, repository)
            outcome = "started"
        except ProjectAlreadyRunningError:
            outcome = "blocked"
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=attempt_start) for _ in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    registry.join_all(timeout=5)

    assert outcomes.count("started") == 1
    assert outcomes.count("blocked") == 24
    assert len(starts) == 1


def test_concurrent_start_requests_only_launch_one_worker(client):
    r = client.post(
        "/api/projects", json={"title": "Race condition", "topic": "T", "mode": "lead-magnet"}
    )
    pid = r.json()["id"]

    def do_start():
        return client.post(f"/api/projects/{pid}/start")

    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(pool.map(lambda _: do_start(), range(20)))

    statuses = [resp.status_code for resp in responses]
    assert statuses.count(202) == 1, statuses
    assert statuses.count(409) == 19, statuses

    wait_for_status(client, pid, {"completed", "failed"}, timeout=60)


def _create_project(client, **overrides):
    payload = {"title": "Sources demo", "topic": "T", "mode": "guide"}
    payload.update(overrides)
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_source_returns_stored_metadata(client):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("notes.txt", b"unikalny fragment ZQX987", "text/plain"))],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["filename"] == "notes.txt"
    assert entry["stored_path"] == "sources/notes.txt"
    assert entry["size_bytes"] == len(b"unikalny fragment ZQX987")
    assert entry["extraction_status"] == "extracted"
    assert entry["extracted_chars"] > 0


def test_upload_source_for_unknown_project_returns_404(client):
    resp = client.post(
        "/api/projects/does-not-exist/sources",
        files=[("files", ("notes.txt", b"content", "text/plain"))],
    )
    assert resp.status_code == 404


def test_upload_source_rejects_unsupported_extension(client, tmp_path):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("script.exe", b"binary", "application/octet-stream"))],
    )
    assert resp.status_code == 422
    sources_dir = tmp_path / "projects" / project["slug"] / "sources"
    assert not sources_dir.exists() or not any(sources_dir.iterdir())


def test_upload_source_rejects_empty_file(client):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("empty.txt", b"", "text/plain"))],
    )
    assert resp.status_code == 422


def test_upload_source_rejects_oversized_file(client):
    project = _create_project(client)
    too_big = b"a" * (5 * 1024 * 1024 + 1)
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("big.txt", too_big, "text/plain"))],
    )
    assert resp.status_code == 422


def test_upload_source_rejects_more_than_five_files_per_project(client):
    project = _create_project(client)
    files = [
        ("files", (f"note-{i}.txt", f"content {i}".encode(), "text/plain")) for i in range(6)
    ]
    resp = client.post(f"/api/projects/{project['id']}/sources", files=files)
    assert resp.status_code == 422


def test_upload_source_rejects_sixth_file_across_separate_requests(client):
    project = _create_project(client)
    for i in range(5):
        resp = client.post(
            f"/api/projects/{project['id']}/sources",
            files=[("files", (f"note-{i}.txt", f"content {i}".encode(), "text/plain"))],
        )
        assert resp.status_code == 201, resp.text

    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("note-6.txt", b"one too many", "text/plain"))],
    )
    assert resp.status_code == 422


def test_upload_source_sanitizes_path_traversal_filename(client, tmp_path):
    project = _create_project(client)
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("../../etc/passwd.txt", b"pwned", "text/plain"))],
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()[0]
    assert entry["filename"] == "passwd.txt"
    assert "/" not in entry["filename"]
    assert not (tmp_path / "etc").exists()


def test_upload_source_appends_extracted_text_to_source_materials_without_exceeding_cap(
    client, tmp_path
):
    project = _create_project(client, source_materials="x" * 49_990)
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("notes.txt", b"y" * 100, "text/plain"))],
    )
    assert resp.status_code == 201, resp.text

    repo = ProjectRepository(tmp_path / "factory.db")
    try:
        stored = repo.get_project(project["id"])
    finally:
        repo.close()
    assert stored.source_materials is not None
    assert len(stored.source_materials) <= 50_000
    assert stored.source_materials.startswith("x" * 49_990)


def test_uploaded_source_text_flows_into_strategy_and_research_stages(client, tmp_path):
    project = _create_project(client)
    marker = "UNIKALNY-MARKER-UPLOAD-42"
    resp = client.post(
        f"/api/projects/{project['id']}/sources",
        files=[("files", ("notes.txt", marker.encode("utf-8"), "text/plain"))],
    )
    assert resp.status_code == 201, resp.text

    start = client.post(f"/api/projects/{project['id']}/start")
    assert start.status_code == 202
    wait_for_status(client, project["id"], {"completed", "failed"}, timeout=60)

    strategy_path = tmp_path / "projects" / project["slug"] / "outline" / "strategy.md"
    research_path = tmp_path / "projects" / project["slug"] / "research" / "notes.md"
    assert marker in strategy_path.read_text(encoding="utf-8")
    assert marker in research_path.read_text(encoding="utf-8")


def test_unavailable_provider_fails_before_stage_execution(client, tmp_path, monkeypatch):
    missing = tmp_path / "missing-codex"
    monkeypatch.setenv("EBOOK_FACTORY_CODEX_CLI", str(missing))
    r = client.post(
        "/api/projects",
        json={"title": "No agent", "topic": "T", "mode": "lead-magnet", "provider": "codex-cli"},
    )
    pid = r.json()["id"]

    start = client.post(f"/api/projects/{pid}/start")
    assert start.status_code == 202
    final = wait_for_status(client, pid, {"completed", "failed"}, timeout=10)

    assert final["status"] == "failed"
    assert "provider codex-cli is not available" in final["error"]
    stages = client.get(f"/api/projects/{pid}").json()["stages"]
    assert stages[0]["status"] == "pending"


# ------------------------------------------------- writing style & humanizer


def test_create_accepts_writing_style_and_humanize_level(client):
    r = client.post(
        "/api/projects",
        json={
            "title": "Styl i humanizacja",
            "topic": "automatyzacja sprzedaży",
            "mode": "lead-magnet",
            "writing_style": "narrative",
            "humanize_level": "strong",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["writing_style"] == "narrative"
    assert body["humanize_level"] == "strong"


def test_create_defaults_to_practical_standard(client):
    r = client.post(
        "/api/projects",
        json={"title": "Domyślne", "topic": "temat", "mode": "lead-magnet"},
    )
    body = r.json()
    assert body["writing_style"] == "practical"
    assert body["humanize_level"] == "standard"


def test_invalid_writing_style_is_rejected(client):
    r = client.post(
        "/api/projects",
        json={
            "title": "Zły styl",
            "topic": "temat",
            "mode": "lead-magnet",
            "writing_style": "poetycki",
        },
    )
    assert r.status_code == 422


def test_patch_updates_the_writing_setup(client):
    project = client.post(
        "/api/projects",
        json={"title": "Do zmiany", "topic": "temat", "mode": "lead-magnet"},
    ).json()

    r = client.patch(
        f"/api/projects/{project['id']}",
        json={"writing_style": "expert", "humanize_level": "off"},
    )

    assert r.status_code == 200
    assert r.json()["writing_style"] == "expert"
    assert r.json()["humanize_level"] == "off"


def test_duplicate_carries_the_writing_setup(client):
    project = client.post(
        "/api/projects",
        json={
            "title": "Do skopiowania",
            "topic": "temat",
            "mode": "lead-magnet",
            "writing_style": "expert",
            "humanize_level": "light",
        },
    ).json()

    clone = client.post(f"/api/projects/{project['id']}/duplicate").json()

    assert clone["writing_style"] == "expert"
    assert clone["humanize_level"] == "light"


def test_version_advertises_the_new_knobs(client):
    body = client.get("/api/version").json()
    assert body["writing_styles"] == ["practical", "narrative", "expert"]
    assert body["humanize_levels"] == ["off", "light", "standard", "strong"]


def test_readability_endpoint_is_empty_before_a_run(client):
    project = client.post(
        "/api/projects",
        json={"title": "Bez treści", "topic": "temat", "mode": "lead-magnet"},
    ).json()

    body = client.get(f"/api/projects/{project['id']}/readability").json()

    assert body["source"] == "empty"
    assert body["after"] is None
    assert body["level_label"]
    assert body["style_label"]


def test_readability_endpoint_reports_the_finished_book(client):
    project = client.post(
        "/api/projects",
        json={"title": "Do oceny", "topic": "automatyzacja sprzedaży", "mode": "lead-magnet"},
    ).json()
    client.post(f"/api/projects/{project['id']}/start")
    wait_for_status(client, project["id"], {"completed", "failed"}, timeout=120)

    body = client.get(f"/api/projects/{project['id']}/readability").json()

    assert body["source"] == "humanize-stage"
    assert body["after"]["ai_score"] <= body["target"]
    assert body["chapters"]
    assert "findings" in body["after"]


def test_readability_endpoint_404s_for_an_unknown_project(client):
    assert client.get("/api/projects/nope/readability").status_code == 404
