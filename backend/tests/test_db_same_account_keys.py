"""Related rows cannot belong to different accounts (audit M-10).

Each of these tables already had a foreign key saying "this points at a
real row". None said "and it is the same player's row", so a settlement
could be written against another account's attempt, or a ledger entry
filed under a name that never played the quiz it records.

Nothing in the code does that today. These tests are about what the
database would accept if something did -- a future change, a migration
written by hand, a repair statement typed at three in the morning. Each
one tries the crossed insert and expects the database to refuse it.

The pattern underneath is always the same: a uniqueness key on
`(id, account_id)` of the parent, so the child can reference both columns
together and the pair is what gets checked.
"""
import unittest

import psycopg

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SameAccountKeyTests(unittest.TestCase):
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
        self.alice = self._account("alice_key", "ALICE1")
        self.mallory = self._account("mallory_key", "MALLO1")
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at)"
            " VALUES ('official', 'Keys', now() - interval '1 day') RETURNING id",
        )["id"]
        self.conn.commit()

    def _account(self, username, tag):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (username, username.lower(), tag),
        )["id"]

    def _assignment(self, account_id):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id, self.season),
        )["id"]

    def _attempt(self, account_id, assignment_id=None):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', now())"
            " RETURNING id",
            (account_id, assignment_id or self._assignment(account_id), self.season),
        )["id"]

    def _settlement(self, attempt_id, account_id):
        migrate.execute(
            self.conn,
            "INSERT INTO settlements (attempt_id, account_id, season_id,"
            " raw_score, adjustment, final_outcome, settled_at)"
            " VALUES (%s, %s, %s, 10, 10, 'completed', now())",
            (attempt_id, account_id, self.season),
        )

    # --- what the database must refuse ---

    def test_a_settlement_cannot_be_filed_under_another_account(self):
        attempt = self._attempt(self.alice)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self._settlement(attempt, self.mallory)
        self.conn.rollback()

    def test_a_ledger_entry_cannot_name_an_account_the_settlement_does_not(self):
        attempt = self._attempt(self.alice)
        self._settlement(attempt, self.alice)
        self.conn.commit()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO balance_history (account_id, settlement_id,"
                " raw_score, adjustment, points_before, points_after,"
                " badge_before, badge_after, recorded_at)"
                " VALUES (%s, %s, 10, 10, 0, 10, 'Iron', 'Iron', now())",
                (self.mallory, attempt),
            )
        self.conn.rollback()

    def test_an_attempt_cannot_use_another_accounts_assignment(self):
        mallorys = self._assignment(self.mallory)
        self.conn.commit()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self._attempt(self.alice, assignment_id=mallorys)
        self.conn.rollback()

    def test_a_tiebreak_seat_cannot_point_at_another_accounts_attempt(self):
        attempt = self._attempt(self.alice)
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points,"
            " hats_available, opened_at, status)"
            " VALUES (%s, 'season_close', 100, 1, now(), 'open') RETURNING id",
            (self.season,),
        )["id"]
        round_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_rounds (group_id, round_number, hats,"
            " opened_at, deadline_at, status)"
            " VALUES (%s, 1, 1, now(), now() + interval '1 day', 'open')"
            " RETURNING id",
            (group,),
        )["id"]
        self.conn.commit()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_attempts (round_id, account_id, attempt_id)"
                " VALUES (%s, %s, %s)",
                (round_id, self.mallory, attempt),
            )
        self.conn.rollback()

    # --- and what it must still accept ---

    def test_one_players_own_chain_is_written_without_complaint(self):
        assignment = self._assignment(self.alice)
        attempt = self._attempt(self.alice, assignment_id=assignment)
        self._settlement(attempt, self.alice)
        migrate.execute(
            self.conn,
            "INSERT INTO balance_history (account_id, settlement_id,"
            " raw_score, adjustment, points_before, points_after,"
            " badge_before, badge_after, recorded_at)"
            " VALUES (%s, %s, 10, 10, 0, 10, 'Iron', 'Iron', now())",
            (self.alice, attempt),
        )
        self.conn.commit()
        row = migrate.fetch_one(
            self.conn,
            "SELECT account_id FROM settlements WHERE attempt_id = %s",
            (attempt,),
        )
        self.assertEqual(row["account_id"], self.alice)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RedundantIndexesTests(unittest.TestCase):
    """Two plain btrees sat on columns that each already carry a UNIQUE
    index. A unique index answers every lookup the plain one would, so
    these cost write time and space and bought nothing.
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        cls.conn = migrate.connect(cls.conninfo)
        cls.addClassCleanup(cls.conn.close)

    def _index_names(self, table):
        return {
            row["indexname"]
            for row in migrate.fetch_all(
                self.conn,
                "SELECT indexname FROM pg_indexes WHERE tablename = %s",
                (table,),
            )
        }

    def test_the_duplicate_indexes_are_gone(self):
        self.assertNotIn("sessions_token_hash_idx", self._index_names("sessions"))
        self.assertNotIn(
            "login_credentials_lookup_key_idx",
            self._index_names("login_credentials"),
        )

    def test_the_unique_indexes_that_do_the_work_are_still_there(self):
        # dropping the duplicate must not have taken the lookup with it
        self.assertIn("sessions_token_hash_key", self._index_names("sessions"))
        self.assertIn(
            "login_credentials_lookup_key_key",
            self._index_names("login_credentials"),
        )


if __name__ == "__main__":
    unittest.main()
