"""Seasons, phase guards, and unique settlement keys schema contract (issue #6 check 3)."""
import unittest

import psycopg.errors

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SeasonsSettlementsSchemaTests(unittest.TestCase):
    _digest_counter = iter(
        f"{index:064x}" for index in range(1, 1000)
    )

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
        # rollback at teardown keeps tests isolated (no committed rows leak between
        # tests; only the migration's schema is committed); cleanups run LIFO, so
        # register close first to roll back before closing
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.account_id = self._make_account()
        # the first season is already closed: cutover opens the next row
        self.season_id = self._make_season(
            label="pre_season",
            opened_at="2026-01-01T00:00:00Z",
            closed_at="2026-01-15T00:00:00Z",
        )

    def _next_digest(self):
        return next(self._digest_counter)

    def _make_account(self):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('season_user', 'season_user', 'C00001') RETURNING id",
        )
        return row["id"]

    def _make_season(self, label="pre_season", phase="pre_season",
                     opened_at=None, closed_at=None):
        # state values are inserted directly to exercise the CHECK
        # constraints; omitted timestamps are left to the column defaults
        # (an explicit NULL would override DEFAULT now())
        columns = ["phase", "label"]
        values = [phase, label]
        if opened_at is not None:
            columns.append("opened_at")
            values.append(opened_at)
        if closed_at is not None:
            columns.append("closed_at")
            values.append(closed_at)
        placeholders = ", ".join(["%s"] * len(values))
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons ({}) VALUES ({}) RETURNING id".format(
                ", ".join(columns), placeholders
            ),
            values,
        )
        return row["id"]

    def _make_question_version(self, digest=None):
        digest = digest or self._next_digest()
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO question_versions (bank_key, difficulty, content_sha256)"
            " VALUES ('sort.basic', 'easy', %s) RETURNING id",
            (digest,),
        )
        return row["id"]

    def _make_assignment(self, season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (self.account_id, season_id or self.season_id),
        )
        return row["id"]

    def _make_attempt(self, season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, state,"
            " season_id, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', 'terminal_pending', %s, 'quit', now())"
            " RETURNING id",
            (self.account_id, self._make_assignment(season_id),
             season_id or self.season_id),
        )
        return row["id"]

    def _make_settlement(self, attempt_id, season_id=None, raw_score=120,
                         adjustment=0, final_outcome="quit"):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO settlements (attempt_id, season_id, raw_score,"
            " adjustment, final_outcome)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING attempt_id",
            (attempt_id, season_id or self.season_id, raw_score, adjustment,
             final_outcome),
        )
        return row["attempt_id"]

    def test_settlement_unique_per_attempt(self):
        attempt_id = self._make_attempt()
        settled = self._make_settlement(attempt_id)
        # the PK on attempt_id IS the settlement key: a repeated terminal
        # request finds the existing row, so a second insert is rejected ...
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self._make_settlement(attempt_id)
        # ... and the original row stands untouched
        row = migrate.fetch_one(
            self.conn,
            "SELECT attempt_id, raw_score FROM settlements WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.assertEqual(row["attempt_id"], settled)
        self.assertEqual(row["raw_score"], 120)

    def test_settlement_raw_score_bounds_and_outcome_enum(self):
        attempt_id = self._make_attempt()
        # raw_score outside [-150, 300] is rejected ...
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_settlement(attempt_id, raw_score=-151)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_settlement(attempt_id, raw_score=301)
        # ... final_outcome outside the enum is rejected ...
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_settlement(attempt_id, final_outcome="forfeit")
        # ... and both boundary scores are inside the CHECK
        self._make_settlement(attempt_id, raw_score=-150)
        migrate.execute(
            self.conn,
            "UPDATE settlements SET raw_score = 300 WHERE attempt_id = %s",
            (attempt_id,),
        )

    def test_season_phase_and_close_ordering(self):
        # phase outside the enum is rejected ...
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_season(label="bad_phase", phase="offseason")
        # ... closed_at before opened_at is rejected ...
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_season(
                label="reversed",
                opened_at="2026-02-01T00:00:00Z",
                closed_at="2026-01-01T00:00:00Z",
            )
        # ... and the label is unique across seasons
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self._make_season(label="pre_season")

    def test_attempts_and_assignments_now_reference_seasons(self):
        ghost_season_id = "00000000-0000-0000-0000-0000000000f7"
        # an assignment whose season_id has no seasons row is rejected ...
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO assignments (account_id, mode, season_id)"
                " VALUES (%s, 'normal', %s)",
                (self.account_id, ghost_season_id),
            )
        # ... and so is an attempt referencing that same unknown season ...
        assignment_id = self._make_assignment()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO attempts (account_id, assignment_id, mode, state,"
                " season_id, final_outcome, settled_at)"
                " VALUES (%s, %s, 'normal', 'terminal_pending', %s, 'quit', now())",
                (self.account_id, assignment_id, ghost_season_id),
            )
        # ... while both tables accept a season that exists
        self.assertIsNotNone(assignment_id)
        self.assertIsNotNone(self._make_attempt())

    def test_settlement_must_use_attempts_season(self):
        official_season_id = self._make_season(label="official", phase="official")
        attempt_id = self._make_attempt(season_id=self.season_id)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self._make_settlement(attempt_id, season_id=official_season_id)

    def test_settlement_cascade_and_season_immutable_history(self):
        # cutover: the closed Pre-Season row stands and the official season
        # opens as a new row — history is never mutated
        season_two_id = self._make_season(label="official", phase="official")
        attempt_id = self._make_attempt(season_id=self.season_id)
        self._make_settlement(attempt_id, season_id=self.season_id)
        seasons_before = migrate.fetch_one(
            self.conn,
            "SELECT count(*) AS n,"
            " count(*) FILTER (WHERE label = 'pre_season') AS pre,"
            " count(*) FILTER (WHERE label = 'official') AS official"
            " FROM seasons",
        )
        self.assertEqual(seasons_before["n"], 2)
        self.assertEqual(seasons_before["pre"], 1)
        self.assertEqual(seasons_before["official"], 1)
        # deleting the attempt cascades its single settlement ...
        migrate.execute(self.conn, "DELETE FROM attempts WHERE id = %s", (attempt_id,))
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM settlements WHERE attempt_id = %s", (attempt_id,))
        )
        # ... and both season rows survive untouched (opened/closed stamps
        # are never rewritten by the cascade or the cutover)
        seasons_after = migrate.fetch_one(
            self.conn,
            "SELECT count(*) AS n,"
            " count(*) FILTER (WHERE label = 'pre_season'"
            "   AND closed_at = '2026-01-15T00:00:00Z') AS pre_closed,"
            " count(*) FILTER (WHERE label = 'official' AND closed_at IS NULL)"
            "   AS official_open"
            " FROM seasons",
        )
        self.assertEqual(seasons_after["n"], 2)
        self.assertEqual(seasons_after["pre_closed"], 1)
        self.assertEqual(seasons_after["official_open"], 1)
