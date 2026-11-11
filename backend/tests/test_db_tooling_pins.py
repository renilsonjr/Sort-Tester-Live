"""Pin the reviewed PostgreSQL tooling versions."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
REQ = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")


class DatabaseToolingPinTests(unittest.TestCase):
    def test_driver_and_migration_tool_pinned(self):
        self.assertIn("psycopg[binary]==3.3.8", REQ)
        self.assertIn("alembic==1.20.1", REQ)

    def test_no_posix_only_or_source_only_dependencies_added(self):
        # The two added lines must be wheel-installable on Linux and Windows.
        self.assertNotIn("psycopg[c]", REQ)  # source build would need libpq headers
