"""Offensive usernames are refused (issue #515).

No test here spells a blocked word: they are read from the encoded list,
so the repository never prints them.
"""
import re
import unittest

from fastapi.testclient import TestClient

from backend.auth import blocked_names
from backend.auth.username_filter import is_blocked
from backend.db import migrate, pool, settings
from backend.main import create_app

BROWSER = {"User-Agent": "test/1.0", "Origin": "http://testserver"}

_TO_DIGIT = str.maketrans({"o": "0", "e": "3", "a": "4", "s": "5", "t": "7", "i": "1"})

# Real first names, surnames and handles, English and Spanish, chosen
# because a careless filter refuses them (a blocked fragment sits inside).
ORDINARY = [
    "maria_sorter", "lucia_sorter", "dock_owl", "jose", "pedro", "kike_r",
    "cassandra", "dickson", "hancock", "glasscock", "scunthorpe", "sussex",
    "essex", "basset", "titan", "constitution", "hoekstra", "therapist_amy",
    "computadora", "reputation", "vergara", "fukuda", "torpedo", "speedo",
    "pajaro", "cocktail_bar", "shiitake", "pitbull", "killian",
    "analisa", "sexton", "manuel_88", "player1988", "rosa_negrete",
    "concepcion", "conor", "culotta", "tito", "papito",
]


class FilterTests(unittest.TestCase):
    def test_the_lists_are_loaded(self):
        self.assertGreater(len(blocked_names.ANYWHERE), 20)
        self.assertGreater(len(blocked_names.WHOLE_WORD), 20)
        for word in blocked_names.ANYWHERE | blocked_names.WHOLE_WORD:
            self.assertRegex(word, r"^[a-z]+$")

    def test_every_word_is_refused_as_the_whole_name(self):
        for word in blocked_names.ANYWHERE | blocked_names.WHOLE_WORD:
            with self.subTest(word=len(word)):
                self.assertTrue(is_blocked(word))
                self.assertTrue(is_blocked(word.upper()))

    def test_anywhere_words_are_refused_inside_a_name(self):
        for word in blocked_names.ANYWHERE:
            with self.subTest(word=len(word)):
                self.assertTrue(is_blocked(f"xx{word}yy"))
                self.assertTrue(is_blocked(f"{word}_2026"))

    def test_whole_words_are_refused_as_a_part_of_the_name(self):
        for word in blocked_names.WHOLE_WORD:
            with self.subTest(word=len(word)):
                self.assertTrue(is_blocked(f"the_{word}_9"))
                self.assertTrue(is_blocked(f"{word}123"))

    def test_look_alike_spellings_are_refused(self):
        for word in blocked_names.ANYWHERE | blocked_names.WHOLE_WORD:
            with self.subTest(word=len(word)):
                digits = word.translate(_TO_DIGIT)
                if any(c.isalpha() for c in digits):
                    self.assertTrue(is_blocked(digits), "digits for letters")
                self.assertTrue(is_blocked("_".join(word)), "underscores between letters")
                if len(re.sub(r"(.)\1+", r"\1", word)) >= 4:
                    self.assertTrue(is_blocked("".join(c * 3 for c in word)), "stretched letters")

    def test_a_hate_number_is_refused(self):
        self.assertTrue(is_blocked("sorter1488"))

    def test_ordinary_names_pass(self):
        for name in ORDINARY:
            with self.subTest(name=name):
                self.assertFalse(is_blocked(name))

    def test_the_allow_list_passes(self):
        for name in blocked_names.ALLOW:
            self.assertFalse(is_blocked(name))


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SignUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        pool.close_pool()
        self.addCleanup(pool.close_pool)
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.app = create_app()
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)

    def _register(self, username):
        return TestClient(self.app, headers=BROWSER).post(
            "/api/auth/register", json={"username": username}
        )

    def _blocked_name(self):
        return "sorter_" + sorted(blocked_names.WHOLE_WORD)[0]

    def test_a_blocked_name_is_refused_and_nothing_is_written(self):
        res = self._register(self._blocked_name())
        self.assertEqual(res.status_code, 422)
        self.assertEqual(
            res.json()["detail"], "That username isn't allowed. Please choose another."
        )
        count = migrate.fetch_one(self.conn, "SELECT COUNT(*) AS n FROM accounts")["n"]
        self.assertEqual(count, 0)

    def test_an_ordinary_name_still_signs_up(self):
        self.assertEqual(self._register("maria_sorter").status_code, 200)

    def test_the_owner_list_flags_an_older_account_with_a_blocked_name(self):
        owner = TestClient(self.app, headers=BROWSER)
        reg = owner.post("/api/auth/register", json={"username": "the_owner"}).json()
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = true WHERE id = %s", (reg["account_id"],)
        )
        # made before the filter existed: written straight to the table
        migrate.execute(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, 'OLD001')",
            (self._blocked_name(), self._blocked_name().lower()),
        )
        self.conn.commit()
        login = owner.post(
            "/api/auth/login", json={"username": "the_owner", "login_id": reg["login_id"]}
        )
        self.assertEqual(login.status_code, 200, login.text)
        rows = owner.get("/api/ranked/owner/accounts").json()["accounts"]
        flags = {row["username"]: row["name_not_allowed"] for row in rows}
        self.assertTrue(flags[self._blocked_name()])
        self.assertFalse(flags["the_owner"])


if __name__ == "__main__":
    unittest.main()
