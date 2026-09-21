#!/usr/bin/env python3
"""Black-box HTTP smoke test against a running Ebook Factory server.

Usage: python scripts/smoke_e2e.py http://127.0.0.1:8765
Prints PASS and exits 0 on success; prints FAIL: <reason> and exits 1 otherwise.
Uses only the stdlib so it can run against a deployed server without the dev venv.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO

REQUIRED_DELIVERY_FILES = {
    "book.pdf",
    "book.epub",
    "cover.png",
    "offer.md",
    "landing.html",
    "posts.md",
    "ads.md",
    "qa-report.md",
    "humanize-report.md",
    "manifest.json",
}

POLL_TIMEOUT_SECONDS = 180
POLL_INTERVAL_SECONDS = 2


class SmokeTestError(Exception):
    pass


def _request(base_url: str, method: str, path: str, payload: dict | None = None) -> dict:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SmokeTestError(f"{method} {path} failed with {exc.code}: {detail}") from exc


def _download(base_url: str, path: str) -> bytes:
    url = base_url.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=60) as resp:
        if resp.status != 200:
            raise SmokeTestError(f"GET {path} returned {resp.status}")
        return resp.read()


def check_health(base_url: str) -> None:
    result = _request(base_url, "GET", "/health")
    if result.get("status") != "ok":
        raise SmokeTestError(f"/health returned unexpected body: {result}")


def create_project(base_url: str) -> str:
    payload = {
        "title": "Smoke Test Lead Magnet",
        "topic": "Weryfikacja pipeline'u produkcyjnego",
        "mode": "lead-magnet",
        "audience": "operatorzy Ebook Factory",
        "brand": "Ebook Factory Demo",
        "tone": "rzeczowy",
    }
    project = _request(base_url, "POST", "/api/projects", payload)
    # The server is the source of truth for how many stages a build has, so
    # adding a stage does not turn this smoke test red on its own.
    expected_stages = _request(base_url, "GET", "/api/version").get("stages", 0)
    if len(project.get("stages", [])) != expected_stages:
        raise SmokeTestError(
            f"expected {expected_stages} stages, got {len(project.get('stages', []))}"
        )
    return project["id"]


def start_project(base_url: str, project_id: str) -> None:
    _request(base_url, "POST", f"/api/projects/{project_id}/start")


def poll_until_terminal(base_url: str, project_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last: dict = {}
    while time.time() < deadline:
        last = _request(base_url, "GET", f"/api/projects/{project_id}")
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(POLL_INTERVAL_SECONDS)
    raise SmokeTestError(
        f"timed out after {POLL_TIMEOUT_SECONDS}s waiting for completion, last state: {last}"
    )


def validate_delivery_zip(zip_bytes: bytes) -> None:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        missing = REQUIRED_DELIVERY_FILES - names
        if missing:
            raise SmokeTestError(f"delivery ZIP is missing required files: {sorted(missing)}")

        if not zf.read("book.pdf").startswith(b"%PDF"):
            raise SmokeTestError("book.pdf does not start with %PDF")
        if zf.read("book.epub")[:2] != b"PK":
            raise SmokeTestError("book.epub is not a valid ZIP container")

        manifest = json.loads(zf.read("manifest.json"))
        manifest_by_name = {e["name"]: e for e in manifest["files"]}
        for name, entry in manifest_by_name.items():
            content = zf.read(name)
            digest = hashlib.sha256(content).hexdigest()
            if digest != entry["sha256"]:
                raise SmokeTestError(f"sha256 mismatch for {name}: manifest={entry['sha256']} actual={digest}")
            if len(content) != entry["bytes"]:
                raise SmokeTestError(f"size mismatch for {name}")


def run(base_url: str) -> None:
    print(f"[1/6] checking /health on {base_url}")
    check_health(base_url)

    print("[2/6] creating lead-magnet project")
    project_id = create_project(base_url)
    print(f"      project id: {project_id}")

    print("[3/6] starting pipeline")
    start_project(base_url, project_id)

    print(f"[4/6] polling until completion (timeout {POLL_TIMEOUT_SECONDS}s)")
    final = poll_until_terminal(base_url, project_id)
    if final["status"] != "completed":
        raise SmokeTestError(f"project did not complete: status={final['status']} error={final.get('error')}")
    print(f"      completed with progress={final['progress']}")

    print("[5/6] downloading delivery ZIP")
    zip_bytes = _download(base_url, f"/api/projects/{project_id}/download")

    print("[6/6] validating delivery ZIP contents")
    validate_delivery_zip(zip_bytes)

    print("PASS")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python scripts/smoke_e2e.py <base_url>", file=sys.stderr)
        return 2
    base_url = argv[0]
    try:
        run(base_url)
    except SmokeTestError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # unexpected errors still produce a non-zero exit
        print(f"FAIL: unexpected error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
