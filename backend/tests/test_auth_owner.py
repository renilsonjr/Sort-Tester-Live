"""The one-time local owner bootstrap command (issue #47, slice 1)."""
import contextlib
import io
import unittest

from backend.auth import owner
from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OwnerBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        try:
            migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)

    def _account(self, tag, username=None, deleted=False):
        username = username or f"player_{tag.lower()}"
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, deleted_at)"
            " VALUES (%s, %s, %s, CASE WHEN %s THEN now() END) RETURNING id",
            (username, username.lower(), tag, deleted),
        )
        self.conn.commit()
        return row["id"]

    def _owners(self):
        rows = migrate.fetch_all(self.conn, "SELECT tag FROM accounts WHERE is_owner")
        self.conn.commit()
        return [row["tag"] for row in rows]

    def test_designating_makes_the_account_the_owner(self):
        account_id = self._account("A1B2C3", username="renilson")
        result = owner.designate_owner(self.conn, "A1B2C3")
        self.assertEqual(
            (result["account_id"], result["username"], result["tag"]),
            (account_id, "renilson", "A1B2C3"),
        )
        self.assertEqual(self._owners(), ["A1B2C3"])

    def test_a_lower_case_tag_matches(self):
        self._account("A1B2C3")
        owner.designate_owner(self.conn, "a1b2c3")
        self.assertEqual(self._owners(), ["A1B2C3"])

    def test_a_second_owner_is_refused(self):
        self._account("A1B2C3")
        self._account("C3D4E5")
        owner.designate_owner(self.conn, "A1B2C3")
        with self.assertRaises(owner.OwnerExistsError):
            owner.designate_owner(self.conn, "C3D4E5")
        with self.assertRaises(owner.OwnerExistsError):
            owner.designate_owner(self.conn, "A1B2C3")  # even the same account
        self.assertEqual(self._owners(), ["A1B2C3"])

    def test_an_unknown_tag_is_refused(self):
        self._account("A1B2C3")
        with self.assertRaises(owner.AccountNotFoundError):
            owner.designate_owner(self.conn, "ZZZZZZ")
        self.assertEqual(self._owners(), [])

    def test_an_account_pending_deletion_is_refused(self):
        self._account("A1B2C3", deleted=True)
        with self.assertRaises(owner.AccountNotFoundError):
            owner.designate_owner(self.conn, "A1B2C3")
        self.assertEqual(self._owners(), [])

    def test_the_database_refuses_a_second_owner_written_directly(self):
        self._account("A1B2C3")
        self._account("C3D4E5")
        owner.designate_owner(self.conn, "A1B2C3")
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(
                self.conn, "UPDATE accounts SET is_owner = true WHERE tag = 'C3D4E5'"
            )
        self.conn.rollback()
        self.assertEqual(self._owners(), ["A1B2C3"])

    # --- the command ---

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = owner.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_the_command_designates_and_reports(self):
        self._account("A1B2C3", username="renilson")
        code, out, err = self._run("designate", "--tag", "A1B2C3")
        self.assertEqual(code, 0, err)
        self.assertIn("renilson", out)
        self.assertIn("A1B2C3", out)
        self.assertEqual(self._owners(), ["A1B2C3"])

    def test_the_command_reports_a_refusal(self):
        self._account("A1B2C3")
        code, out, err = self._run("designate", "--tag", "ZZZZZZ")
        self.assertEqual(code, 1)
        self.assertIn("ZZZZZZ", err)
        self.assertEqual(self._owners(), [])

    # --- show: "which account is the owner here?" ---

    def test_show_names_the_owner(self):
        self._account("A1B2C3", username="renilson")
        self._run("designate", "--tag", "A1B2C3")
        code, out, err = self._run("show")
        self.assertEqual(code, 0, err)
        self.assertIn("renilson", out)
        self.assertIn("A1B2C3", out)

    def test_show_says_so_when_no_owner_has_been_designated(self):
        """How a fresh deployment is checked."""
        code, out, err = self._run("show")
        self.assertEqual(code, 0, err)
        self.assertIn("No owner", out)

    def test_show_changes_nothing(self):
        self._account("A1B2C3")
        self._run("designate", "--tag", "A1B2C3")
        self._run("show")
        self.assertEqual(self._owners(), ["A1B2C3"])

    # --- reissue-login-id: the locked-out owner ---

    def test_reissue_gives_the_owner_a_new_login_id(self):
        """The owner cannot use the in-app recovery, because that needs an
        owner session and a locked-out owner has none."""
        self._account("A1B2C3", username="renilson")
        self._run("designate", "--tag", "A1B2C3")
        code, out, err = self._run("reissue-login-id")
        self.assertEqual(code, 0, err)
        self.assertIn("renilson", out)
        self.assertIn("shown once", out)

    def test_reissue_is_refused_when_there_is_no_owner(self):
        code, out, err = self._run("reissue-login-id")
        self.assertEqual(code, 1)
        self.assertIn("no owner", err)

    def test_reissue_ends_the_owner_sessions(self):
        self._account("A1B2C3")
        self._run("designate", "--tag", "A1B2C3")
        account_id = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE tag = 'A1B2C3'"
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO sessions (account_id, token_hash, expires_at)"
            " VALUES (%s, %s, now() + interval '1 hour')",
            (account_id, b"y" * 32),
        )
        self.conn.commit()
        self._run("reissue-login-id")
        live = migrate.fetch_all(
            self.conn,
            "SELECT id FROM sessions WHERE account_id = %s AND revoked_at IS NULL",
            (account_id,),
        )
        self.assertEqual(live, [])

    def test_reissue_keeps_the_owner_role_and_the_same_account(self):
        self._account("A1B2C3", username="renilson")
        self._run("designate", "--tag", "A1B2C3")
        self._run("reissue-login-id")
        self.assertEqual(self._owners(), ["A1B2C3"])


if __name__ == "__main__":
    unittest.main()
