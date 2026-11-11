"""Migration pipeline contract: clean migrate, restart persistence, rollback."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class ToolingProbeMigrationTests(unittest.TestCase):
    conninfo = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.admin = settings.admin_url()  # same server, maintenance db
            migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
            cls.conninfo = settings.test_database_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def test_clean_migrate_creates_probe_table(self):
        migrate.upgrade_to_head(self.conninfo)
        self.assertEqual(migrate.current_revision(self.conninfo), "0001")
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))

    def test_rerun_is_idempotent(self):
        migrate.upgrade_to_head(self.conninfo)
        self.assertEqual(migrate.current_revision(self.conninfo), "0001")
        migrate.upgrade_to_head(self.conninfo)
        self.assertEqual(migrate.current_revision(self.conninfo), "0001")
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))

    def test_downgrade_removes_probe_table(self):
        migrate.upgrade_to_head(self.conninfo)
        self.assertEqual(migrate.current_revision(self.conninfo), "0001")
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))
        migrate.downgrade_all(self.conninfo)
        self.assertIsNone(migrate.current_revision(self.conninfo))
        self.assertFalse(migrate.table_exists(self.conninfo, "tooling_probe"))


class MalformedEnvironmentTests(unittest.TestCase):
    def test_migration_suite_skips_malformed_nonempty_url(self):
        env = os.environ.copy()
        env[settings.ENV_VAR] = "not-a-url"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "backend.tests.test_db_migration.ToolingProbeMigrationTests",
                "-v",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("skipped=1", output)
        self.assertIn(settings.ENV_VAR, output)
        self.assertNotIn("Traceback", output)
