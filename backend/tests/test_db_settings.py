"""Connection-settings contract for the tooling foundation."""
import os
import unittest
from unittest import mock


from backend.db import settings


class TestDatabaseUrlTests(unittest.TestCase):
    def test_missing_variable_raises_naming_it(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(settings.ENV_VAR, None)
            with self.assertRaises(settings.DatabaseConfigError) as ctx:
                settings.test_database_url()
        self.assertIn(settings.ENV_VAR, str(ctx.exception))

    def test_non_postgres_scheme_rejected(self):
        with mock.patch.dict(
            os.environ, {settings.ENV_VAR: "mysql://u:p@localhost/db"}
        ):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.test_database_url()

    def test_scratch_database_name_enforced(self):
        with mock.patch.dict(
            os.environ,
            {
                settings.ENV_VAR: "postgresql://u:p@localhost:5432/sort_tester_unittest_scratch"
            },
        ):
            self.assertEqual(
                settings.test_database_url(),
                "postgresql://u:p@localhost:5432/sort_tester_unittest_scratch",
            )

    def test_foreign_database_name_rejected(self):
        with mock.patch.dict(
            os.environ, {settings.ENV_VAR: "postgresql://u:p@localhost:5432/sort_tester_dev"}
        ):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.test_database_url()
