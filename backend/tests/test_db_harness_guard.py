"""Guard rails around the scratch-database harness."""
import unittest
from unittest import mock


from backend.db import migrate, settings


class RecreateGuardTests(unittest.TestCase):
    def assert_admin_rejected_before_connect(self, conninfo):
        with mock.patch("backend.db.migrate.psycopg.connect") as connect:
            with self.assertRaises(settings.DatabaseConfigError):
                migrate.recreate_scratch_database(
                    conninfo, settings.SCRATCH_DB_NAME
                )
        connect.assert_not_called()

    def test_recreate_refuses_non_scratch_database(self):
        with self.assertRaises(settings.DatabaseConfigError):
            migrate.recreate_scratch_database(
                "postgresql://u:p@localhost:5432/sort_tester_dev",
                "sort_tester_dev",
            )

    def test_recreate_refuses_blank_name(self):
        with self.assertRaises(settings.DatabaseConfigError):
            migrate.recreate_scratch_database(
                "postgresql://u:p@localhost:5432/sort_tester_unittest_scratch", ""
            )

    def test_recreate_refuses_non_maintenance_effective_database(self):
        self.assert_admin_rejected_before_connect(
            "postgresql://u:p@localhost:5432/postgres"
            "?dbname=sort_tester_unittest_scratch"
        )

    def test_recreate_refuses_missing_or_empty_effective_database(self):
        for conninfo in (
            "postgresql://localhost/",
            "postgresql://localhost/postgres?dbname=",
        ):
            with self.subTest(conninfo=conninfo):
                self.assert_admin_rejected_before_connect(conninfo)

    def test_recreate_normalizes_malformed_conninfo_before_connect(self):
        self.assert_admin_rejected_before_connect(
            "postgresql://localhost/postgres?not-valid"
        )
