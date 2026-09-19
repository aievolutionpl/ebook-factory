# Open-Source Agent v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public AGPL Ebook Factory operated by Codex CLI or Claude Code with a polished production workspace.

**Architecture:** A provider protocol owns agent execution and a registry exposes availability. Projects persist the selected provider; pipeline stages assemble bounded prompts and invoke it without shell interpolation. The current deterministic provider remains the zero-cost default and delivery path.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, vanilla HTML/CSS/JS, pytest, subprocess, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-19-open-source-agent-v1.md`

## Global Constraints
- AGPL-3.0-only; no secrets or credentials.
- `demo` is default and backward compatible.
- Commands use argv lists and `shell=False`.
- Existing API/actions/uploads remain compatible.
- UI stays dependency-free and uses documented design tokens.
- Real-browser validation at 1440/1150/768/390/360.

---

### Task 1: Provider abstraction and safe CLI runners
**Files:** Create `src/ebook_factory/providers.py`; create `tests/test_providers.py`.
**Interfaces:** Produces `AgentRequest`, `AgentResult`, `AgentProvider`, `DemoProvider`, `CodexCLIProvider`, `ClaudeCodeProvider`, `get_provider`, `provider_statuses`.
- [ ] Write failing tests using fake CLI executables for availability, argv invocation, cwd, stdout/stderr, timeout, nonzero exit and output containment.
- [ ] Run `pytest tests/test_providers.py -q` and record expected RED.
- [ ] Implement the smallest safe provider layer with no `shell=True`.
- [ ] Run provider tests and full suite GREEN.
- [ ] Commit `feat: add local agent provider adapters`.

### Task 2: Persist provider and integrate pipeline/API
**Files:** Modify `models.py`, `repository.py`, `api.py`, `pipeline.py`, `stages.py`; modify corresponding tests.
**Interfaces:** Consumes provider registry; produces project `provider` and `GET /api/providers`.
- [ ] Add failing migration/model/API/pipeline tests proving old DB compatibility, validated provider names, status endpoint and unavailable-provider preflight.
- [ ] Run focused tests and record RED.
- [ ] Add additive SQLite migration, API field, prompt builder and provider invocation while preserving demo output packaging.
- [ ] Run focused and full tests GREEN.
- [ ] Commit `feat: integrate agents into ebook pipeline`.

### Task 3: Premium calm Codex UI polish and provider controls
**Files:** Modify static HTML/CSS/JS, `DESIGN.md`, `tests/test_static_ui.py`.
**Interfaces:** Consumes `/api/providers`; preserves current selectors and actions.
- [ ] Add failing static/UI contract tests for provider selector, completion summary, translated stages, tablet drawer and non-obscuring contextual controls.
- [ ] Record RED.
- [ ] Implement provider selection/status and approved visual polish using tokens only.
- [ ] Run static tests, node syntax, Impeccable and full suite GREEN.
- [ ] Render and inspect empty/populated states at all required widths; fix blockers.
- [ ] Commit `feat: polish agent workspace experience`.

### Task 4: Open-source distribution and documentation
**Files:** Create `LICENSE`, `.env.example`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/workflows/ci.yml`, issue and PR templates; rewrite `README.md`; add docs/screenshots.
**Interfaces:** Documents exact tested install and provider commands.
- [ ] Add failing repository hygiene tests/assertions for required release files and forbidden tracked artifacts.
- [ ] Record RED.
- [ ] Add AGPL-3.0-only materials, workflow, polished README, architecture diagram and real screenshots.
- [ ] Validate every documented command in a clean local setup where practical.
- [ ] Run full suite GREEN and secret scan.
- [ ] Commit `docs: prepare public open-source release`.

### Task 5: Final review, deploy and publish
**Files:** No planned product changes except review fixes.
**Interfaces:** Produces verified main branch and public GitHub repository URL.
- [ ] Run broad spec and code-quality review; fix Critical/Important findings via one reviewed fix wave.
- [ ] Run fresh full pytest, `hermes verify`, node check, Impeccable and browser E2E.
- [ ] Merge fast-forward to main.
- [ ] Restart local production and public tunnel; verify public root/health and new provider UI.
- [ ] Create or connect public `aievolutionpl/ebook-factory`, set description/topics, push main, verify remote files/actions/license.
- [ ] Record release state in vault and report the public URL.
