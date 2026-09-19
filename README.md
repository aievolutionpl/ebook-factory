# Ebook Factory

Private single-user panel that runs a full demo ebook production pipeline —
strategy, research, outline, draft, edit, fact-check, cover design, PDF/EPUB
publishing, marketing assets, QA and delivery packaging — and produces a
ready-to-review sales package. No autopublishing, no payments, no external
paid APIs: every artifact is generated deterministically so the full
lifecycle can be tested end to end for free.

Spec: `docs/superpowers/specs/2026-09-19-ebook-factory-design.md`
Plan: `docs/superpowers/plans/2026-09-19-ebook-factory-mvp.md`

## Requirements

- Python 3.11+
- Optional: `typst` on `PATH` (or at `~/.local/bin/typst`) for higher-fidelity
  PDF output. Without it, the pipeline falls back to a pure-stdlib PDF writer
  and records which engine ran in the QA report.
- Optional: `pdftotext` (poppler-utils) on `PATH` for extracting text from
  uploaded PDF source files. Without it, PDFs are still stored but their
  text is not appended to `source_materials` (extraction is reported as
  `unavailable`).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Running the server

```bash
.venv/bin/python scripts/run_server.py --host 127.0.0.1 --port 8765 --data-dir data
```

Then open `http://127.0.0.1:8765` for the dashboard, or `GET /health` to
check liveness. `--data-dir` controls where the SQLite database
(`factory.db`) and per-project artifact folders (`projects/<slug>/`) are
written; it is created if missing and survives process restarts.

## Testing

Run the full suite with the project's virtualenv:

```bash
.venv/bin/pytest -q
```

### Smoke test

`scripts/smoke_e2e.py` is a stdlib-only black-box HTTP client that creates a
lead-magnet project against a **running** server, starts it, polls to
completion, downloads the delivery ZIP and validates every required file and
its SHA-256 manifest entry. It is independent of the dev virtualenv so it can
also be run against a deployed instance:

```bash
.venv/bin/python scripts/run_server.py --host 127.0.0.1 --port 8765 --data-dir /tmp/ef-smoke &
.venv/bin/python scripts/smoke_e2e.py http://127.0.0.1:8765
```

Prints `PASS` and exits `0` on success; prints `FAIL: <reason>` and exits
non-zero on any missing/invalid artifact or timeout.

## API overview

All endpoints are served from the same FastAPI app as the static dashboard.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/api/projects` | Create a project (`title`, `topic`, `mode`, ...) |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/{id}` | Project detail with stages |
| POST | `/api/projects/{id}/start` | Start/resume the pipeline in the background |
| POST | `/api/projects/{id}/pause` | Request pause after the current stage |
| POST | `/api/projects/{id}/resume` | Resume a paused project |
| POST | `/api/projects/{id}/cancel` | Cancel |
| GET | `/api/projects/{id}/events` | Event log |
| GET | `/api/projects/{id}/download` | Delivery ZIP |
| POST | `/api/projects/{id}/sources` | Upload source-material files (multipart) |

Modes: `lead-magnet`, `guide`, `premium`. The pipeline runs each project on
its own background thread, persists state after every stage so it survives a
process restart, and retries a failing stage up to three times before
marking the project `failed`.

### Source-material uploads

`POST /api/projects/{id}/sources` accepts a `multipart/form-data` request
with one or more `files` parts. Uploads are bounded and sanitized:

- Only `.txt`, `.md`, `.pdf` extensions are accepted (case-insensitive);
  anything else is rejected with `422`.
- Each file must be non-empty and at most 5 MiB; a project may hold at most
  5 source files total (checked cumulatively across requests).
- Filenames are sanitized to a flat, safe basename before storage — path
  separators and traversal segments (e.g. `../../etc/passwd.txt`) are
  stripped so files can only ever land under `projects/<slug>/sources/`.
- On success, each file is described in the response as
  `{filename, stored_path, size_bytes, extraction_status, extracted_chars}`.
  `extraction_status` is `extracted`, `empty`, or `unavailable` (PDF text
  extraction requires `pdftotext`; without it the file is still stored).
- Extracted text is appended to the project's `source_materials` (used by
  the `strategy` and `research` stages) without exceeding the existing
  50,000-character cap — text beyond the cap is truncated, never rejected.

The dashboard's "Nowy ebook" dialog includes a `.txt,.md,.pdf` multi-file
picker; selected files are uploaded right after the project is created (and
before the pipeline is started), with a clear inline error if the upload is
rejected.

## Deployment

`deploy/start-production.sh` runs the server as a supervised background
process with logs under `deploy/logs/`. `deploy/cloudflared-tunnel.sh`
exposes it over HTTPS via a Cloudflare Quick Tunnel (using an installed
`cloudflared` if present, otherwise downloading the official binary into
`~/.local/bin`). Both scripts run under `set -euo pipefail`, bind only to the
host/port/data-dir passed as arguments, and never embed secrets or tokens.

```bash
deploy/start-production.sh --host 127.0.0.1 --port 8765 --data-dir data
deploy/cloudflared-tunnel.sh --port 8765
```

The tunnel script prints the public `https://*.trycloudflare.com` URL once
`cloudflared` reports it in its logs.

## Project layout

```text
src/ebook_factory/       FastAPI app, pipeline, stages, artifacts, static dashboard
scripts/run_server.py    One-command launcher
scripts/smoke_e2e.py     Stdlib-only black-box smoke test
deploy/                  Production launch + tunnel scripts
tests/                   pytest suite (unit, API, static UI, E2E)
```
