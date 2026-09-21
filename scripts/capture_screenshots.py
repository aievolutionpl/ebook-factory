#!/usr/bin/env python3
"""Regenerate the README screenshots from a live workspace.

The script boots the real app on a throwaway data directory, produces one demo
ebook end to end and captures every viewport the design contract covers, so the
images in ``docs/screenshots`` always match the shipped UI.

Usage::

    pip install playwright
    python scripts/capture_screenshots.py

Chromium must be available to Playwright (``playwright install chromium`` or a
preinstalled browser pointed at by ``CHROMIUM_PATH``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ebook_factory.app import create_app  # noqa: E402

DEFAULT_OUTPUT = ROOT / "docs" / "screenshots"
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 950},
    "tablet": {"width": 900, "height": 1000},
    "mobile": {"width": 390, "height": 844},
}
DEMO_PROJECT = {
    "title": "Automatyzacja marketingu",
    "topic": "Automatyzacja marketingu dla małych firm",
    "mode": "guide",
    "language": "pl",
    "audience": "właściciele małych firm",
    "brand": "Ebook Factory Demo",
    "tone": "rzeczowy",
    "provider": "demo",
    "writing_style": "practical",
    "humanize_level": "standard",
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"server did not answer on {url}")


def _post(url: str, payload: dict | None = None) -> dict:
    import json

    data = json.dumps(payload).encode() if payload is not None else b""
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode()
    return json.loads(body) if body else {}


def _get(url: str) -> dict:
    import json

    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def _serve(data_dir: Path, port: int) -> threading.Thread:
    import uvicorn

    app = create_app(data_dir)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread


def _seed_project(base: str) -> str:
    project = _post(f"{base}/api/projects", DEMO_PROJECT)
    _post(f"{base}/api/projects/{project['id']}/start")
    deadline = time.time() + 300
    while time.time() < deadline:
        current = _get(f"{base}/api/projects/{project['id']}")
        if current["status"] in ("completed", "failed", "cancelled"):
            return project["id"]
        time.sleep(1)
    raise RuntimeError("demo project did not finish in time")


def _launch_browser(playwright):
    executable = os.environ.get("CHROMIUM_PATH")
    if executable:
        return playwright.chromium.launch(executable_path=executable)
    return playwright.chromium.launch()


def capture(base: str, output: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)

        page = browser.new_page(viewport=VIEWPORTS["desktop"])
        page.goto(base, wait_until="networkidle")
        page.click(".project-card")
        page.wait_for_selector("#project-detail:not([hidden])")
        page.wait_for_timeout(1200)
        written.append(_shot(page, output / "desktop-workspace.png"))

        page.click("#tab-files")
        page.wait_for_timeout(900)
        written.append(_shot(page, output / "desktop-files.png"))

        page.click("#tab-quality")
        page.wait_for_timeout(900)
        # The panel sits below the metrics, so scroll it into frame before the
        # shot; otherwise the screenshot only shows the header again.
        page.eval_on_selector(
            "#panel-quality", "node => node.scrollIntoView({block: 'start'})"
        )
        page.wait_for_timeout(400)
        written.append(_shot(page, output / "desktop-quality.png"))

        page.click("#tab-workflow")
        page.click("#theme-toggle")
        page.wait_for_timeout(500)
        written.append(_shot(page, output / "desktop-light.png"))
        page.click("#theme-toggle")
        page.wait_for_timeout(300)

        page.click("#new-project-button")
        page.fill("#field-title", "Sprzedaż przez newsletter")
        page.fill("#field-topic", "Budowa listy i sprzedaż w mailingu")
        page.wait_for_timeout(400)
        written.append(_shot(page, output / "desktop-wizard.png"))
        page.click("#cancel-new-project")
        page.close()

        tablet = browser.new_page(viewport=VIEWPORTS["tablet"])
        tablet.goto(base, wait_until="networkidle")
        tablet.click(".project-card")
        tablet.wait_for_selector("#project-detail:not([hidden])")
        tablet.wait_for_timeout(1200)
        written.append(_shot(tablet, output / "tablet-workspace.png"))
        tablet.close()

        mobile = browser.new_page(viewport=VIEWPORTS["mobile"], is_mobile=True, has_touch=True)
        mobile.goto(base, wait_until="networkidle")
        mobile.click(".project-card")
        mobile.wait_for_selector("#project-detail:not([hidden])")
        mobile.wait_for_timeout(1200)
        written.append(_shot(mobile, output / "mobile-workspace.png"))
        mobile.close()

        browser.close()
    return written


def _shot(page, path: Path) -> Path:
    page.screenshot(path=str(path))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Screenshot directory")
    parser.add_argument("--keep-data", action="store_true", help="Keep the temporary data directory")
    args = parser.parse_args(argv)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("playwright is required: pip install playwright", file=sys.stderr)
        return 2

    data_dir = Path(tempfile.mkdtemp(prefix="ebook-factory-shots-"))
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    try:
        _serve(data_dir, port)
        _wait_for(f"{base}/health")
        _seed_project(base)
        written = capture(base, Path(args.output))
    finally:
        if not args.keep_data:
            shutil.rmtree(data_dir, ignore_errors=True)

    for path in written:
        print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
