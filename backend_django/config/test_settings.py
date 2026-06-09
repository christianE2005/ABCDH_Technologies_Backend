"""Test settings: run the suite against an in-memory SQLite DB so tests don't
need the Docker Postgres. Inherits everything else from the real settings."""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


class _DisableMigrations:
    """Build the test schema directly from model state.

    The real migration history contains Postgres-only SQL (e.g. ADD COLUMN IF NOT
    EXISTS) that SQLite can't run. Skipping migrations lets the suite run on SQLite;
    tests that need seeded rows (badges, roles) create them in setUp.
    """

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

# Speed up password hashing in tests (not that we use Django auth much here).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
