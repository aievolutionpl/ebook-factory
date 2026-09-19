import re
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "ebook_factory" / "static"


def read(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_static_files_exist():
    for name in ("index.html", "styles.css", "app.js", "favicon.svg"):
        assert (STATIC_DIR / name).is_file(), f"missing {name}"


def test_index_has_viewport_meta():
    html = read("index.html")
    assert re.search(
        r'<meta[^>]+name=["\']viewport["\'][^>]+content=["\'][^"\']*width=device-width',
        html,
    )


def test_index_has_required_landmarks():
    html = read("index.html")
    assert re.search(r"<header[\s>]", html)
    assert re.search(r'<nav[^>]*aria-label=', html)
    assert re.search(r"<main[\s>]", html)
    assert re.search(r"<footer[\s>]", html)


def test_index_has_ai_disclosure_bar():
    html = read("index.html")
    assert "ai-disclosure" in html
    lowered = html.lower()
    assert "ai" in lowered and ("wygenerowan" in lowered or "generowan" in lowered)


def test_index_has_new_project_primary_action():
    html = read("index.html")
    assert "Nowy ebook" in html


def test_index_has_labeled_form_controls():
    html = read("index.html")
    label_fors = set(re.findall(r'<label[^>]*for=["\']([\w-]+)["\']', html))
    input_ids = set(re.findall(r'<(?:input|select|textarea)[^>]*\sid=["\']([\w-]+)["\']', html))
    assert input_ids, "expected at least one form control with an id"
    assert input_ids.issubset(label_fors), f"unlabeled controls: {input_ids - label_fors}"


def test_index_has_no_cdn_script_or_style_dependencies():
    html = read("index.html")
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
    link_hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html)
    for src in script_srcs + link_hrefs:
        assert not src.startswith("http"), f"external dependency found: {src}"


def test_index_only_references_local_assets():
    html = read("index.html")
    assert 'src="app.js"' in html or "src='app.js'" in html or "src=\"/app.js\"" in html
    assert "styles.css" in html
    assert "favicon.svg" in html


def test_index_references_known_api_routes():
    app_js = read("app.js")
    for route in ("/api/projects", "/health"):
        assert route in app_js


def test_app_js_covers_pipeline_controls():
    app_js = read("app.js")
    for fragment in ("/start", "/pause", "/resume", "/cancel", "/download", "/events"):
        assert fragment in app_js


def test_styles_define_focus_visible_ring():
    css = read("styles.css")
    assert ":focus-visible" in css


def test_styles_respect_reduced_motion():
    css = read("styles.css")
    assert "prefers-reduced-motion" in css


def test_styles_have_no_external_font_or_cdn_imports():
    css = read("styles.css")
    assert "@import" not in css
    assert "fonts.googleapis.com" not in css
    assert "http://" not in css and "https://" not in css


def test_styles_use_design_tokens_for_color():
    css = read("styles.css")
    assert "--color-bg" in css
    assert "--color-accent" in css
    assert "--space-4" in css


def test_styles_define_breakpoints_for_required_viewports():
    css = read("styles.css")
    assert "768px" in css
    assert "1150px" in css


def test_index_has_source_materials_textarea():
    html = read("index.html")
    assert re.search(r'<textarea[^>]*id=["\']field-source-materials["\']', html)
    assert re.search(r'<textarea[^>]*maxlength=["\']50000["\']', html)


def test_index_has_bounded_source_file_upload_input():
    html = read("index.html")
    match = re.search(r'<input[^>]*id=["\']field-source-files["\'][^>]*>', html)
    assert match, "expected a file input for source materials uploads"
    tag = match.group(0)
    assert 'type="file"' in tag
    assert 'multiple' in tag
    accept_match = re.search(r'accept=["\']([^"\']+)["\']', tag)
    assert accept_match, "file input must restrict accepted extensions"
    accepted = {ext.strip() for ext in accept_match.group(1).split(",")}
    assert accepted == {".txt", ".md", ".pdf"}


def test_favicon_is_valid_svg():
    svg = read("favicon.svg")
    assert svg.strip().startswith("<svg") or "<?xml" in svg[:100]
