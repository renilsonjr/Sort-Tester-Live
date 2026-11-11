"""Migration pipeline contract: clean migrate, restart persistence, rollback."""
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
        cls.admin = settings.admin_url()  # same server, connects to the default db
        migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
        cls.conninfo = settings.test_database_url()

    def test_clean_migrate_creates_probe_table(self):
        migrate.upgrade_to_head(self.conninfo)
        self.assertIsNotNone(migrate.current_revision(self.conninfo))
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))

    def test_rerun_is_idempotent(self):
        migrate.upgrade_to_head(self.conninfo)  # second call, same head
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))

    def test_downgrade_removes_probe_table(self):
        migrate.downgrade_all(self.conninfo)
        self.assertIsNone(migrate.current_revision(self.conninfo))
        self.assertFalse(migrate.table_exists(self.conninfo, "tooling_probe"))
