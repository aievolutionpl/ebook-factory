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


def test_index_has_codex_workspace_shell_regions():
    html = read("index.html")
    for fragment in (
        'class="workspace-shell"',
        'class="project-rail"',
        'class="workspace-panel"',
        'class="inspector-panel"',
        'id="command-composer"',
    ):
        assert fragment in html
    assert re.search(r'<nav[^>]+class=["\'][^"\']*project-rail[^"\']*["\'][^>]+aria-label=["\']Projekty', html)
    assert re.search(r'<aside[^>]+class=["\'][^"\']*inspector-panel[^"\']*["\']', html)


def test_project_rail_has_search_status_filters_and_new_action():
    html = read("index.html")
    assert 'id="project-search"' in html
    assert 'type="search"' in html
    for status in ("all", "draft", "running", "paused", "completed", "failed", "cancelled"):
        assert f'data-status-filter="{status}"' in html
    assert 'id="new-project-button"' in html


def test_workspace_has_header_progress_contextual_action_and_tabs():
    html = read("index.html")
    for fragment in (
        'id="workspace-primary-action"',
        'id="workspace-progress-label"',
        'role="tablist"',
        'id="tab-workflow"',
        'id="tab-files"',
        'id="tab-activity"',
        'id="panel-workflow"',
        'id="panel-files"',
        'id="panel-activity"',
    ):
        assert fragment in html


def test_inspector_exposes_outputs_sources_activity_and_download():
    html = read("index.html")
    for fragment in (
        'id="inspector-outputs"',
        'id="inspector-sources"',
        'id="inspector-activity"',
        'id="inspector-download-link"',
        'id="inspector-sheet-toggle"',
    ):
        assert fragment in html


def test_command_composer_maps_only_existing_project_actions():
    html = read("index.html")
    app_js = read("app.js")
    for command in ("start", "pause", "resume", "cancel", "download"):
        assert f'data-command="{command}"' in html
    forbidden = set(re.findall(r'data-command=["\']([^"\']+)["\']', html)) - {
        "start",
        "pause",
        "resume",
        "cancel",
        "download",
    }
    assert not forbidden
    assert "runComposerCommand" in app_js


def test_command_palette_is_accessible_keyboard_navigable_and_restores_focus():
    html = read("index.html")
    app_js = read("app.js")
    assert 'id="command-palette"' in html
    assert 'role="dialog"' in html
    assert 'id="command-palette-list"' in html
    assert 'aria-activedescendant' in html
    for fragment in ("metaKey", "ctrlKey", "Escape", "ArrowDown", "ArrowUp", "restorePaletteFocus"):
        assert fragment in app_js


def test_new_project_dialog_is_three_step_accessible_wizard_preserving_fields():
    html = read("index.html")
    for step in ("wizard-step-goal", "wizard-step-brand", "wizard-step-sources", "wizard-step-review"):
        assert f'id="{step}"' in html
    for fragment in (
        'id="wizard-back"',
        'id="wizard-next"',
        'id="wizard-review"',
        'aria-live="polite"',
        'data-preset="lead-magnet"',
        'data-preset="guide"',
        'data-preset="premium"',
    ):
        assert fragment in html
    for field_id in (
        "field-title",
        "field-topic",
        "field-mode",
        "field-language",
        "field-audience",
        "field-brand",
        "field-tone",
        "field-source-materials",
        "field-source-files",
    ):
        assert f'id="{field_id}"' in html


def test_app_js_preserves_create_then_upload_api_behavior():
    app_js = read("app.js")
    create_index = app_js.find("apiFetch('/api/projects'")
    upload_index = app_js.find("uploadSourceFiles(project.id")
    assert create_index != -1 and upload_index != -1
    assert create_index < upload_index
    assert "formData.delete('source_files')" in app_js
    assert "uploadData.append('files', file)" in app_js


def test_styles_define_required_responsive_workspace_layouts():
    css = read("styles.css")
    assert re.search(r"grid-template-columns:\s*var\(--rail-width\)\s+minmax\(0,\s*1fr\)\s+var\(--inspector-width\)", css)
    assert "@media (min-width: 768px)" in css
    assert "@media (min-width: 1150px)" in css
    assert "@media (max-width: 767px)" in css
    assert "overflow-x: hidden" in css
    assert "min-width: 0" in css


def test_styles_include_skeleton_toast_bottom_sheet_and_sticky_mobile_action():
    css = read("styles.css")
    for selector in (
        ".skeleton",
        ".toast-region",
        ".inspector-sheet",
        ".mobile-sticky-action",
        ".project-drawer",
    ):
        assert selector in css


def test_styles_avoid_gradients_and_keep_rule_values_tokenized():
    css = read("styles.css")
    assert "gradient(" not in css
    css_without_tokens = re.sub(r":root\s*{.*?}", "", css, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}", css_without_tokens)
    assert "letter-spacing: -" not in css


