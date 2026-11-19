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
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
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

    def test_the_unchecked_regenerate_endpoint_is_withdrawn(self):
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

        # Withdrawn: this route reset a login ID on the owner's say-so
        # alone, which the settled recovery policy does not allow. It now
        # says where recovery lives instead of quietly serving one.
        response = self.client.post("/api/auth/admin/regenerate", json={"account_id": target_id})
        self.assertEqual(response.status_code, 410)
        self.assertIn("Access recovery", response.json()["detail"])
        self.assertNotIn("login_id", response.text)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SessionWritePersistenceTests(unittest.TestCase):
    """A session write has to survive the request that made it (audit H-1).

    These go through the HTTP layer on purpose. The manager-level tests in
    ``test_auth_sessions`` keep one connection open across the call, so an
    uncommitted UPDATE is still visible to them inside that transaction;
    a request closes its own connection, and an uncommitted write is gone.
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.client = TestClient(create_app(), headers=BROWSER)

    def _read_session(self):
        """The one live session row, read on a connection of its own."""
        conn = migrate.connect(self.conninfo)
        self.addCleanup(conn.close)
        return migrate.fetch_one(
            conn,
            "SELECT id, last_seen_at, revoked_at FROM sessions"
            " ORDER BY created_at DESC LIMIT 1",
        )

    def _login(self, username):
        reg = self.client.post("/api/auth/register", json={"username": username})
        login_id = reg.json()["login_id"]
        self.client.post("/api/auth/login", json={"login_id": login_id})

    def test_last_seen_at_advances_across_authenticated_requests(self):
        self._login("h1_user")
        before = self._read_session()["last_seen_at"]

        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

        self.assertGreater(self._read_session()["last_seen_at"], before)

    def test_idle_revocation_persists_after_the_refusal(self):
        self._login("h1_idle")
        session_id = self._read_session()["id"]
        aging = migrate.connect(self.conninfo)
        self.addCleanup(aging.close)
        migrate.execute(
            aging,
            "UPDATE sessions SET last_seen_at = now() - interval '16 minutes'"
            " WHERE id = %s",
            (session_id,),
        )
        aging.commit()

        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

        # the refusal is not enough: the row has to carry the revocation,
        # or the same token works again on the next request
        self.assertIsNotNone(self._read_session()["revoked_at"])


if __name__ == "__main__":
    unittest.main()
