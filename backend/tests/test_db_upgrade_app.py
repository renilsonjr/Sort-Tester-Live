"""The guarded command that migrates the application database (issue #75)."""
import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from backend.db import upgrade_app

APP_URL = "postgresql://appuser:s3cret-pass@db.example.com:5432/sort_tester_app"


def run(argv, env_url=APP_URL):
    """Run the command with a fake environment; return (exit code, stdout, stderr, upgrade mock)."""
    out, err = io.StringIO(), io.StringIO()
    environment = {} if env_url is None else {"SORT_TESTER_DATABASE_URL": env_url}
    with patch.dict(os.environ, environment, clear=True), \
            patch.object(upgrade_app.migrate, "upgrade_to_head") as upgrade, \
            patch.object(upgrade_app.migrate, "current_revision", side_effect=["0008", "0009"]), \
            redirect_stdout(out), redirect_stderr(err):
        code = upgrade_app.main(argv)
    return code, out.getvalue(), err.getvalue(), upgrade


class UpgradeAppCommandTests(unittest.TestCase):
    def test_confirmed_target_is_upgraded_to_head(self):
        code, out, _err, upgrade = run(["--confirm", "sort_tester_app"])
        self.assertEqual(code, 0)
        upgrade.assert_called_once_with(APP_URL)
        self.assertIn("sort_tester_app", out)
        self.assertIn("db.example.com:5432", out)
        self.assertIn("0008", out)
        self.assertIn("0009", out)

    def test_missing_confirmation_refuses_before_connecting(self):
        code, _out, err, upgrade = run([])
        self.assertEqual(code, 2)
        upgrade.assert_not_called()
        self.assertIn("--confirm", err)

    def test_wrong_confirmation_refuses_before_connecting(self):
        code, _out, err, upgrade = run(["--confirm", "some_other_db"])
        self.assertEqual(code, 2)
        upgrade.assert_not_called()
        self.assertIn("sort_tester_app", err)

    def test_missing_url_refuses(self):
        code, _out, err, upgrade = run(["--confirm", "sort_tester_app"], env_url=None)
        self.assertEqual(code, 2)
        upgrade.assert_not_called()
        self.assertIn("SORT_TESTER_DATABASE_URL", err)

    def test_test_url_alone_is_never_used(self):
        out, err = io.StringIO(), io.StringIO()
        environment = {"SORT_TESTER_TEST_DATABASE_URL": "postgresql://u@h:5432/sort_tester_unittest_scratch"}
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(upgrade_app.migrate, "upgrade_to_head") as upgrade, \
                redirect_stdout(out), redirect_stderr(err):
            code = upgrade_app.main(["--confirm", "sort_tester_unittest_scratch"])
        self.assertEqual(code, 2)
        upgrade.assert_not_called()

    def test_scratch_database_is_refused(self):
        url = "postgresql://u@127.0.0.1:5432/sort_tester_unittest_scratch"
        code, _out, err, upgrade = run(["--confirm", "sort_tester_unittest_scratch"], env_url=url)
        self.assertEqual(code, 2)
        upgrade.assert_not_called()
        self.assertIn("scratch", err)

    def test_malformed_url_refuses(self):
        for url in ("not a url", "mysql://u@h/db", "postgresql://u@h"):
            with self.subTest(url=url):
                code, _out, _err, upgrade = run(["--confirm", "db"], env_url=url)
                self.assertEqual(code, 2)
                upgrade.assert_not_called()

    def test_password_is_never_printed(self):
        for argv in (["--confirm", "sort_tester_app"], ["--confirm", "wrong"], []):
            with self.subTest(argv=argv):
                _code, out, err, _upgrade = run(argv)
                self.assertNotIn("s3cret-pass", out + err)

    def test_upgrade_failure_returns_nonzero_without_password(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"SORT_TESTER_DATABASE_URL": APP_URL}, clear=True), \
                patch.object(upgrade_app.migrate, "current_revision", return_value="0008"), \
                patch.object(upgrade_app.migrate, "upgrade_to_head",
                             side_effect=RuntimeError(f"could not connect to {APP_URL}")), \
                redirect_stdout(out), redirect_stderr(err):
            code = upgrade_app.main(["--confirm", "sort_tester_app"])
        self.assertEqual(code, 1)
        self.assertNotIn("s3cret-pass", out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()