def test_mobile_project_rail_is_drawer_not_inline_split_view():
    html = read("index.html")
    css = read("styles.css")
    app_js = read("app.js")
    assert 'id="project-drawer-backdrop"' in html
    assert 'aria-controls="sidebar-nav"' in html
    assert "openProjectDrawer" in app_js
    assert "closeProjectDrawer" in app_js
    assert "project-drawer-backdrop" in app_js
    assert "event.key === 'Escape'" in app_js
    mobile_block = re.search(r"@media \(max-width: 767px\)\s*{(?P<body>.*?)\n}", css, re.S)
    assert mobile_block, "expected mobile breakpoint"
    assert re.search(r"\.project-rail\s*{[^}]*position:\s*fixed", css, re.S)
    assert re.search(r"\.project-rail\s*{[^}]*transform:\s*translateX\(-100%\)", css, re.S)
    assert ".project-rail.is-open" in css
    assert "closeProjectDrawer();" in app_js


def test_mobile_empty_and_selected_states_hide_duplicate_actions():
    css = read("styles.css")
    app_js = read("app.js")
    assert "updateMobileChrome" in app_js
    assert "el.mobilePrimaryAction.hidden = !hasProject" in app_js
    assert "el.inspectorPanel.hidden = !hasProject" in app_js
    assert re.search(r"@media \(max-width: 767px\).*?\.command-composer\s*{\s*display:\s*none", css, re.S)
    assert re.search(r"\.inspector-panel\s*{[^}]*transform:\s*translateY\(100%\)", css, re.S)


def test_mobile_header_and_toasts_do_not_cover_actions():
    css = read("styles.css")
    app_js = read("app.js")
    assert re.search(r"@media \(max-width: 767px\).*?\.header-context\s*{\s*display:\s*none", css, re.S)
    assert re.search(r"@media \(max-width: 767px\).*?#palette-open-button\s*{\s*display:\s*none", css, re.S)
    assert re.search(r"@media \(max-width: 767px\).*?\.app-header\s*{[^}]*flex-wrap:\s*nowrap", css, re.S)
    assert re.search(r"\.toast-region\s*{[^}]*top:\s*max\(var\(--space-3\), env\(safe-area-inset-top\)\)", css, re.S)
    assert re.search(r"@media \(max-width: 767px\).*?\.toast-region\s*{[^}]*right:\s*max\(var\(--space-3\), env\(safe-area-inset-right\)\)", css, re.S)
    assert "window.setTimeout" in app_js and "toast.remove()" in app_js


def test_visible_shell_copy_is_consistently_polish():
    html = read("index.html")
    app_js = read("app.js")
    for text in (
        "Projekty",
        "Szukaj",
        "Wszystkie",
        "Szkic",
        "W trakcie",
        "Wstrzymane",
        "Gotowe",
        "Błąd",
        "Anulowane",
        "Proces",
        "Pliki",
        "Aktywność",
        "Inspektor",
        "Źródła",
        "Wyniki",
        "Ostatnia aktywność",
        "+ Nowy ebook",
    ):
        assert text in html or text in app_js
    for hybrid in ("+ New / Nowy ebook", ">Projects<", ">Search<", ">Workflow<", ">Files<", ">Activity<", ">Inspector<"):
        assert hybrid not in html
    for label in ("Uruchom projekt", "Wstrzymaj po bieżącym etapie", "Wznów projekt", "Anuluj projekt", "Pobierz paczkę ZIP"):
        assert label in app_js


def test_provider_controls_and_status_are_exposed():
    html = read("index.html")
    app_js = read("app.js")
    for fragment in (
        'id="field-provider"',
        'name="provider"',
        'id="provider-guidance"',
        'id="detail-provider"',
        'id="inspector-provider-status"',
    ):
        assert fragment in html
    assert "/api/providers" in app_js
    assert "loadProviders" in app_js
    assert "PROVIDER_LABELS" in app_js
    assert "renderProviderStatus" in app_js


def test_stage_ids_are_translated_for_users():
    app_js = read("app.js")
    assert "STAGE_LABELS" in app_js
    for label in (
        "Strategia",
        "Research",
        "Architektura",
        "Pisanie",
        "Redakcja",
        "Weryfikacja faktów",
        "Projekt okładki",
        "Publikacja",
        "Marketing",
        "Kontrola jakości",
        "Paczka końcowa",
    ):
        assert label in app_js
    assert "stage.name : 'Oczekuje na start'" not in app_js
    assert "escapeHtml(stage.name)" not in app_js


def test_completion_summary_and_single_dominant_action_surface():
    html = read("index.html")
    css = read("styles.css")
    app_js = read("app.js")
    assert 'id="completion-summary"' in html
    assert "renderCompletionSummary" in app_js
    assert "Projekt gotowy do pobrania" in app_js
    assert not re.search(r"\.command-composer\s*{[^}]*position:\s*fixed", css, re.S)
    assert re.search(r"\.workspace-panel\s*{[^}]*overflow-y:\s*auto", css, re.S)


def test_tablet_uses_project_drawer_and_calm_dimensions():
    css = read("styles.css")
    assert "--rail-width: 280px" in css
    assert "--inspector-width: 300px" in css
    assert "@media (min-width: 768px) and (max-width: 1149px)" in css
    assert re.search(
        r"@media \(min-width: 768px\) and \(max-width: 1149px\).*?\.project-rail\s*{[^}]*position:\s*fixed",
        css,
        re.S,
    )
    assert re.search(
        r"@media \(min-width: 768px\) and \(max-width: 1149px\).*?\.workspace-shell\s*{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)",
        css,
        re.S,
    )


