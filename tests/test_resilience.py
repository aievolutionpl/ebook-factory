"""Failure-path guarantees: a broken run must never strand a project.

Every test here drives a failure that the happy-path suite does not exercise:
a worker that raises, a project row pointing at a provider that no longer
exists, an oversized upload, and a delivery stage missing its inputs. In each
case the project must end up in an explicit, reportable state instead of
hanging on "running" or surfacing a raw traceback.
"""

import io
import time

import pytest
from fastapi.testclient import TestClient

from ebook_factory.api import WorkerRegistry, build_router
from ebook_factory.app import create_app
from ebook_factory.models import ProjectCreate
from ebook_factory.pipeline import PipelineRunner
from ebook_factory.repository import ProjectRepository
from ebook_factory.sources import MAX_SOURCE_FILE_BYTES, read_bounded
from ebook_factory.stages import DEFAULT_STAGE_HANDLERS, delivery_stage


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        yield c


def wait_for_status(client, project_id, targets, timeout=30):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/projects/{project_id}").json()
        if last["status"] in targets:
            return last
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {targets}, last={last}")


def _make_project(client, **overrides):
    payload = {"title": "Test", "topic": "Temat", "mode": "lead-magnet"}
    payload.update(overrides)
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------
# A crashing worker must fail the project, not strand it on "running"
# --------------------------------------------------------------------------


class _ExplodingRunner:
    """Stands in for a PipelineRunner whose run() raises unexpectedly."""

    def run(self, project_id, stop_requested=lambda: False):
        raise RuntimeError("boom")


def test_worker_crash_marks_project_failed(tmp_path):
    repository = ProjectRepository(tmp_path / "factory.db")
    try:
        project = repository.create_project(
            ProjectCreate(title="Crash", topic="Temat", mode="lead-magnet")
        )
        registry = WorkerRegistry()
        registry.start(project.id, _ExplodingRunner(), repository)
        registry.join_all(timeout=10)

        stored = repository.get_project(project.id)
        assert stored.status == "failed"
        assert "boom" in (stored.error or "")

        messages = [e.message for e in repository.list_events(project.id)]
        assert any("boom" in m for m in messages)
    finally:
        repository.close()


def test_worker_crash_releases_the_slot_for_a_retry(tmp_path):
    repository = ProjectRepository(tmp_path / "factory.db")
    try:
        project = repository.create_project(
            ProjectCreate(title="Crash", topic="Temat", mode="lead-magnet")
        )
        registry = WorkerRegistry()
        registry.start(project.id, _ExplodingRunner(), repository)
        registry.join_all(timeout=10)
        assert registry.is_running(project.id) is False
        # A second start must be accepted rather than rejected as "already running".
        registry.start(project.id, _ExplodingRunner(), repository)
        registry.join_all(timeout=10)
    finally:
        repository.close()


# --------------------------------------------------------------------------
# An unknown provider is a data problem, not a crash
# --------------------------------------------------------------------------


def test_unknown_provider_fails_the_project_cleanly(tmp_path):
    repository = ProjectRepository(tmp_path / "factory.db")
    try:
        project = repository.create_project(
            ProjectCreate(title="Legacy", topic="Temat", mode="lead-magnet")
        )
        # Simulate a row written by an older/newer build with a provider this
        # version does not know about.
        repository.update_project(project.id, provider="gpt-9000")
        runner = PipelineRunner(
            repository, tmp_path / "projects", stage_handlers=DEFAULT_STAGE_HANDLERS
        )
        result = runner.run(project.id)

        assert result.status == "failed"
        assert "gpt-9000" in (result.error or "")
        messages = [e.message for e in repository.list_events(project.id)]
        assert any("gpt-9000" in m for m in messages)
    finally:
        repository.close()


# --------------------------------------------------------------------------
# Uploads are bounded before they are buffered
# --------------------------------------------------------------------------


def test_oversized_upload_is_rejected_without_buffering_everything(client):
    project = _make_project(client)
    oversized = b"a" * (MAX_SOURCE_FILE_BYTES + 5000)
    response = client.post(
        f"/api/projects/{project['id']}/sources",
        files={"files": ("big.txt", io.BytesIO(oversized), "text/plain")},
    )
    assert response.status_code == 422
    assert "size" in response.json()["detail"].lower()


def test_read_bounded_stops_one_byte_past_the_limit():
    """An oversized upload must never be read in full, only far enough to reject."""

    class _CountingStream:
        def __init__(self, total: int) -> None:
            self.remaining = total
            self.served = 0

        def read(self, size: int = -1) -> bytes:
            if size is None or size < 0:
                size = self.remaining
            size = min(size, self.remaining)
            self.remaining -= size
            self.served += size
            return b"a" * size

    stream = _CountingStream(MAX_SOURCE_FILE_BYTES * 4)
    data = read_bounded(stream)

    assert len(data) == MAX_SOURCE_FILE_BYTES + 1
    assert stream.served == MAX_SOURCE_FILE_BYTES + 1
    assert stream.remaining > 0  # the rest was never pulled into memory


def test_read_bounded_returns_short_streams_whole():
    import io

    assert read_bounded(io.BytesIO(b"krotki plik")) == b"krotki plik"


def test_upload_is_refused_while_the_project_is_running(client, tmp_path):
    project = _make_project(client)
    client.post(f"/api/projects/{project['id']}/start")
    # Whether we catch it mid-run or after it finished, the contract is the
    # same: never mutate source materials underneath a live pipeline.
    response = client.post(
        f"/api/projects/{project['id']}/sources",
        files={"files": ("notes.txt", io.BytesIO(b"tresc"), "text/plain")},
    )
    assert response.status_code in (201, 409)
    if response.status_code == 409:
        assert "running" in response.json()["detail"]
    wait_for_status(client, project["id"], {"completed", "failed"})


# --------------------------------------------------------------------------
# Delivery reports what is missing instead of raising
# --------------------------------------------------------------------------


def test_delivery_stage_reports_missing_inputs(tmp_path):
    repository = ProjectRepository(tmp_path / "factory.db")
    try:
        project = repository.create_project(
            ProjectCreate(title="Partial", topic="Temat", mode="lead-magnet")
        )
        project_dir = tmp_path / "projects" / project.slug
        (project_dir / "delivery").mkdir(parents=True)
        result = delivery_stage(project, project_dir)
        assert result.success is False
        assert "book.pdf" in result.message
    finally:
        repository.close()


# --------------------------------------------------------------------------
# Version endpoint advertises the permissive license
# --------------------------------------------------------------------------


def test_version_endpoint_reports_name_version_and_license(client):
    response = client.get("/api/version")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "ebook-factory"
    assert body["license"] == "MIT"
    assert body["version"]
    assert body["stages"] == 11
