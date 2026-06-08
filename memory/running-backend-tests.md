---
name: running-backend-tests
description: How to run the Django backend test suite locally (sqlite override)
metadata:
  type: reference
---

The Django backend (`backend_django/`) targets Postgres, and some migrations use
Postgres-only SQL (e.g. `ADD COLUMN IF NOT EXISTS`) that SQLite rejects. To run tests
without the Docker Postgres, use `config/test_settings.py`, which switches to in-memory
SQLite and disables migrations (schema is built directly from model state via a
`MIGRATION_MODULES` shim). Data-migration seeds (roles, badges) therefore don't run
under tests — seed needed rows in `setUp`.

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests --settings=config.test_settings`
(a local `.venv` was created in `backend_django/`; it's gitignored).

`manage.py makemigrations` / `check` warn `could not translate host name "db"` — that's
just the consistency probe hitting the unreachable Docker DB host; harmless.
