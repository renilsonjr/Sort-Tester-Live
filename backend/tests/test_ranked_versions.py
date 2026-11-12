"""Durable question-version materialization (issue #8, piece 2)."""
import tempfile
import unittest

from backend.db import migrate, settings
from backend.ranked.versions import materialize_question_version
from backend.ranked_bank.identity import question_content_digest
from backend.tests.ranked_helpers import make_unconstrained_bank


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class QuestionVersionMaterializationTests(unittest.TestCase):
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
        bank = make_unconstrained_bank(tempfile.mkdtemp())
        self.question = bank.questions[0]

    def test_insert_then_reuse_is_idempotent(self):
        first = materialize_question_version(self.conn, self.question)
        self.conn.commit()
        second = materialize_question_version(self.conn, self.question)
        self.conn.commit()
        self.assertEqual(first, second)
        count = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM question_versions WHERE bank_key = %s",
            (self.question.canonical_id,),
        )
        self.assertEqual(count["n"], 1)

    def test_row_records_key_difficulty_and_digest(self):
        version_id = materialize_question_version(self.conn, self.question)
        self.conn.commit()
        row = migrate.fetch_one(
            self.conn,
            "SELECT bank_key, difficulty, content_sha256 FROM question_versions WHERE id = %s",
            (version_id,),
        )
        self.assertEqual(row["bank_key"], self.question.canonical_id)
        self.assertEqual(row["difficulty"], self.question.difficulty.lower())
        self.assertEqual(row["content_sha256"], question_content_digest(self.question))


if __name__ == "__main__":
    unittest.main()
