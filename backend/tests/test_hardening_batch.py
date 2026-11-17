"""Nine small hardening fixes, named after what each one prevents
(audit L5, L7, L8 and the batch in Task 16).

None of these is a hole on its own. What they have in common is that each
one is a door left on the latch: an owner action without the
re-authentication its siblings require, a reviewer check that a deleted
account still passes, an allowlist that includes a header the caller
controls. They are collected here because they were fixed in one pass,
not because they are one subject.
"""
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.auth import settings as auth_settings_module
from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class HardeningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(self.conninfo)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.owner = TestClient(create_app(), headers=BROWSER)
        self.owner_login = self._sign_in(self.owner, "batch_owner")
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'batch_owner'",
        )
        self.conn.commit()

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login_id = reg.json()["login_id"]
        self.assertEqual(
            client.post("/api/auth/login", json={"login_id": login_id}).status_code,
            200,
        )
        return login_id

    def _reauth(self, client, login_id):
        return client.post("/api/auth/reauthenticate", json={"login_id": login_id})


class LaunchNeedsRecentReauthTests(HardeningTestCase):
    """Launching the official season is the most destructive owner action
    there is: it voids unfinished attempts and resets every balance. Its
    siblings -- approvals, revocations -- all ask the owner to re-enter
    their login ID first. This one did not, so a session left open on a
    shared machine was enough.
    """

    def _launch(self):
        return self.owner.post("/api/ranked/season/launch", json={"confirm": "LAUNCH"})

    def test_it_is_refused_without_a_fresh_login_id(self):
        response = self._launch()
        self.assertEqual(response.status_code, 428, response.text)

    def test_after_reauthenticating_it_is_not_refused_for_that_reason(self):
        self.assertEqual(self._reauth(self.owner, self.owner_login).status_code, 204)
        self.assertNotEqual(self._launch().status_code, 428)


class TicketDescriptionIsCappedTests(HardeningTestCase):
    """An unbounded free-text field is storage someone else chooses the
    size of."""

    def _open_ticket(self, description):
        return self.owner.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": "00000000-0000-0000-0000-000000000000",
                  "description": description},
        )

    def test_a_description_past_the_cap_is_refused_before_anything_is_read(self):
        response = self._open_ticket("x" * 2001)
        self.assertEqual(response.status_code, 422, response.text)

    def test_a_description_at_the_cap_is_not_refused_for_its_length(self):
        response = self._open_ticket("x" * 2000)
        self.assertNotEqual(response.status_code, 422)


class DeletedReviewerTests(HardeningTestCase):
    """A deleted account keeps its row -- deletion is a timestamp, not a
    DELETE -- so a check that reads `is_owner` alone still passes for an
    owner whose account is gone.
    """

    def test_a_soft_deleted_owner_is_no_longer_a_reviewer(self):
        from backend.support import tickets

        owner_id = migrate.fetch_one(
            self.conn,
            "SELECT id FROM accounts WHERE username_lower = 'batch_owner'",
        )["id"]
        tickets._require_reviewer(self.conn, owner_id)  # passes while present

        migrate.execute(
            self.conn,
            "UPDATE accounts SET deleted_at = now() WHERE id = %s",
            (owner_id,),
        )
        self.conn.commit()

        with self.assertRaises(tickets.NotAuthorizedError):
            tickets._require_reviewer(self.conn, owner_id)


class LoginRaceTests(HardeningTestCase):
    """Between creating the session and reading the account back, the
    account can disappear. The read returned None and the route then
    indexed into it: a 500, and a traceback, for something that is simply
    an unauthenticated request.
    """

    def test_an_account_that_vanishes_mid_login_is_a_401_not_a_500(self):
        client = TestClient(create_app(), headers=BROWSER)
        reg = client.post("/api/auth/register", json={"username": "racer_one"})
        login_id = reg.json()["login_id"]

        with mock.patch(
            "backend.routers.auth.get_account_by_session", return_value=None
        ):
            response = client.post("/api/auth/login", json={"login_id": login_id})

        self.assertEqual(response.status_code, 401, response.text)


