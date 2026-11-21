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


class VerifiedTlsTests(unittest.TestCase):
    """A DSN that reaches the database over a network must verify TLS.

    Audit M-4: nothing in code required ``sslmode``, and libpq's own
    default is ``prefer`` -- which silently falls back to an unencrypted
    connection if the server offers one. A misconfiguration therefore
    downgraded the connection with no error anywhere (audit L1).
    """

    def _app_url(self, url):
        with mock.patch.dict(os.environ, {settings.APP_ENV_VAR: url}):
            return settings.app_database_url()

    def _assert_app_url_rejected(self, url):
        with self.assertRaises(settings.DatabaseConfigError) as ctx:
            self._app_url(url)
        return str(ctx.exception)

    def test_a_remote_dsn_without_sslmode_is_refused(self):
        # libpq would read this as sslmode=prefer and accept plaintext
        message = self._assert_app_url_rejected(
            "postgresql://u:p@db.example.com:5432/sort_tester_app"
        )
        self.assertIn("sslmode", message)
        self.assertIn("verify-full", message)

    def test_the_downgrading_sslmodes_are_refused(self):
        for mode in ("disable", "allow", "prefer"):
            with self.subTest(mode=mode):
                self._assert_app_url_rejected(
                    f"postgresql://u:p@db.example.com/sort_tester_app?sslmode={mode}"
                )

    def test_the_verifying_sslmodes_are_accepted(self):
        for mode in ("require", "verify-ca", "verify-full"):
            with self.subTest(mode=mode):
                url = f"postgresql://u:p@db.example.com/sort_tester_app?sslmode={mode}"
                self.assertEqual(self._app_url(url), url)

    def test_a_refusal_does_not_echo_the_password(self):
        message = self._assert_app_url_rejected(
            "postgresql://u:super-secret@db.example.com/sort_tester_app"
        )
        self.assertNotIn("super-secret", message)

    def test_a_loopback_database_may_still_run_without_tls(self):
        # the development database on the same machine: there is no network
        # for the connection to be read on, and requiring a certificate
        # there would mean no one could run the app locally at all
        for host in ("localhost", "127.0.0.1", "[::1]"):
            with self.subTest(host=host):
                url = f"postgresql://{host}:5432/sort_tester_walkthrough"
                self.assertEqual(self._app_url(url), url)

    def test_the_test_dsn_follows_the_same_rule(self):
        remote = (
            "postgresql://u:p@db.example.com/sort_tester_unittest_scratch"
        )
        with mock.patch.dict(os.environ, {settings.ENV_VAR: remote}):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.test_database_url()

        secured = f"{remote}?sslmode=verify-full"
        with mock.patch.dict(os.environ, {settings.ENV_VAR: secured}):
            self.assertEqual(settings.test_database_url(), secured)


class DbAuthModeTests(unittest.TestCase):
    def test_defaults_to_password_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(settings.DB_AUTH_ENV_VAR, None)
            self.assertEqual(settings.db_auth_mode(), settings.PASSWORD_MODE)

    def test_blank_is_password(self):
        with mock.patch.dict(os.environ, {settings.DB_AUTH_ENV_VAR: "   "}):
            self.assertEqual(settings.db_auth_mode(), settings.PASSWORD_MODE)

    def test_managed_identity_is_accepted(self):
        with mock.patch.dict(os.environ, {settings.DB_AUTH_ENV_VAR: "managed_identity"}):
            self.assertEqual(settings.db_auth_mode(), settings.MANAGED_IDENTITY_MODE)

    def test_unknown_mode_raises(self):
        with mock.patch.dict(os.environ, {settings.DB_AUTH_ENV_VAR: "kerberos"}):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.db_auth_mode()
