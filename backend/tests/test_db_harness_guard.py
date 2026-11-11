"""Guard rails around the scratch-database harness."""
import unittest


from backend.db import migrate, settings


class RecreateGuardTests(unittest.TestCase):
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
