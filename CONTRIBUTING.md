# Contributing

Thanks for improving Ebook Factory.

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
PYTHONPATH=src .venv/bin/pytest -q
node --check src/ebook_factory/static/app.js
```

Use strict TDD for behavioral changes: add or update a failing test first,
capture the RED command, implement the smallest working change, then capture
GREEN.

## Rules

- Keep the project AGPL-3.0-only.
- Do not commit secrets, `.env`, `data/`, `projects/`, generated ebooks,
  SQLite databases, virtualenvs, or provider credentials.
- Use argv lists for subprocesses. Never use shell interpolation for provider
  execution.
- Preserve the deterministic `demo` provider path.
