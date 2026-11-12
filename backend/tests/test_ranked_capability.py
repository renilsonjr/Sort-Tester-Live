"""Page-instance capability for ranked attempts (issue #8, slice 4)."""
import hashlib
import tempfile
from datetime import datetime, timezone
import unittest

from backend.db import migrate, settings
from backend.ranked import capability, engine
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock


class CapabilityTokenTests(unittest.TestCase):
    def test_new_tokens_are_long_and_different(self):
        first, second = capability.new_token(), capability.new_token()
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 40)

    def test_hash_is_the_sha256_of_the_token(self):
        self.assertEqual(
            capability.hash_token("abc"), hashlib.sha256(b"abc").digest()
        )


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class CapabilityStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        try:
            migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(self.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.bank = make_unconstrained_bank(tempfile.mkdtemp())
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'test-season')",
        )
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('cap_player', 'cap_player', 'C00001') RETURNING id",
        )
        self.conn.commit()
        self.account_id = row["id"]

    def _start(self, token):
        return engine.start_attempt(
            self.conn, self.account_id, clock=self.clock, bank=self.bank,
            page_capability=token,
        )

    def test_start_stores_the_hash_and_never_the_token(self):
        token = capability.new_token()
        attempt_id = self._start(token)
        row = migrate.fetch_one(
            self.conn,
            "SELECT page_capability_sha256 AS stored FROM attempts WHERE id = %s",
            (attempt_id,),
        )
        self.assertEqual(bytes(row["stored"]), capability.hash_token(token))
        self.assertNotIn(token.encode("ascii"), bytes(row["stored"]))

    def test_the_right_token_matches(self):
        token = capability.new_token()
        attempt_id = self._start(token)
        self.assertTrue(capability.matches(self.conn, attempt_id, token))

    def test_wrong_empty_missing_and_odd_tokens_do_not_match(self):
        attempt_id = self._start(capability.new_token())
        for bad in (capability.new_token(), "", None, "não-ascii"):
            with self.subTest(bad=bad):
                self.assertFalse(capability.matches(self.conn, attempt_id, bad))

    def test_attempt_started_without_a_capability_matches_nothing(self):
        attempt_id = engine.start_attempt(
            self.conn, self.account_id, clock=self.clock, bank=self.bank
        )
        self.assertFalse(
            capability.matches(self.conn, attempt_id, capability.new_token())
        )
        self.assertFalse(capability.matches(self.conn, attempt_id, None))


if __name__ == "__main__":
    unittest.main()
