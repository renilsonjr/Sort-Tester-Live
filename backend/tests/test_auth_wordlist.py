"""The Quiz Code word list stays clean (issue #516).

No test here spells a removed word: the ones taken out for an offensive
English or Spanish reading are kept ROT13-encoded, so the repository never
prints them.
"""
import codecs
import unittest

from backend.auth import credentials
from backend.auth.username_filter import is_blocked
from backend.auth.wordlist import WORDS

# Taken out in #516: a slur or a slang reading in English or Spanish, or an
# offensive piece that reads badly next to two digits.
_REMOVED = frozenset(
    codecs.decode(word, "rot13")
    for word in (
        "ornire pbpxngbb pbyn penpxre tlcfhz ubr xabo ahg cncnln crnpbpx "
        "enppbba fnhfntr fperj frnjrrq jrrq"
    ).split()
)


class WordListTests(unittest.TestCase):
    def test_the_list_keeps_its_size(self):
        # Decision 14's guessing budget: about 2,000 words times the endings.
        self.assertGreaterEqual(len(WORDS), 2000)

    def test_every_word_is_plain(self):
        self.assertEqual(len(WORDS), len(set(WORDS)), "duplicates")
        for word in WORDS:
            self.assertRegex(word, r"^[a-z]{3,8}$")

    def test_no_word_fails_the_username_filter(self):
        self.assertEqual([len(w) for w in WORDS if is_blocked(w)], [])

    def test_the_removed_words_stay_out(self):
        self.assertEqual(len(_REMOVED & set(WORDS)), 0)


class EndingTests(unittest.TestCase):
    def test_the_excluded_endings_are_never_drawn(self):
        self.assertEqual(len(credentials.CODE_ENDINGS), 97)
        for ending in ("14", "88", "69"):
            self.assertNotIn(ending, credentials.CODE_ENDINGS)

    def test_a_new_code_never_ends_in_one(self):
        for _ in range(3000):
            code = credentials.generate_login_id()
            self.assertRegex(code, r"^[a-z]{3,8}-[0-9]{2}$")
            self.assertNotIn(code[-2:], {"14", "88", "69"})
            self.assertIn(code.split("-")[0], WORDS)


if __name__ == "__main__":
    unittest.main()
