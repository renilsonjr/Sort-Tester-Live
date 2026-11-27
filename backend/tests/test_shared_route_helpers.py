"""The helpers every router shares live in one place, and say one thing.

Two rules, each of which was once broken by copying:

* a router takes its connection, its signed-in account and the question
  bank from ``backend.routers.deps``, never from the private names of a
  sibling router;
* "is this account the owner?" is one question with one answer, and a
  deleted owner is not the owner.
"""
import ast
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.auth.owner import is_active_owner
from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

ROUTERS = Path(__file__).resolve().parents[1] / "routers"


class RoutersDoNotReachIntoEachOtherTests(unittest.TestCase):
    def test_no_router_imports_a_private_name_from_another_router(self):
        reached = []
        for path in sorted(ROUTERS.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if not (node.module or "").startswith("backend.routers"):
                    continue
                reached += [
                    f"{path.name}: {node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name.startswith("_")
                ]
        self.assertEqual(reached, [])

    def test_only_the_shared_module_opens_the_pool(self):
        openers = [
            path.name
            for path in sorted(ROUTERS.glob("*.py"))
            if "pool.checkout" in path.read_text()
        ]
        self.assertEqual(openers, ["deps.py"])


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class IsActiveOwnerTests(unittest.TestCase):
    def setUp(self):
        try:
            conninfo = settings.test_database_url()
            admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        migrate.reset_scratch_to_head(admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(conninfo)
        self.addCleanup(self.conn.close)
        client = TestClient(create_app(), headers=BROWSER)
        for username in ("shared_owner", "shared_player"):
            reg = client.post("/api/auth/register", json={"username": username})
            self.assertEqual(reg.status_code, 200, reg.text)
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'shared_owner'",
        )
        self.conn.commit()

    def _id(self, username):
        return migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = %s", (username,)
        )["id"]

    def test_the_owner_is_the_owner_and_a_player_is_not(self):
        self.assertTrue(is_active_owner(self.conn, self._id("shared_owner")))
        self.assertFalse(is_active_owner(self.conn, self._id("shared_player")))

    def test_a_deleted_owner_is_not_the_owner(self):
        owner_id = self._id("shared_owner")
        migrate.execute(
            self.conn, "UPDATE accounts SET deleted_at = now() WHERE id = %s", (owner_id,)
        )
        self.conn.commit()
        self.assertFalse(is_active_owner(self.conn, owner_id))


if __name__ == "__main__":
    unittest.main()
