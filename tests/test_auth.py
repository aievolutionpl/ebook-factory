import base64

import pytest
from fastapi.testclient import TestClient

from ebook_factory.app import create_app


def _basic_header(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def protected_client(tmp_path):
    app = create_app(tmp_path, auth_credentials=("admin", "s3cret-pass"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def open_client(tmp_path):
    app = create_app(tmp_path, auth_credentials=None)
    with TestClient(app) as c:
        yield c


def test_health_is_public_even_when_credentials_configured(protected_client):
    r = protected_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_requires_auth_when_credentials_configured(protected_client):
    r = protected_client.get("/api/projects")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_api_rejects_wrong_credentials(protected_client):
    r = protected_client.get("/api/projects", headers=_basic_header("admin", "wrong"))
    assert r.status_code == 401


def test_api_accepts_correct_credentials(protected_client):
    r = protected_client.get("/api/projects", headers=_basic_header("admin", "s3cret-pass"))
    assert r.status_code == 200


def test_static_ui_requires_auth_when_credentials_configured(protected_client):
    r = protected_client.get("/")
    assert r.status_code == 401


def test_static_ui_accepts_correct_credentials(protected_client):
    r = protected_client.get("/", headers=_basic_header("admin", "s3cret-pass"))
    assert r.status_code == 200


def test_download_endpoint_requires_auth_when_credentials_configured(protected_client):
    r = protected_client.get("/api/projects/does-not-exist/download")
    assert r.status_code == 401


def test_project_create_requires_auth_when_credentials_configured(protected_client):
    r = protected_client.post(
        "/api/projects", json={"title": "X", "topic": "Y", "mode": "guide"}
    )
    assert r.status_code == 401


def test_without_configured_credentials_api_stays_reachable(open_client):
    r = open_client.get("/api/projects")
    assert r.status_code == 200


def test_env_credentials_are_picked_up_when_not_passed_explicitly(tmp_path, monkeypatch):
    monkeypatch.setenv("EBOOK_FACTORY_AUTH_USER", "envuser")
    monkeypatch.setenv("EBOOK_FACTORY_AUTH_PASSWORD", "envpass")
    app = create_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/projects").status_code == 401
        assert (
            client.get("/api/projects", headers=_basic_header("envuser", "envpass")).status_code
            == 200
        )
