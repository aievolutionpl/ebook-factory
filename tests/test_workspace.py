"""Tests for the on-disk artifact view: listing, path safety, metrics."""

import pytest

from ebook_factory import workspace


@pytest.fixture
def project_dir(tmp_path):
    root = tmp_path / "projects" / "demo"
    for sub in ("chapters", "builds", "delivery", "images", "sources", "qa"):
        (root / sub).mkdir(parents=True)
    (root / "chapters" / "chapter-01.md").write_text(
        "# Wprowadzenie\n\nJeden dwa trzy cztery piec.\n", encoding="utf-8"
    )
    (root / "chapters" / "chapter-02.md").write_text(
        "# Rozwiniecie\n\nSzesc siedem osiem.\n", encoding="utf-8"
    )
    (root / "builds" / "book.pdf").write_bytes(b"%PDF-1.4 fake")
    (root / "delivery" / "delivery.zip").write_bytes(b"PK\x03\x04")
    (root / "images" / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "sources" / "notes.md").write_text("zrodlo", encoding="utf-8")
    (root / "qa" / "engine.json").write_text('{"pdf_engine": "typst", "print_grade": true}', encoding="utf-8")
    return root


def test_artifacts_are_grouped_by_category_in_display_order(project_dir):
    groups = workspace.list_artifact_groups(project_dir)
    categories = [group.category for group in groups]
    assert categories.index("delivery") < categories.index("chapters")
    assert set(categories) == {"delivery", "builds", "images", "chapters", "sources", "qa"}
    delivery = next(g for g in groups if g.category == "delivery")
    assert [f.name for f in delivery.files] == ["delivery.zip"]
    assert delivery.files[0].kind == "archive"


def test_artifact_classification_marks_only_text_and_images_previewable(project_dir):
    groups = {g.category: g for g in workspace.list_artifact_groups(project_dir)}
    pdf = groups["builds"].files[0]
    assert pdf.kind == "pdf" and pdf.previewable is False
    png = groups["images"].files[0]
    assert png.kind == "image" and png.previewable is True
    markdown = groups["chapters"].files[0]
    assert markdown.kind == "text" and markdown.previewable is True


def test_resolve_artifact_returns_file_inside_workspace(project_dir):
    resolved = workspace.resolve_artifact(project_dir, "chapters/chapter-01.md")
    assert resolved.name == "chapter-01.md"


@pytest.mark.parametrize(
    "path",
    [
        "../../secrets.txt",
        "chapters/../../escape.md",
        "/etc/passwd",
        "..",
        "chapters\\..\\..\\escape.md",
    ],
)
def test_resolve_artifact_rejects_traversal_and_absolute_paths(project_dir, path):
    with pytest.raises(workspace.ArtifactAccessDenied):
        workspace.resolve_artifact(project_dir, path)


def test_resolve_artifact_rejects_symlink_escaping_workspace(project_dir, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = project_dir / "chapters" / "link.md"
    link.symlink_to(outside)
    with pytest.raises(workspace.ArtifactAccessDenied):
        workspace.resolve_artifact(project_dir, "chapters/link.md")


def test_listing_skips_symlinks(project_dir, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (project_dir / "chapters" / "link.md").symlink_to(outside)
    names = [f.name for g in workspace.list_artifact_groups(project_dir) for f in g.files]
    assert "link.md" not in names


def test_resolve_artifact_raises_not_found_for_missing_file(project_dir):
    with pytest.raises(workspace.ArtifactNotFound):
        workspace.resolve_artifact(project_dir, "chapters/chapter-99.md")


def test_read_preview_is_bounded_and_reports_truncation(project_dir):
    long_path = project_dir / "chapters" / "chapter-03.md"
    long_path.write_text("a" * 5000, encoding="utf-8")
    text, truncated = workspace.read_preview(long_path, max_chars=100)
    assert len(text) == 100
    assert truncated is True

    short, short_truncated = workspace.read_preview(
        project_dir / "sources" / "notes.md", max_chars=100
    )
    assert short == "zrodlo"
    assert short_truncated is False


def test_compute_metrics_counts_words_pages_and_engine(project_dir):
    metrics = workspace.compute_metrics(project_dir)
    assert metrics["chapters"] == 2
    assert metrics["words"] == 10
    assert metrics["estimated_pages"] == 1
    assert metrics["reading_minutes"] == 1
    assert metrics["pdf_engine"] == "typst"
    assert metrics["print_grade"] is True
    assert metrics["artifacts"] >= 7
    assert [row["title"] for row in metrics["chapter_breakdown"]] == [
        "Wprowadzenie",
        "Rozwiniecie",
    ]


def test_compute_metrics_on_empty_workspace(tmp_path):
    metrics = workspace.compute_metrics(tmp_path / "missing")
    assert metrics["chapters"] == 0
    assert metrics["words"] == 0
    assert metrics["estimated_pages"] == 0


def test_count_words_handles_polish_diacritics_and_numbers():
    assert workspace.count_words("Zażółć gęślą jaźń 2026") == 4


def test_delete_project_workspace_removes_directory(project_dir):
    assert workspace.delete_project_workspace(project_dir) is True
    assert not project_dir.exists()
    assert workspace.delete_project_workspace(project_dir) is False
