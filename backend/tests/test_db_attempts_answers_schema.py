"""Attempts, active lock, and answer acceptance schema contract (issue #6 check 3)."""
import unittest

import psycopg.errors

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AttemptsAnswersSchemaTests(unittest.TestCase):
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
        # since migration 0007, assignments/attempts.season_id reference
        # seasons(id), so every assignment/attempt cites a real season row
        self.season_id = self._make_season()

    def _next_digest(self):
        return next(self._digest_counter)

    def _make_account(self):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('attempt_user', 'attempt_user', 'C00001') RETURNING id",
        )
        return row["id"]

    def _make_season(self, label="pre_season", phase="pre_season", closed_at=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, closed_at) VALUES (%s, %s, %s) RETURNING id",
            (phase, label, closed_at),
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

    def _make_assignment(self, account_id=None, mode="normal", season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id) VALUES (%s, %s, %s) RETURNING id",
            (account_id or self.account_id, mode, season_id or self.season_id),
        )
        return row["id"]

    def _make_attempt(self, account_id=None, assignment_id=None, mode="normal",
                      state="active", tiebreak_round=None, grace_deadline_at=None,
                      final_outcome=None, settled_at=None, season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, state, tiebreak_round,"
            " season_id, grace_deadline_at, final_outcome, settled_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                account_id or self.account_id,
                assignment_id or self._make_assignment(mode=mode, season_id=season_id),
                mode,
                state,
                tiebreak_round,
                season_id or self.season_id,
                grace_deadline_at,
                final_outcome,
                settled_at,
            ),
        )
        return row["id"]

    def _add_answer(self, attempt_id, seq, question_version_id=None,
                    first_sent_at=None, deadline_at=None, answer=None,
                    outcome="unsent", accepted_at=None):
        # state values are inserted directly to exercise the CHECK constraints
        first_sent_at = first_sent_at or "2026-01-01T00:00:00Z"
        deadline_at = deadline_at or "2026-01-01T00:00:10Z"
        return migrate.execute(
            self.conn,
            "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
            " first_sent_at, deadline_at, answer, outcome, accepted_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (attempt_id, seq, question_version_id or self._make_question_version(),
             first_sent_at, deadline_at, answer, outcome, accepted_at),
        )

    def test_one_active_attempt_per_account_including_grace(self):
        first_attempt_id = self._make_attempt(state="active")
        # a second unfinished attempt is rejected in every unfinished state ...
        with self.assertRaises(migrate.IntegrityError):
            self._make_attempt(state="active")
        with self.assertRaises(migrate.IntegrityError):
            self._make_attempt(
                state="grace", grace_deadline_at="2026-01-01T00:01:00Z"
            )
        with self.assertRaises(migrate.IntegrityError):
            self._make_attempt(
                state="terminal_pending", final_outcome="quit"
            )
        # ... but once the first attempt is finalized (state transitions are
        # the engine's job; the lock index simply stops counting it), a new
        # active attempt inserts
        migrate.execute(
            self.conn,
            "UPDATE attempts SET state = 'finalized', final_outcome = 'completed',"
            " settled_at = now() WHERE id = %s",
            (first_attempt_id,),
        )
        self._make_attempt(state="active")

    def test_finalized_attempt_allows_new_and_never_reactivates(self):
        # SQL does not police the lifecycle (engine concern); the lock's
        # semantics are exactly: any number of finalized rows coexist with
        # at most one unfinished row
        finalized_one = self._make_attempt(
            state="finalized", final_outcome="completed", settled_at="2026-01-01T00:02:00Z"
        )
        finalized_two = self._make_attempt(
            state="finalized", final_outcome="quit", settled_at="2026-01-01T00:03:00Z"
        )
        active = self._make_attempt(state="active")
        rows = migrate.fetch_one(
            self.conn,
            "SELECT count(*) AS n FROM attempts WHERE state = 'finalized'",
        )
        self.assertEqual(rows["n"], 2)
        self.assertIsNotNone(finalized_one)
        self.assertIsNotNone(finalized_two)
        self.assertIsNotNone(active)

    def test_answer_immutable_unique_key(self):
        attempt_id = self._make_attempt()
        version_id = self._make_question_version()
        self._add_answer(attempt_id, 1, version_id)
        # second insert with the same (attempt_id, seq) is rejected ...
        with self.assertRaises(migrate.IntegrityError):
            self._add_answer(attempt_id, 1, version_id)
        # ... an answer recorded without its acceptance timestamp is rejected ...
        with self.assertRaises(migrate.IntegrityError):
            self._add_answer(attempt_id, 2, answer="correct", outcome="correct")
        # ... first_sent_at is mandatory, with every other required column supplied ...
        with self.assertRaises(psycopg.errors.NotNullViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
                " first_sent_at, deadline_at, outcome)"
                " VALUES (%s, %s, %s, NULL, %s, 'unsent')",
                (attempt_id, 3, self._make_question_version(), "2026-01-01T00:00:10Z"),
            )
        # ... and the deadline must lie strictly after first_sent_at
        with self.assertRaises(migrate.IntegrityError):
            self._add_answer(
                attempt_id, 4,
                first_sent_at="2026-01-01T00:00:10Z",
                deadline_at="2026-01-01T00:00:10Z",
            )

    def test_answer_outcome_and_bounds(self):
        attempt_id = self._make_attempt()
        # outcome outside the enum is rejected ...
        with self.assertRaises(migrate.IntegrityError):
            self._add_answer(attempt_id, 1, outcome="forfeit")
        # ... seq bounds match the assignment layout ...
        with self.assertRaises(migrate.IntegrityError):
            self._add_answer(attempt_id, 0)
        with self.assertRaises(migrate.IntegrityError):
            self._add_answer(attempt_id, 16)
        self._add_answer(attempt_id, 15)
        # ... tiebreak_round is only valid on tiebreak attempts, inside 1..5;
        # dedicated accounts keep the active-attempt lock from masking either CHECK
        normal_round_account = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('normal_round_user', 'normal_round_user', 'C00004') RETURNING id",
        )
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_attempt(
                account_id=normal_round_account["id"], mode="normal", tiebreak_round=2
            )
        tiebreak_round_account = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('tiebreak_round_user', 'tiebreak_round_user', 'C00005') RETURNING id",
        )
        with self.assertRaises(psycopg.errors.CheckViolation):
            self._make_attempt(
                account_id=tiebreak_round_account["id"], mode="tiebreak", tiebreak_round=6
            )
        # NULL round is allowed even on a tiebreak attempt (the round number
        # is engine-assigned at round creation; NULL means not yet slotted);
        # a dedicated account so the active lock on the first attempt does
        # not interfere
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('tiebreak_user', 'tiebreak_user', 'C00003') RETURNING id",
        )
        self._make_attempt(account_id=row["id"], mode="tiebreak", tiebreak_round=None)

    def test_attempt_answer_accepts_exactly_once(self):
        attempt_id = self._make_attempt()
        self._add_answer(attempt_id, 1, answer=None, outcome="unsent", accepted_at=None)
        migrate.execute(
            self.conn,
            "UPDATE attempt_answers SET answer = 'correct', accepted_at = now()"
            " WHERE attempt_id = %s AND seq = 1",
            (attempt_id,),
        )
        row = migrate.fetch_one(
            self.conn,
            "SELECT answer, outcome, accepted_at FROM attempt_answers"
            " WHERE attempt_id = %s AND seq = 1",
            (attempt_id,),
        )
        self.assertEqual(row["answer"], "correct")
        self.assertEqual(row["outcome"], "unsent")
        self.assertIsNotNone(row["accepted_at"])
        with self.assertRaises(psycopg.errors.RaiseException):
            migrate.execute(
                self.conn,
                "UPDATE attempt_answers SET answer = 'wrong', accepted_at = now()"
                " WHERE attempt_id = %s AND seq = 1",
                (attempt_id,),
            )

    def test_attempt_answer_send_timestamp_is_immutable(self):
        attempt_id = self._make_attempt()
        self._add_answer(attempt_id, 1)
        with self.assertRaises(psycopg.errors.RaiseException):
            migrate.execute(
                self.conn,
                "UPDATE attempt_answers SET first_sent_at = '2026-01-01T00:00:01Z'"
                " WHERE attempt_id = %s AND seq = 1",
                (attempt_id,),
            )

    def test_attempt_and_answers_cascade_with_account(self):
        # a dedicated account so the shared setUp account is untouched
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('cascade_user', 'cascade_user', 'C00002') RETURNING id",
        )
        doomed_account_id = row["id"]
        attempt_id = self._make_attempt(account_id=doomed_account_id)
        self._add_answer(attempt_id, 1)
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (doomed_account_id,))
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM attempts WHERE id = %s", (attempt_id,))
        )
        self.assertIsNone(
            migrate.fetch_one(
                self.conn,
                "SELECT 1 FROM attempt_answers WHERE attempt_id = %s",
                (attempt_id,),
            )
        )
