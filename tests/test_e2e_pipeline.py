import hashlib
import json
import time
import zipfile

from fastapi.testclient import TestClient

from ebook_factory.app import create_app
from scripts.run_server import build_arg_parser

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


def test_build_arg_parser_has_expected_defaults():
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.data_dir == "data"


def test_build_arg_parser_accepts_overrides():
    parser = build_arg_parser()
    args = parser.parse_args(["--host", "0.0.0.0", "--port", "9000", "--data-dir", "/tmp/x"])
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.data_dir == "/tmp/x"


def _wait_for_status(client, project_id, targets, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/projects/{project_id}").json()
        if last["status"] in targets:
            return last
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {targets}, last={last}")


def test_full_lead_magnet_pipeline_via_http_produces_valid_delivery(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        create = client.post(
            "/api/projects",
            json={
                "title": "E2E Lead Magnet",
                "topic": "Testowanie kompletnego pipeline'u",
                "mode": "lead-magnet",
                "audience": "testerzy oprogramowania",
                "brand": "Ebook Factory",
                "tone": "rzeczowy",
            },
        )
        assert create.status_code == 201
        project = create.json()
        assert len(project["stages"]) == 11
        assert project["status"] == "draft"

        start = client.post(f"/api/projects/{project['id']}/start")
        assert start.status_code == 202

        final = _wait_for_status(client, project["id"], {"completed", "failed"})
        assert final["status"] == "completed", final
        assert final["progress"] == 100

        download = client.get(f"/api/projects/{project['id']}/download")
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
        assert download.content[:2] == b"PK"

        zip_path = tmp_path / "downloaded.zip"
        zip_path.write_bytes(download.content)

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert REQUIRED_DELIVERY_FILES.issubset(names)

            assert zf.read("book.pdf").startswith(b"%PDF")
            assert zf.read("book.epub")[:2] == b"PK"

            manifest = json.loads(zf.read("manifest.json"))
            manifest_by_name = {e["name"]: e for e in manifest["files"]}
            assert (REQUIRED_DELIVERY_FILES - {"manifest.json"}).issubset(manifest_by_name)

            for name, entry in manifest_by_name.items():
                content = zf.read(name)
                assert hashlib.sha256(content).hexdigest() == entry["sha256"]
                assert len(content) == entry["bytes"]

        events = client.get(f"/api/projects/{project['id']}/events").json()
        assert len(events) >= 11
