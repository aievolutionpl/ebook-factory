## Summary

## Tests

- [ ] `PYTHONPATH=src .venv/bin/pytest -q`
- [ ] `node --check src/ebook_factory/static/app.js`

## Checklist

- [ ] No secrets, credentials, generated ebooks, databases, or virtualenv files.
- [ ] Provider subprocesses use argv lists, not shell interpolation.
- [ ] Demo provider remains deterministic and backward compatible.
