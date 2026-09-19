# Ebook Factory MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować, przetestować i wdrożyć prywatny panel, który uruchamia pełny demonstracyjny pipeline ebooka i generuje gotową paczkę sprzedażową.

**Architecture:** Jeden serwis FastAPI serwuje API oraz statyczny panel HTML/CSS/JS. SQLite przechowuje stan, a osobny worker w procesie wykonuje idempotentne etapy i zapisuje artefakty do izolowanego katalogu projektu. Adapter demo tworzy realne pliki PDF/EPUB/HTML/marketing bez płatnych API; interfejs adaptera pozwala później wpiąć Hermes/LLM.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLite, pytest, stdlib EPUB/ZIP/SVG, Typst jeśli dostępny, vanilla HTML/CSS/JS, Playwright/browser-use, Cloudflare Quick Tunnel.

**Spec:** `docs/superpowers/specs/2026-09-19-ebook-factory-design.md`

## Global Constraints

- Trzy tryby: `lead-magnet`, `guide`, `premium`.
- Wyjście: PDF, EPUB, cover PNG/SVG, oferta, landing, posty, reklamy, QA, manifest, ZIP.
- Brak autopublikacji i płatności.
- Stan musi przetrwać restart procesu.
- Maksymalnie trzy próby etapu; trzecia porażka ustawia `failed`.
- Panel mobile/tablet-first, WCAG AA, viewporty 390/768/1150/1440.
- Każda nowa funkcja powstaje TDD: test ma najpierw poprawnie zawieść.
- Zero sekretów w repo i paczkach.

---

### Task 1: Model domeny, repozytorium SQLite i walidacja

**Files:**
- Create: `pyproject.toml`
- Create: `src/ebook_factory/__init__.py`
- Create: `src/ebook_factory/models.py`
- Create: `src/ebook_factory/repository.py`
- Create: `tests/test_repository.py`

**Interfaces:**
- Produces: `ProjectCreate`, `Project`, `Stage`, `ProjectRepository.create_project()`, `.get_project()`, `.list_projects()`, `.update_project()`, `.upsert_stage()`, `.append_event()`.

- [ ] **Step 1: Write failing tests** for slug sanitization, all three modes, persistence after reopening SQLite, ordered stages and invalid mode rejection.

```python
def test_project_survives_repository_reopen(tmp_path):
    repo = ProjectRepository(tmp_path / "factory.db")
    created = repo.create_project(ProjectCreate(title="AI dla firm", topic="AI", mode="guide"))
    repo.close()
    reopened = ProjectRepository(tmp_path / "factory.db")
    assert reopened.get_project(created.id).title == "AI dla firm"
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_repository.py -q`
Expected: collection/import failure because production modules do not exist.

- [ ] **Step 3: Implement minimal models and SQLite repository** using parameterized SQL, UTC ISO timestamps, JSON columns for artifacts and explicit mode validation.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_repository.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests/test_repository.py
git commit -m "feat: add persistent ebook project model"
```

### Task 2: Idempotent pipeline and real delivery artifacts

**Files:**
- Create: `src/ebook_factory/artifacts.py`
- Create: `src/ebook_factory/pipeline.py`
- Create: `src/ebook_factory/stages.py`
- Create: `tests/test_pipeline.py`
- Create: `tests/test_artifacts.py`

**Interfaces:**
- Consumes: repository interfaces from Task 1.
- Produces: `PipelineRunner.run(project_id)`, `StageResult`, `build_epub()`, `build_pdf()`, `build_delivery_zip()`.

- [ ] **Step 1: Write failing artifact tests** asserting EPUB begins with uncompressed `mimetype`, contains `META-INF/container.xml`, `content.opf`, `nav.xhtml`; PDF starts `%PDF`; manifest contains SHA-256 for every delivery file; ZIP contains the required filenames.

- [ ] **Step 2: Write failing pipeline tests** asserting ordered execution, completed-stage skipping, pause after current stage, resume, max-three-attempt failure and final `completed` state.

- [ ] **Step 3: Run RED**

Run: `pytest tests/test_artifacts.py tests/test_pipeline.py -q`
Expected: missing modules/functions.

- [ ] **Step 4: Implement deterministic stages** that create strategy, research with source placeholders clearly marked as demo, outline, mode-sized sample chapters, edited manuscript, fact-check report, SVG cover, PDF, EPUB, offer, landing, posts, ads, QA, manifest and ZIP.

- [ ] **Step 5: Implement PDF path**: use Typst when `~/.local/bin/typst` exists; otherwise generate a minimal valid PDF with stdlib. Never silently claim print-grade output on fallback; record engine in QA.

- [ ] **Step 6: Run GREEN**

Run: `pytest tests/test_artifacts.py tests/test_pipeline.py -q`
Expected: all tests pass and temp delivery package validates.

- [ ] **Step 7: Commit**

```bash
git add src/ebook_factory tests/test_pipeline.py tests/test_artifacts.py
git commit -m "feat: add resumable ebook production pipeline"
```

### Task 3: FastAPI API and background execution

**Files:**
- Create: `src/ebook_factory/api.py`
- Create: `src/ebook_factory/app.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: repository and `PipelineRunner`.
- Produces: `create_app(data_dir: Path) -> FastAPI`; endpoints defined in the spec.

- [ ] **Step 1: Write failing API tests** with `TestClient`: health, create/list/detail, start, pause, resume, cancel, events, download; invalid mode 422; unknown project 404; safe filename headers.

