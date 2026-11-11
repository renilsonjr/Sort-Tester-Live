"""Connection-settings contract for the tooling foundation."""
import os
import unittest
from unittest import mock


from psycopg.conninfo import conninfo_to_dict

from backend.db import settings


class TestDatabaseUrlTests(unittest.TestCase):
    def assert_url_rejected_before_connect(self, url):
        with mock.patch.dict(os.environ, {settings.ENV_VAR: url}):
            with mock.patch("backend.db.migrate.psycopg.connect") as connect:
                with self.assertRaises(settings.DatabaseConfigError) as ctx:
                    settings.test_database_url()
        connect.assert_not_called()
        self.assertIn(settings.ENV_VAR, str(ctx.exception))
        return str(ctx.exception)

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

    def test_conflicting_dbname_override_rejected_before_connect(self):
        self.assert_url_rejected_before_connect(
            "postgresql://localhost/sort_tester_unittest_scratch"
            "?dbname=sort_tester_dev"
        )

    def test_host_only_url_rejected_before_connect(self):
        self.assert_url_rejected_before_connect(
            "postgresql://sort_tester_unittest_scratch"
        )

    def test_missing_or_empty_effective_database_rejected(self):
        for url in (
            "postgresql://localhost/",
            "postgresql://localhost/sort_tester_unittest_scratch?dbname=",
        ):
            with self.subTest(url=url):
                self.assert_url_rejected_before_connect(url)

    def test_malformed_url_and_conninfo_errors_are_normalized(self):
        for url in (
            "not-a-url",
            "postgresql://[not-an-ipv6]/sort_tester_unittest_scratch",
            "postgresql://localhost/sort_tester_unittest_scratch?not-valid",
        ):
            with self.subTest(url=url):
                self.assert_url_rejected_before_connect(url)

    def test_rejection_does_not_echo_credentials(self):
        message = self.assert_url_rejected_before_connect(
            "postgresql://user:super-secret@[broken/sort_tester_unittest_scratch"
        )
        self.assertNotIn("super-secret", message)

    def test_admin_url_resolves_to_maintenance_database(self):
        with mock.patch.dict(
            os.environ,
            {
                settings.ENV_VAR: "postgresql://localhost/sort_tester_unittest_scratch"
                "?dbname=sort_tester_unittest_scratch&connect_timeout=1"
            },
        ):
            admin = conninfo_to_dict(settings.admin_url())
        self.assertEqual(admin["dbname"], settings.MAINTENANCE_DATABASE)
        self.assertEqual(admin["connect_timeout"], "1")

    def test_environment_guard_is_presence_only(self):
        with mock.patch.dict(os.environ, {settings.ENV_VAR: "not-a-url"}):
            self.assertTrue(settings.environment_has_test_url())
