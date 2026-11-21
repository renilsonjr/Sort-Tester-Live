"""How many sessions one account may hold, and how long dead rows stay.

Two different problems with the same table.

A session that is never revoked lives until it expires, and nothing
limited how many an account could accumulate: every login on every device
added one, and each is a bearer token that works until its own clock runs
out. Signing in again on a borrowed phone left the old session alive
behind you. The cap makes a new login push out the oldest, so the number
of keys to one account is bounded and the one you stopped using is the
one that goes.

Revoked and expired rows are a different matter: they authenticate
nobody, but they accumulate forever, and each one still points at an
account.

**What is deliberately not here: `ip_address` and `user_agent`.** The
columns exist and login passes None for both. Decision 14 settles this
project on minimal collection -- no real name, no employee id, no phone,
and Decision 15 took email out of the whole app. On a work network, an
address and a timestamp identify a person as surely as a name does. The
owner reaffirmed this on 2026-11-17 when Task 17 proposed recording them,
and `SessionsCollectNoAddressTests` below is that decision written where
it will be noticed: if someone starts populating those columns, this
fails and the choice has to be made again on purpose.
"""
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.auth import sessions
from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

TTL = 3600


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SessionLifecycleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.account_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('sess_user', 'sess_user', 'SESS01') RETURNING id",
        )["id"]
        self.conn.commit()

    def _open(self, n=1):
        tokens = []
        for _ in range(n):
            token, _id = sessions.create_session(
                self.conn, self.account_id, TTL, None, None
            )
            tokens.append(token)
        self.conn.commit()
        return tokens

    def _active(self):
        return migrate.fetch_one(
            self.conn,
            "SELECT count(*) AS n FROM sessions"
            " WHERE account_id = %s AND revoked_at IS NULL",
            (self.account_id,),
        )["n"]


class SessionCapTests(SessionLifecycleTestCase):
    def test_up_to_the_cap_every_session_stays(self):
        self._open(sessions.MAX_ACTIVE_SESSIONS)
        self.assertEqual(self._active(), sessions.MAX_ACTIVE_SESSIONS)

    def test_one_past_the_cap_pushes_out_the_oldest(self):
        self._open(sessions.MAX_ACTIVE_SESSIONS)
        self._open(1)
        self.assertEqual(self._active(), sessions.MAX_ACTIVE_SESSIONS)

    def test_the_session_that_goes_is_the_oldest_not_a_random_one(self):
        first = self._open(1)[0]
        self._open(sessions.MAX_ACTIVE_SESSIONS)  # one past the cap in total
        self.assertIsNone(
            sessions.authenticate_session(self.conn, first),
            "the oldest session must be the one revoked",
        )

    def test_the_newest_session_still_works_afterwards(self):
        self._open(sessions.MAX_ACTIVE_SESSIONS)
        newest = self._open(1)[0]
        self.assertIsNotNone(sessions.authenticate_session(self.conn, newest))

    def test_another_account_is_not_affected(self):
        other = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('sess_two', 'sess_two', 'SESS02') RETURNING id",
        )["id"]
        self.conn.commit()
        for _ in range(sessions.MAX_ACTIVE_SESSIONS + 2):
            sessions.create_session(self.conn, other, TTL, None, None)
        self.conn.commit()

        self._open(1)
        self.assertEqual(self._active(), 1, "the cap is per account")


class ExpiredRowCleanupTests(SessionLifecycleTestCase):
    def _age(self, days):
        # created_at moves too: the schema keeps a row coherent with
        # CHECK (expires_at >= created_at), so a session cannot be made to
        # have expired before it began
        expired_at = datetime.now(timezone.utc) - timedelta(days=days)
        migrate.execute(
            self.conn,
            "UPDATE sessions SET expires_at = %s,"
            " created_at = LEAST(created_at, %s)",
            (expired_at, expired_at),
        )
        self.conn.commit()

    def _rows(self):
        return migrate.fetch_one(
            self.conn, "SELECT count(*) AS n FROM sessions"
        )["n"]

    def test_a_long_expired_row_is_deleted(self):
        self._open(1)
        self._age(3)
        sessions.purge_expired_sessions(self.conn)
        self.conn.commit()
        self.assertEqual(self._rows(), 0)

    def test_a_row_that_expired_just_now_is_kept_for_a_day(self):
        # the grace window is so that a session which has only just ended
        # can still be told apart from one that never existed
        self._open(1)
        self._age(0)
        sessions.purge_expired_sessions(self.conn)
        self.conn.commit()
        self.assertEqual(self._rows(), 1)

    def test_a_live_session_is_never_touched(self):
        token = self._open(1)[0]
        sessions.purge_expired_sessions(self.conn)
        self.conn.commit()
        self.assertIsNotNone(sessions.authenticate_session(self.conn, token))


class SessionsCollectNoAddressTests(SessionLifecycleTestCase):
    """Decision 14, written where a change would trip over it.

    Not a bug guard: a reminder that leaving these empty is a choice this
    project made, so filling them has to be made again on purpose.
    """

    def test_logging_in_records_no_address_and_no_user_agent(self):
        client = TestClient(create_app(), headers=BROWSER)
        reg = client.post("/api/auth/register", json={"username": "privacy_one"})
        self.assertEqual(reg.status_code, 200, reg.text)
        self.assertEqual(
            client.post(
                "/api/auth/login", json={"login_id": reg.json()["login_id"]}
            ).status_code,
            200,
        )

        row = migrate.fetch_one(
            self.conn,
            "SELECT ip_address, user_agent FROM sessions"
            " ORDER BY created_at DESC LIMIT 1",
        )
        self.assertIsNotNone(row, "the login should have created a session")
        self.assertIsNone(row["ip_address"])
        self.assertIsNone(row["user_agent"])

    def test_the_router_passes_nothing_rather_than_omitting_the_argument(self):
        # naming them as None is the decision written at the call site: a
        # reader sees that they are not collected, instead of wondering
        # whether someone forgot. Anything other than None here is a
        # collection change and should fail.
        import pathlib
        import re

        auth_router = (
            pathlib.Path(__file__).resolve().parents[1] / "routers" / "auth.py"
        ).read_text(encoding="utf-8")

        for column in ("ip_address", "user_agent"):
            for match in re.finditer(rf"{column}\s*=\s*([^,\n)]+)", auth_router):
                self.assertEqual(
                    match.group(1).strip(),
                    "None",
                    f"auth.py now passes something for {column}",
                )

    def test_no_response_model_carries_either_column(self):
        # empty today, but a response field would be the shape a later
        # change quietly starts filling
        import pathlib

        routers = pathlib.Path(__file__).resolve().parents[1] / "routers"
        for path in routers.glob("*.py"):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith(("ip_address:", "user_agent:")):
                    self.fail(f"{path.name} declares {stripped} in a model")


if __name__ == "__main__":
    unittest.main()