```python
def test_create_and_fetch_project(client):
    r = client.post('/api/projects', json={"title":"AI dla firm","topic":"AI","mode":"guide"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.get(f'/api/projects/{pid}').json()["title"] == "AI dla firm"
```

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_api.py -q`
Expected: missing app module.

- [ ] **Step 3: Implement API** with per-project background tasks, clean JSON responses, path confinement and static mount.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_api.py -q`
Expected: all API tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ebook_factory/api.py src/ebook_factory/app.py tests/test_api.py
git commit -m "feat: expose ebook factory API"
```

### Task 4: Responsive production dashboard

**Files:**
- Create: `DESIGN.md`
- Create: `src/ebook_factory/static/index.html`
- Create: `src/ebook_factory/static/styles.css`
- Create: `src/ebook_factory/static/app.js`
- Create: `src/ebook_factory/static/favicon.svg`
- Create: `tests/test_static_ui.py`

**Interfaces:**
- Consumes: API routes from Task 3.
- Produces: accessible dashboard, create form, project detail/status, controls, artifacts/download.

- [ ] **Step 1: Record design contract**: audience Chris/JARVIS operators; product AI production tool; personality precise/editorial/calm; density medium-high; primary action “Nowy ebook”; emotion control and confidence. Use Swiss/International dominant style with restrained editorial support. Define every color, spacing, radius, shadow and duration as a token.

- [ ] **Step 2: Write failing static tests** for required landmark/labels, viewport meta, focus styles, reduced motion, AI disclosure bar, no CDN dependencies and API route references.

- [ ] **Step 3: Run RED**

Run: `pytest tests/test_static_ui.py -q`
Expected: missing static assets.

- [ ] **Step 4: Build the dashboard** with desktop sidebar, tablet/mobile bottom navigation, project cards, progress timeline, empty/loading/error states, large tap targets and polling for status updates.

- [ ] **Step 5: Run GREEN**

Run: `pytest tests/test_static_ui.py -q`
Expected: all static requirements pass.

- [ ] **Step 6: Run anti-slop gate**

Run: `npx --yes impeccable detect --json src/ebook_factory/static > /tmp/ebook-impeccable.json`
Expected: inspect findings; zero blockers before commit.

- [ ] **Step 7: Commit**

```bash
git add DESIGN.md src/ebook_factory/static tests/test_static_ui.py
git commit -m "feat: add responsive ebook production dashboard"
```

### Task 5: Local integration, packaging and full E2E

**Files:**
- Create: `scripts/run_server.py`
- Create: `scripts/smoke_e2e.py`
- Create: `README.md`
- Create: `.gitignore`
- Create: `tests/test_e2e_pipeline.py`

**Interfaces:**
- Consumes: complete app.
- Produces: one-command server, automated browser/API smoke workflow and documented operation.

- [ ] **Step 1: Write failing E2E test** that creates a lead magnet through HTTP, starts it, polls to completion, downloads ZIP and validates every required file.

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_e2e_pipeline.py -q`
Expected: run script or integrated lifecycle missing.

- [ ] **Step 3: Implement launcher and smoke script** with bounded polling, meaningful timeout and non-zero exit on any missing artifact.

- [ ] **Step 4: Run full suite**

Run: `pytest -q`
Expected: zero failures.

- [ ] **Step 5: Start server and run smoke**

Run: `python scripts/run_server.py --host 127.0.0.1 --port 8765` and then `python scripts/smoke_e2e.py http://127.0.0.1:8765`
Expected: `PASS`, completed project, valid ZIP.

- [ ] **Step 6: Browser E2E** at 390, 768, 1150 and 1440 px: create project, start, observe progress, open detail, download; assert no overflow and zero console errors.

- [ ] **Step 7: Commit**

```bash
git add scripts README.md .gitignore tests/test_e2e_pipeline.py
git commit -m "test: verify ebook factory end to end"
```

### Task 6: Server deployment and live verification

**Files:**
- Create: `deploy/start-production.sh`
- Create: `deploy/cloudflared-tunnel.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 5 server.
- Produces: supervised local backend plus externally reachable HTTPS tunnel URL.

- [ ] **Step 1: Add script tests** ensuring strict shell flags, bound host/port, data directory and no embedded secrets.

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_deploy_scripts.py -q`
Expected: deploy scripts missing.

- [ ] **Step 3: Implement scripts**; prefer installed `cloudflared`, otherwise download/run verified binary in user space. Keep app and tunnel as tracked background processes with logs.

- [ ] **Step 4: Run GREEN and full verification**

Run: `pytest -q && python scripts/smoke_e2e.py http://127.0.0.1:8765`
Expected: zero test failures and smoke PASS.

- [ ] **Step 5: Launch tunnel and capture public URL** from logs.

- [ ] **Step 6: Verify live**: `GET /health`, root HTML, create/start/poll/download via live HTTPS, then real-browser E2E at 390 and 1440 px.

- [ ] **Step 7: Commit deployment files**

```bash
git add deploy README.md tests/test_deploy_scripts.py
git commit -m "ops: deploy ebook factory through secure tunnel"
```

## Plan self-review
- Spec coverage: model, pipeline, API, UI, resilience, artifacts, QA and live deployment each map to Tasks 1–6.
- Type consistency: `ProjectRepository`, `PipelineRunner` and `create_app(data_dir)` are the only cross-task interfaces.
- Scope: publishing, payments, SaaS accounts, KDP and audiobook remain excluded.
- Placeholder scan: no TBD/TODO/“similar to” instructions.
