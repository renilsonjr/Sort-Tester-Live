import unittest

from fastapi.testclient import TestClient

from backend.tests.browser import BROWSER

from backend.db import migrate, settings
from backend.main import create_app


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AuthRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        app = create_app()
        self.client = TestClient(app, headers=BROWSER)

    def test_register_endpoint_returns_login_id_once(self):
        response = self.client.post("/api/auth/register", json={"username": "router_user"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("account_id", data)
        self.assertIn("login_id", data)
        self.assertEqual(len(data["login_id"].replace("-", "")), 16)

    def test_login_endpoint_sets_session_cookie(self):
        reg = self.client.post("/api/auth/register", json={"username": "router_user2"})
        login_id = reg.json()["login_id"]

        response = self.client.post("/api/auth/login", json={"login_id": login_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("sort_tester_session", self.client.cookies)
        data = response.json()
        self.assertEqual(data["username"], "router_user2")

    def test_me_endpoint_requires_session(self):
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_logout_endpoint_clears_session(self):
        reg = self.client.post("/api/auth/register", json={"username": "router_user3"})
        login_id = reg.json()["login_id"]
        self.client.post("/api/auth/login", json={"login_id": login_id})

        response = self.client.post("/api/auth/logout")
        self.assertEqual(response.status_code, 204)
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 401)

    def test_admin_regenerate_endpoint(self):
        # Set up owner in a committed connection so the router can see it.
        setup_conn = migrate.connect(self.conninfo)
        owner_id = migrate.fetch_one(
            setup_conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner) VALUES ('owner_r', 'owner_r', 'OWNR01', true) RETURNING id",
        )["id"]
        setup_conn.commit()
        setup_conn.close()

        reg = self.client.post("/api/auth/register", json={"username": "target_r"})
        target_id = reg.json()["account_id"]

        # Create a session for the owner directly.
        from backend.auth.sessions import create_session

        session_conn = migrate.connect(self.conninfo)
        owner_token, _ = create_session(session_conn, owner_id, 3600, None, None)
        session_conn.commit()
        session_conn.close()
        self.client.cookies["sort_tester_session"] = owner_token

        response = self.client.post("/api/auth/admin/regenerate", json={"account_id": target_id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("login_id", response.json())


if __name__ == "__main__":
    unittest.main()
