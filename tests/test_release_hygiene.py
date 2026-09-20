from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_required_open_source_release_files_exist():
    required = [
        "LICENSE",
        ".env.example",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        ".github/workflows/ci.yml",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/feature_request.md",
        ".github/pull_request_template.md",
        "docs/screenshots/desktop-workspace.png",
        "docs/screenshots/tablet-workspace.png",
        "docs/screenshots/mobile-workspace.png",
    ]
    for path in required:
        assert (ROOT / path).is_file(), f"missing {path}"


def test_license_is_agpl_3_only():
    license_text = read("LICENSE")
    pyproject = read("pyproject.toml")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 19 November 2007" in license_text
    assert "AGPL-3.0-only" in pyproject
    assert "MIT" not in pyproject
    assert "Apache" not in pyproject


def test_readme_public_release_contract():
    readme = read("README.md")
    for fragment in (
        "AGPL-3.0-only",
        "```mermaid",
        "Quick start",
        "Codex CLI",
        "Claude Code",
        "Security and privacy",
        "Screenshots",
        "AI disclosure",
        "/api/providers",
        "PYTHONPATH=src",
    ):
        assert fragment in readme
    assert "third-party" in readme.lower()
    assert "subscription" in readme.lower()


def test_ci_uses_existing_venv_style_and_runs_quality_gates():
    ci = read(".github/workflows/ci.yml")
    for fragment in (
        "pytest",
        "node --check src/ebook_factory/static/app.js",
        "PYTHONPATH=src",
        "python -m pip install -e .[dev]",
    ):
        assert fragment in ci


def test_no_forbidden_runtime_artifacts_are_tracked():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    forbidden_parts = (
        ".venv/",
        "data/",
        "projects/",
        "factory.db",
        "delivery.zip",
    )
    tracked = result.stdout.splitlines()
    offenders = [
        path
        for path in tracked
        if path == ".env"
        or any(part in path or path.endswith(part.rstrip("/")) for part in forbidden_parts)
    ]
    assert offenders == []


def test_readme_documents_the_workspace_feature_set():
    readme = read("README.md")
    for endpoint in (
        "/api/stats",
        "/api/projects/{id}/artifacts",
        "/api/projects/{id}/metrics",
        "/api/projects/{id}/retry",
        "/api/projects/{id}/duplicate",
    ):
        assert endpoint in readme, f"README does not document {endpoint}"
    for section in (
        "Workflow: od pomysłu do paczki",
        "Workspace UI",
        "Co zawiera gotowa paczka",
        "Własna struktura rozdziałów",
        "Konfiguracja",
        "Troubleshooting",
    ):
        assert section in readme, f"README is missing the {section!r} section"


def test_readme_screenshots_all_exist():
    import re

    readme = read("README.md")
    referenced = re.findall(r"!\[[^\]]*\]\((docs/screenshots/[^)]+)\)", readme)
    assert len(referenced) >= 3
    for path in referenced:
        assert (ROOT / path).is_file(), f"README references a missing screenshot: {path}"


def test_env_example_documents_every_supported_variable():
    env_example = read(".env.example")
    for variable in (
        "EBOOK_FACTORY_AUTH_USER",
        "EBOOK_FACTORY_AUTH_PASSWORD",
        "EBOOK_FACTORY_CODEX_CLI",
        "EBOOK_FACTORY_CLAUDE_CODE",
        "EBOOK_FACTORY_DATA_DIR",
    ):
        assert variable in env_example, f".env.example does not mention {variable}"
