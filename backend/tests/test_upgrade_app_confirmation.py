"""What `--confirm` has to name, and what never reaches a log
(audit L7, L8).

Both of these are about a migration command run by a person, from a
terminal, against a database they believe they know.

L7: the confirmation took the database name alone. Staging and production
call their database the same thing, so the typed word that was supposed to
prove "I know where this is pointing" proved only "I know what it is
called". The target is a database **on a host**, and that is what must be
repeated back.

L8: the failure path removed the connection URL from error text by exact
string match. psycopg rewrites a DSN -- reordered parameters, a
percent-encoded password -- so the string in the error is often not the
string we hold, and the replace silently does nothing while looking like
a redaction. Deploy logs are kept.
"""
import os
import unittest
from unittest import mock

from backend.db import settings, upgrade_app


class ConfirmationNamesTheHostTests(unittest.TestCase):
    URL = "postgresql://app_user:pw@db.example.com:5432/sort_tester_app"

    def test_the_database_name_alone_is_no_longer_enough(self):
        # with the target configured, so the refusal is about the
        # confirmation and not about a missing environment variable
        with mock.patch.dict(os.environ, {settings.APP_ENV_VAR: self.URL}):
            code = upgrade_app.main(["--confirm", "sort_tester_app"])
        self.assertEqual(code, 2)

    def test_the_full_target_is_accepted_as_far_as_the_confirmation_goes(self):
        # it will still fail to connect to db.example.com; what matters is
        # that it gets past the confirmation to try
        with mock.patch.dict(os.environ, {settings.APP_ENV_VAR: self.URL}):
            code = upgrade_app.main(
                ["--confirm", "sort_tester_app@db.example.com:5432"]
            )
        self.assertEqual(code, 1, "1 is a connection failure; 2 is a refusal")

    def test_the_target_must_be_repeated_with_its_host_and_port(self):
        target = upgrade_app._target(self.URL)
        self.assertEqual(
            upgrade_app._confirmation_for(target),
            "sort_tester_app@db.example.com:5432",
        )

    def test_the_maintenance_database_is_refused_outright(self):
        # `postgres` exists on every server and is never ours to migrate;
        # a DSN that lost its dbname silently falls back to it
        with self.assertRaises(upgrade_app._Refused):
            upgrade_app._target("postgresql://app_user:pw@db.example.com:5432/postgres")


class ErrorsDoNotCarryThePasswordTests(unittest.TestCase):
    def test_a_reformatted_dsn_is_still_masked(self):
        # the URL psycopg names in an error is not the one we passed: the
        # old exact-match replace left this untouched
        held = "postgresql://app_user:s3cret@db.example.com:5432/sort_tester_app"
        reported = (
            "connection to server failed for"
            ' "postgresql://app_user:s3cret@db.example.com:5432/'
            'sort_tester_app?sslmode=require"'
        )
        masked = upgrade_app._safe(reported, held)
        self.assertNotIn("s3cret", masked)

    def test_a_percent_encoded_password_is_masked_too(self):
        held = "postgresql://app_user:a%40b@db.example.com:5432/sort_tester_app"
        reported = "could not connect: postgresql://app_user:a%40b@db.example.com:5432/x"
        self.assertNotIn("a%40b", upgrade_app._safe(reported, held))

    def test_text_with_no_credentials_is_left_readable(self):
        # a redaction that eats the whole message helps nobody debug
        message = "relation 'alembic_version' does not exist"
        self.assertEqual(upgrade_app._safe(message, "postgresql://u:p@h:5432/d"), message)


if __name__ == "__main__":
    unittest.main()
