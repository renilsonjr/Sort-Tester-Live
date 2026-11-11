"""Question versions and frozen assignments schema contract (issue #6 check 3)."""
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class QuestionsAssignmentsSchemaTests(unittest.TestCase):
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

    def _next_digest(self):
        return next(self._digest_counter)

    def _make_account(self):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('assign_user', 'assign_user', 'C00001') RETURNING id",
        )
        return row["id"]

    def _make_question_version(self, bank_key="sort.basic", difficulty="easy", digest=None):
        digest = digest or self._next_digest()
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO question_versions (bank_key, difficulty, content_sha256)"
            " VALUES (%s, %s, %s) RETURNING id",
            (bank_key, difficulty, digest),
        )
        return row["id"]

    def _make_assignment(self, account_id=None, mode="normal", season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id) VALUES (%s, %s, %s) RETURNING id",
            (account_id or self.account_id, mode, season_id or self.account_id),
        )
        return row["id"]

    def _add_question(self, assignment_id, seq, question_version_id):
        return migrate.execute(
            self.conn,
            "INSERT INTO assignment_questions (assignment_id, seq, question_version_id) VALUES (%s, %s, %s)",
            (assignment_id, seq, question_version_id),
        )

    def test_question_version_unique_per_bank_key_and_digest(self):
        digest = self._next_digest()
        self._make_question_version(bank_key="sort.basic", digest=digest)
        # same (bank_key, digest) twice is rejected ...
        with self.assertRaises(migrate.IntegrityError):
            self._make_question_version(bank_key="sort.basic", digest=digest)
        # ... but the same bank_key with a different digest coexists
        # (a corrected future version of the same question)
        self._make_question_version(bank_key="sort.basic", digest=self._next_digest())
        row = migrate.fetch_one(
            self.conn,
            "SELECT count(*) AS n FROM question_versions WHERE bank_key = 'sort.basic'",
        )
        self.assertEqual(row["n"], 2)

    def test_assignment_questions_unique_seq_and_no_repeat(self):
        assignment_id = self._make_assignment()
        version_id = self._make_question_version()
        other_version_id = self._make_question_version()
        self._add_question(assignment_id, 1, version_id)
        # second row with the same (assignment_id, seq) is rejected ...
        with self.assertRaises(migrate.IntegrityError):
            self._add_question(assignment_id, 1, other_version_id)
        # ... and the same question twice in one assignment (different seq) is
        # rejected by the no-repeat unique index ...
        with self.assertRaises(migrate.IntegrityError):
            self._add_question(assignment_id, 2, version_id)
        # ... while a different question at a different seq coexists
        self._add_question(assignment_id, 2, other_version_id)

    def test_assignment_seq_bounds(self):
        assignment_id = self._make_assignment()
        version_id = self._make_question_version()
        with self.assertRaises(migrate.IntegrityError):
            self._add_question(assignment_id, 0, version_id)
        with self.assertRaises(migrate.IntegrityError):
            self._add_question(assignment_id, 16, version_id)
        # the boundary values themselves are inside the CHECK
        self._add_question(assignment_id, 1, version_id)
        self._add_question(assignment_id, 15, self._make_question_version())

    def test_assignment_cascades_with_account(self):
        # a dedicated account so the shared setUp account is untouched
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('cascade_user', 'cascade_user', 'C00002') RETURNING id",
        )
        doomed_account_id = row["id"]
        assignment_id = self._make_assignment(account_id=doomed_account_id)
        version_id = self._make_question_version()
        self._add_question(assignment_id, 1, version_id)
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (doomed_account_id,))
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM assignments WHERE id = %s", (assignment_id,))
        )
        self.assertIsNone(
            migrate.fetch_one(
                self.conn,
                "SELECT 1 FROM assignment_questions WHERE assignment_id = %s",
                (assignment_id,),
            )
        )
        # question_versions is insert-only shared content: it must survive
        self.assertIsNotNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM question_versions WHERE id = %s", (version_id,))
        )
