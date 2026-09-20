"""API contract tests for the artifact, metrics and lifecycle endpoints."""

import time

import pytest
from fastapi.testclient import TestClient

from ebook_factory.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path, auth_credentials=None)
    with TestClient(app) as c:
        c.app_state = app.state
        yield c


def create_project(client, **overrides):
    payload = {"title": "AI dla firm", "topic": "AI w praktyce", "mode": "lead-magnet"}
    payload.update(overrides)
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def wait_for_finish(client, project_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/projects/{project_id}").json()
        if body["status"] in ("completed", "failed", "cancelled"):
            return body
        time.sleep(0.1)
    raise AssertionError("pipeline did not finish in time")


def run_to_completion(client, project_id, timeout=60):
    assert client.post(f"/api/projects/{project_id}/start").status_code == 202
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/projects/{project_id}").json()
        if body["status"] in ("completed", "failed", "cancelled"):
            return body
        time.sleep(0.1)
    raise AssertionError("pipeline did not finish in time")


# ------------------------------------------------------------------ stats


def test_stats_reports_counts_by_status(client):
    assert client.get("/api/stats").json() == {
        "total": 0,
        "by_status": {},
        "running": 0,
        "completed": 0,
        "failed": 0,
    }
    create_project(client)
    stats = client.get("/api/stats").json()
    assert stats["total"] == 1
    assert stats["by_status"]["draft"] == 1


# -------------------------------------------------------- chapter structure


def test_custom_chapter_titles_are_normalized_and_drive_the_outline(client):
    project = create_project(
        client,
        chapter_titles=["  Start  ", "Narzędzia", "start", "", "Wdrożenie"],
    )
    assert project["chapter_titles"] == ["Start", "Narzędzia", "Wdrożenie"]

    finished = run_to_completion(client, project["id"])
    assert finished["status"] == "completed"

    metrics = client.get(f"/api/projects/{project['id']}/metrics").json()
    assert metrics["chapters"] == 3
    assert [row["title"] for row in metrics["chapter_breakdown"]] == [
        "Start",
        "Narzędzia",
        "Wdrożenie",
    ]


def test_too_many_chapter_titles_are_rejected(client):
    response = client.post(
        "/api/projects",
        json={
            "title": "Za duzo",
            "topic": "temat",
            "mode": "guide",
            "chapter_titles": [f"Rozdzial {i}" for i in range(60)],
        },
    )
    assert response.status_code == 422


# ------------------------------------------------------------- artifacts


def test_artifacts_endpoint_lists_real_files_grouped_by_category(client):
    project = create_project(client)
    empty = client.get(f"/api/projects/{project['id']}/artifacts").json()
    assert empty["count"] == 0

    run_to_completion(client, project["id"])
    listing = client.get(f"/api/projects/{project['id']}/artifacts").json()
    categories = {group["category"] for group in listing["groups"]}
    assert {"delivery", "builds", "chapters", "marketing", "qa"} <= categories
    assert listing["count"] > 10
    assert listing["total_bytes"] > 0

    delivery = next(g for g in listing["groups"] if g["category"] == "delivery")
    names = {f["name"] for f in delivery["files"]}
    assert {"book.pdf", "book.epub", "manuscript.md", "README.md"} <= names


def test_artifact_preview_returns_text_for_markdown(client):
    project = create_project(client)
    run_to_completion(client, project["id"])
    response = client.get(
        f"/api/projects/{project['id']}/artifacts/preview",
        params={"path": "outline/strategy.md"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "text"
    assert "Strategia" in body["text"]
    assert body["truncated"] is False


def test_artifact_preview_refuses_binary_artifacts(client):
    project = create_project(client)
    run_to_completion(client, project["id"])
    response = client.get(
        f"/api/projects/{project['id']}/artifacts/preview",
        params={"path": "builds/book.pdf"},
    )
    assert response.status_code == 415


def test_raw_artifact_serves_images_inline_but_never_html(client):
    project = create_project(client)
    run_to_completion(client, project["id"])

    png = client.get(
        f"/api/projects/{project['id']}/artifacts/raw", params={"path": "images/cover.png"}
    )
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.headers["content-disposition"].startswith("inline")
    assert png.headers["x-content-type-options"] == "nosniff"

    # Generated HTML and SVG can carry script, so they must never render on
    # the app's own origin.
    for path in ("marketing/landing.html", "images/cover.svg"):
        response = client.get(
            f"/api/projects/{project['id']}/artifacts/raw", params={"path": path}
        )
        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment")
        assert response.headers["content-type"].startswith("application/octet-stream")


def test_raw_artifact_download_flag_forces_attachment(client):
    project = create_project(client)
    run_to_completion(client, project["id"])
    response = client.get(
        f"/api/projects/{project['id']}/artifacts/raw",
        params={"path": "images/cover.png", "download": "true"},
    )
    assert response.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize("path", ["../../factory.db", "/etc/passwd", "outline/../../x"])
def test_raw_artifact_rejects_path_traversal(client, path):
    project = create_project(client)
    run_to_completion(client, project["id"])
    response = client.get(
        f"/api/projects/{project['id']}/artifacts/raw", params={"path": path}
    )
    assert response.status_code == 400


def test_artifact_endpoints_404_for_unknown_project(client):
    assert client.get("/api/projects/nope/artifacts").status_code == 404
    assert client.get("/api/projects/nope/metrics").status_code == 404


# --------------------------------------------------------------- metrics


def test_metrics_reflect_generated_manuscript(client):
    project = create_project(client)
    run_to_completion(client, project["id"])
    metrics = client.get(f"/api/projects/{project['id']}/metrics").json()
    assert metrics["chapters"] == 5
    assert metrics["words"] > 100
    assert metrics["estimated_pages"] >= 1
    assert metrics["artifacts"] > 10


# ---------------------------------------------------------------- events


def test_events_support_incremental_polling_and_limit(client):
    project = create_project(client)
    run_to_completion(client, project["id"])
    all_events = client.get(f"/api/projects/{project['id']}/events").json()
    assert len(all_events) > 3

    tail = client.get(
        f"/api/projects/{project['id']}/events",
        params={"after_id": all_events[1]["id"]},
    ).json()
    assert len(tail) == len(all_events) - 2
    assert tail[0]["id"] == all_events[2]["id"]

    limited = client.get(
        f"/api/projects/{project['id']}/events", params={"limit": 2}
    ).json()
    assert len(limited) == 2

    unknown = client.get(
        f"/api/projects/{project['id']}/events", params={"after_id": "does-not-exist"}
    ).json()
    assert len(unknown) == len(all_events)


# --------------------------------------------------------------- lifecycle


def test_patch_updates_settings_and_logs_an_event(client):
    project = create_project(client)
    response = client.patch(
        f"/api/projects/{project['id']}",
        json={"audience": "mikrofirmy", "tone": "konkretny", "chapter_titles": ["A", "B"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["audience"] == "mikrofirmy"
    assert body["chapter_titles"] == ["A", "B"]
    assert body["topic"] == project["topic"]

    events = client.get(f"/api/projects/{project['id']}/events").json()
    assert any("settings updated" in event["message"] for event in events)


def test_patch_rejects_blank_required_fields(client):
    project = create_project(client)
    assert client.patch(f"/api/projects/{project['id']}", json={"title": "   "}).status_code == 422


def test_patch_rejects_running_project(client, tmp_path):
    app = create_app(tmp_path / "patch", auth_credentials=None)
    with TestClient(app) as patch_client:
        project = create_project(patch_client)
        app.state.repository.update_project(project["id"], status="running")
        response = patch_client.patch(
            f"/api/projects/{project['id']}", json={"tone": "inny"}
        )
        assert response.status_code == 409


def test_duplicate_clones_settings_without_artifacts(client):
    project = create_project(client, chapter_titles=["Jeden", "Dwa"], brand="Marka")
    run_to_completion(client, project["id"])

    response = client.post(f"/api/projects/{project['id']}/duplicate")
    assert response.status_code == 201
    clone = response.json()
    assert clone["title"] == project["title"] + " (kopia)"
    assert clone["chapter_titles"] == ["Jeden", "Dwa"]
    assert clone["brand"] == "Marka"
    assert clone["status"] == "draft"
    assert clone["progress"] == 0
    assert clone["id"] != project["id"]
    assert all(stage["status"] == "pending" for stage in clone["stages"])
    assert client.get(f"/api/projects/{clone['id']}/artifacts").json()["count"] == 0


def test_delete_removes_project_rows_and_workspace(client, tmp_path):
    project = create_project(client)
    run_to_completion(client, project["id"])
    project_dir = tmp_path / "projects" / project["slug"]
    assert project_dir.is_dir()

    response = client.delete(f"/api/projects/{project['id']}")
    assert response.status_code == 200
    assert response.json()["deleted"] == project["id"]
    assert not project_dir.exists()
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert client.get("/api/projects").json() == []


def test_delete_unknown_project_is_404(client):
    assert client.delete("/api/projects/missing").status_code == 404


def test_retry_resets_failed_stages_and_reruns(client, tmp_path):
    """A stage that fails once is replayed from its own position on retry."""
    from ebook_factory.pipeline import StageResult
    from ebook_factory.stages import DEFAULT_STAGE_HANDLERS

    # MAX_STAGE_ATTEMPTS in-run retries must be exhausted before the project
    # itself is marked failed, so the handler fails three times.
    calls = {"count": 0}

    def flaky_outline(project, project_dir):
        calls["count"] += 1
        if calls["count"] <= 3:
            return StageResult(False, "boom")
        return DEFAULT_STAGE_HANDLERS["outline"](project, project_dir)

    handlers = dict(DEFAULT_STAGE_HANDLERS)
    handlers["outline"] = flaky_outline

    app = create_app(tmp_path / "retry", auth_credentials=None)
    app.state.runner.stage_handlers = handlers
    with TestClient(app) as retry_client:
        project = create_project(retry_client)
        finished = run_to_completion(retry_client, project["id"])
        assert finished["status"] == "failed"
        assert "outline" in finished["error"]

        response = retry_client.post(f"/api/projects/{project['id']}/retry")
        assert response.status_code == 202

        after = wait_for_finish(retry_client, project["id"])
        assert after["status"] == "completed"
        stages = {s["name"]: s for s in after["stages"]}
        assert stages["strategy"]["status"] == "completed"
        assert stages["outline"]["attempts"] == 1


def test_retry_refuses_projects_that_are_not_stopped(client):
    project = create_project(client)
    assert client.post(f"/api/projects/{project['id']}/retry").status_code == 409
    run_to_completion(client, project["id"])
    assert client.post(f"/api/projects/{project['id']}/retry").status_code == 409
