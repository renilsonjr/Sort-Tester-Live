"""Which statements run under a savepoint, and what that costs a request.

A savepoint is two more round trips to the server per statement. Writes
need one, because callers recover from a refused write and carry on in the
same transaction. Reads do not, and they are most of what a request does.
"""
import unittest
from unittest import mock

import psycopg
from fastapi.testclient import TestClient
from psycopg.pq import TransactionStatus

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER


class PlainReadTests(unittest.TestCase):
    def test_a_select_is_a_plain_read(self):
        for text in ("SELECT 1", "select 1", "  \n  SELECT id FROM accounts", "Select 1"):
            self.assertTrue(migrate._is_plain_read(text), text)

    def test_everything_else_is_treated_as_a_write(self):
        for text in (
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET a = 1",
            "DELETE FROM t",
            "INSERT INTO t SELECT 1",
            # a WITH can write from inside the query
            "WITH gone AS (DELETE FROM t RETURNING id) SELECT id FROM gone",
            "WITH x AS (SELECT 1) SELECT * FROM x",
            "",
        ):
            self.assertFalse(migrate._is_plain_read(text), text)

    def test_a_composed_statement_is_treated_as_a_write(self):
        self.assertFalse(migrate._is_plain_read(psycopg.sql.SQL("SELECT 1")))


def _statements(spy):
    return [str(call.args[0]) for call in spy.call_args_list]


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SavepointTests(unittest.TestCase):
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

    def _spy(self):
        spy = mock.Mock(wraps=self.conn.execute)
        patcher = mock.patch.object(self.conn, "execute", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return spy

    def test_a_read_is_sent_on_its_own(self):
        migrate.fetch_one(self.conn, "SELECT 1 AS one")  # opens the transaction
        spy = self._spy()
        self.assertEqual(migrate.fetch_one(self.conn, "SELECT 2 AS two"), {"two": 2})
        self.assertEqual(migrate.fetch_all(self.conn, "SELECT 3 AS three"), [{"three": 3}])
        self.assertEqual(_statements(spy), ["SELECT 2 AS two", "SELECT 3 AS three"])

    def test_a_read_still_opens_the_transaction(self):
        self.assertEqual(self.conn.info.transaction_status, TransactionStatus.IDLE)
        migrate.fetch_one(self.conn, "SELECT 1 AS one")
        self.assertEqual(self.conn.info.transaction_status, TransactionStatus.INTRANS)

    def test_a_write_still_runs_under_a_savepoint(self):
        migrate.fetch_one(self.conn, "SELECT 1 AS one")
        spy = self._spy()
        migrate.execute(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('sp_one', 'sp_one', 'SPONE1')",
        )
        sent = _statements(spy)
        self.assertEqual(len(sent), 3)
        self.assertIn("SAVEPOINT", sent[0])
        self.assertIn("INSERT INTO accounts", sent[1])
        self.assertIn("RELEASE SAVEPOINT", sent[2])

    def test_a_refused_write_leaves_the_transaction_usable(self):
        insert = (
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('sp_two', 'sp_two', %s)"
        )
        migrate.execute(self.conn, insert, ("SPTWO1",))
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, insert, ("SPTWO2",))  # the name is taken
        # the first row is still there and the transaction still works
        row = migrate.fetch_one(
            self.conn, "SELECT count(*) AS n FROM accounts WHERE username_lower = 'sp_two'"
        )
        self.assertEqual(row["n"], 1)

    def test_a_with_statement_runs_under_a_savepoint(self):
        migrate.fetch_one(self.conn, "SELECT 1 AS one")
        spy = self._spy()
        migrate.fetch_all(self.conn, "WITH x AS (SELECT 1 AS one) SELECT one FROM x")
        self.assertIn("SAVEPOINT", _statements(spy)[0])

    def test_a_read_that_fails_ends_the_transaction(self):
        migrate.fetch_one(self.conn, "SELECT 1 AS one")
        with self.assertRaises(psycopg.Error):
            migrate.fetch_one(self.conn, "SELECT * FROM no_such_table_here")
        self.assertEqual(self.conn.info.transaction_status, TransactionStatus.INERROR)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AnswerRequestCostTests(unittest.TestCase):
    """One Ranked answer is the request a player waits on. Every statement
    is a round trip, so the count is held to a ceiling here."""

    CEILING = 35

    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        conn = migrate.connect(self.conninfo)
        self.addCleanup(conn.close)
        migrate.execute(
            conn, "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'cost-test')"
        )
        conn.commit()
        self.client = TestClient(create_app(), headers=BROWSER)
        reg = self.client.post("/api/auth/register", json={"username": "cost_player"})
        self.client.post("/api/auth/login", json={"username": "cost_player", "login_id": reg.json()["login_id"]})
        started = self.client.post("/api/ranked/attempts").json()
        self.attempt = started["attempt_id"]
        self.client.headers["X-Attempt-Capability"] = started["capability"]

    def test_an_answer_stays_under_the_statement_ceiling(self):
        question = self.client.get(f"/api/ranked/attempts/{self.attempt}/current").json()
        sent = []
        real = psycopg.Cursor.execute

        def counting(cursor, query, *args, **kwargs):
            sent.append(str(query))
            return real(cursor, query, *args, **kwargs)

        with mock.patch.object(psycopg.Cursor, "execute", counting):
            answer = self.client.post(
                f"/api/ranked/attempts/{self.attempt}/answer",
                json={"seq": question["seq"], "choice": question["options"][0]},
            )
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertLessEqual(
            len(sent), self.CEILING,
            f"{len(sent)} statements for one answer; the ceiling is {self.CEILING}",
        )


if __name__ == "__main__":
    unittest.main()