class OutageIsOwnerOnlyTests(HardeningTestCase):
    """Recording a confirmed outage voids attempts and rewrites flags for
    every account on the server. It had no owner check of its own, which
    was safe only while no route called it -- and that is exactly when the
    check is cheap to add (audit L5).
    """

    def _ids(self):
        rows = migrate.fetch_all(
            self.conn,
            "SELECT id, is_owner FROM accounts WHERE username_lower IN"
            " ('batch_owner', 'batch_player')",
        )
        return {row["is_owner"]: row["id"] for row in rows}

    def setUp(self):
        super().setUp()
        self.player = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.player, "batch_player")

    def test_a_player_cannot_record_an_outage(self):
        from datetime import datetime, timedelta, timezone

        from backend.ranked import outages
        from backend.tests.test_ranked_clock import FakeClock

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(outages.NotOwnerError):
            outages.record_outage(
                self.conn,
                acting_account_id=self._ids()[False],
                starts_at=now,
                ends_at=now + timedelta(minutes=5),
                clock=FakeClock(now),
            )

    def test_nothing_was_written_by_the_refused_attempt(self):
        row = migrate.fetch_one(
            self.conn, "SELECT count(*) AS n FROM confirmed_outages"
        )
        self.assertEqual(row["n"], 0)

    def test_the_owner_is_allowed(self):
        from datetime import datetime, timedelta, timezone

        from backend.ranked import outages
        from backend.tests.test_ranked_clock import FakeClock

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        outages.record_outage(
            self.conn,
            acting_account_id=self._ids()[True],
            starts_at=now,
            ends_at=now + timedelta(minutes=5),
            clock=FakeClock(now + timedelta(minutes=6)),
        )
        row = migrate.fetch_one(
            self.conn, "SELECT count(*) AS n FROM confirmed_outages"
        )
        self.assertEqual(row["n"], 1)


class OriginGuardTests(unittest.TestCase):
    """The allowlist included the request's own Host header.

    Host is set by whoever makes the request. Admitting it meant the guard
    asked the caller where they were from and believed the answer -- so a
    request carrying a matching Origin and Host pair passed, which is the
    one thing the guard exists to refuse.
    """

    def test_a_configured_origin_is_not_widened_by_the_host_header(self):
        from backend import origin_guard

        hosts = origin_guard.allowed_hosts(
            "attacker.example", "https://app.example", []
        )
        self.assertEqual(hosts, {"app.example"})

    def test_without_a_configured_origin_the_host_is_still_the_fallback(self):
        # local development and the first deployment have no app origin yet;
        # removing the fallback there would refuse every write
        from backend import origin_guard

        hosts = origin_guard.allowed_hosts("localhost:8000", "", [])
        self.assertEqual(hosts, {"localhost:8000"})

    def test_development_origins_are_still_allowed_alongside(self):
        from backend import origin_guard

        hosts = origin_guard.allowed_hosts(
            "attacker.example", "https://app.example", ["http://localhost:5173"]
        )
        self.assertEqual(hosts, {"app.example", "localhost:5173"})


class CookieSecureStartupGuardTests(unittest.TestCase):
    """An insecure cookie flag is invisible until someone reads a session
    token off the wire. The default stays False so local HTTP works; what
    cannot happen is serving an https origin without it.
    """

    def test_an_https_origin_with_an_insecure_cookie_refuses_to_start(self):
        with self.assertRaises(auth_settings_module.InsecureCookieError):
            auth_settings_module.check_cookie_policy(
                cookie_secure=False, app_origin="https://app.example"
            )

    def test_plain_http_development_is_left_alone(self):
        auth_settings_module.check_cookie_policy(
            cookie_secure=False, app_origin="http://localhost:8000"
        )
        auth_settings_module.check_cookie_policy(cookie_secure=False, app_origin="")

    def test_an_https_origin_with_a_secure_cookie_is_fine(self):
        auth_settings_module.check_cookie_policy(
            cookie_secure=True, app_origin="https://app.example"
        )


if __name__ == "__main__":
    unittest.main()