# ------------------------------------------------------------------ v2 UI


def test_file_browser_uses_the_real_artifact_api_not_a_hardcoded_list():
    app_js = read("app.js")
    assert "/artifacts" in app_js
    assert "loadArtifacts" in app_js
    assert "artifacts/preview" in app_js
    assert "artifacts/raw" in app_js
    # The old placeholder rows must be gone.
    assert "Zapisane przez istniejące API uploadu" not in app_js
    assert "'marketing pack'" not in app_js


def test_files_panel_exposes_filter_and_refresh_controls():
    html = read("index.html")
    for fragment in ('id="file-filter"', 'id="files-refresh"', 'id="workspace-files"'):
        assert fragment in html


def test_artifact_preview_dialog_is_accessible_and_offers_download():
    html = read("index.html")
    app_js = read("app.js")
    for fragment in (
        'id="artifact-preview"',
        'id="artifact-preview-title"',
        'id="artifact-preview-body"',
        'id="artifact-download-link"',
        'id="artifact-preview-close"',
    ):
        assert fragment in html
    assert "openArtifactPreview" in app_js
    assert "escapeHtml(payload.text)" in app_js


def test_metrics_grid_is_rendered_from_the_metrics_endpoint():
    html = read("index.html")
    app_js = read("app.js")
    assert 'id="workspace-metrics"' in html
    assert "/metrics" in app_js
    assert "renderMetrics" in app_js
    for label in ("Rozdziały", "Słowa", "Strony (szac.)", "Czas czytania"):
        assert label in app_js


def test_settings_panel_patches_the_project():
    html = read("index.html")
    app_js = read("app.js")
    assert 'id="panel-settings"' in html
    assert 'id="settings-form"' in html
    assert "'PATCH'" in app_js
    assert "saveSettings" in app_js
    for field_id in (
        "settings-title",
        "settings-topic",
        "settings-mode",
        "settings-audience",
        "settings-brand",
        "settings-tone",
        "settings-language",
        "settings-chapters",
    ):
        assert f'id="{field_id}"' in html


def test_project_menu_exposes_retry_duplicate_and_delete():
    html = read("index.html")
    app_js = read("app.js")
    for action in ("retry", "duplicate", "delete", "edit"):
        assert f'data-action="{action}"' in html
    assert "duplicateCurrentProject" in app_js
    assert "deleteCurrentProject" in app_js
    assert "'/retry'" in app_js or "/retry" in app_js
    assert "'DELETE'" in app_js


def test_destructive_delete_is_confirmed_before_it_runs():
    html = read("index.html")
    app_js = read("app.js")
    assert 'id="confirm-dialog"' in html
    assert "askConfirmation" in app_js
    delete_index = app_js.find("function deleteCurrentProject")
    confirm_index = app_js.find("askConfirmation", delete_index)
    fetch_index = app_js.find("method: 'DELETE'", delete_index)
    assert delete_index != -1 and confirm_index != -1 and fetch_index != -1
    assert confirm_index < fetch_index


def test_theme_toggle_persists_the_choice_and_css_defines_a_light_palette():
    html = read("index.html")
    app_js = read("app.js")
    css = read("styles.css")
    assert 'id="theme-toggle"' in html
    assert "localStorage" in app_js
    assert "applyTheme" in app_js
    assert ':root[data-theme="light"]' in css
    assert "--color-bg: hsl(" in css


def test_chapter_structure_can_be_supplied_in_the_wizard():
    html = read("index.html")
    app_js = read("app.js")
    assert 'id="field-chapter-titles"' in html
    assert "parseChapterTitles" in app_js
    assert "payload.chapter_titles" in app_js


def test_stage_rows_expose_progress_detail_without_leaking_raw_stage_ids():
    app_js = read("app.js")
    assert "STAGE_HINTS" in app_js
    assert "formatDuration" in app_js
    assert "stage-artifacts" in app_js
    assert "escapeHtml(stage.name)" not in app_js


def test_polling_backs_off_when_a_project_is_not_running():
    app_js = read("app.js")
    assert "POLL_INTERVAL_ACTIVE" in app_js
    assert "POLL_INTERVAL_IDLE" in app_js
    assert "after_id=" in app_js


def test_rail_shows_portfolio_stats_and_sorting():
    html = read("index.html")
    app_js = read("app.js")
    for fragment in ('id="stat-running"', 'id="stat-completed"', 'id="stat-failed"', 'id="project-sort"'):
        assert fragment in html
    assert "/api/stats" in app_js
    assert "sortProjects" in app_js


def test_new_v2_copy_is_polish():
    html = read("index.html")
    app_js = read("app.js")
    for text in (
        "Ustawienia",
        "Podgląd",
        "Pobierz",
        "Duplikuj projekt",
        "Usuń projekt",
        "Ponów",
        "Struktura rozdziałów",
    ):
        assert text in html or text in app_js
