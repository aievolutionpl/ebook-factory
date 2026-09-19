import time

import pytest
from fastapi.testclient import TestClient

from ebook_factory.app import create_app


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
    assert body["status"] == "draft"
    assert "stages" in body
    assert len(body["stages"]) == 11
    pid = body["id"]
    detail = client.get(f"/api/projects/{pid}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "AI dla firm"


def test_create_project_invalid_mode_returns_422(client):
    r = client.post("/api/projects", json={"title": "X", "topic": "Y", "mode": "not-a-mode"})
    assert r.status_code == 422


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
