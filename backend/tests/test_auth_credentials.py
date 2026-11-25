import re
import unittest

from backend.auth.credentials import (
    generate_login_id,
    hash_login_id,
    new_lookup_key,
    normalize_login_id,
    verify_login_id,
)
from backend.auth.wordlist import WORDS

WORD_CODE = re.compile(r"^[a-z]{3,8}-[0-9]{2}$")


class CredentialsTests(unittest.TestCase):
    def test_a_new_code_is_one_word_and_two_digits(self):
        for _ in range(200):
            login_id = generate_login_id()
            self.assertRegex(login_id, WORD_CODE)
            self.assertIn(login_id.split("-")[0], WORDS)

    def test_new_codes_spread_over_words_and_endings(self):
        codes = [generate_login_id() for _ in range(2000)]
        words = {c.split("-")[0] for c in codes}
        endings = {c.split("-")[1] for c in codes}
        # 2,000 draws from 2,000 words x 100 endings: anything bunched up
        # here means the draw is not using the whole list.
        self.assertGreater(len(words), 1000)
        self.assertEqual(len(endings), 100)

    def test_generate_and_verify_a_word_code(self):
        login_id = generate_login_id()
        hashed = hash_login_id(login_id)
        self.assertTrue(verify_login_id(login_id, hashed))
        self.assertTrue(verify_login_id(login_id.upper().replace("-", " "), hashed))
        self.assertFalse(verify_login_id("wrong-00", hashed))

    def test_a_code_from_before_still_verifies(self):
        hashed = hash_login_id("ABCD-EFGH-JKMN-PRST")
        self.assertTrue(verify_login_id("abcd efgh jkmn prst", hashed))
        self.assertFalse(verify_login_id("WRNG-WRNG-WRNG-WRNG", hashed))

    def test_word_codes_ignore_case_spaces_and_dashes(self):
        for typed in ("banana-48", "Banana-48", "BANANA48", " banana 48 ", "banana48"):
            self.assertEqual(normalize_login_id(typed), "banana48")

    def test_old_codes_keep_their_rules(self):
        self.assertEqual(normalize_login_id("abcd-efgh-jkmn-prst"), "ABCDEFGHJKMNPRST")
        self.assertEqual(normalize_login_id("  abcd efgh jkmn prst  "), "ABCDEFGHJKMNPRST")

    def test_anything_else_is_refused(self):
        for typed in (
            "",
            "banana",  # no digits
            "banana-4",  # one digit
            "banana-480",  # three digits
            "ab-12",  # word too short
            "elephants-12",  # word too long
            "ban4na-48",
            "ABCD-EFGH-JKLM-NPQO",  # old shape with a letter it never used
            "not a code!!",
        ):
            with self.subTest(typed=typed), self.assertRaises(ValueError):
                normalize_login_id(typed)

    def test_lookup_keys_are_random_and_fit_the_column(self):
        keys = {new_lookup_key() for _ in range(500)}
        self.assertEqual(len(keys), 500)
        self.assertTrue(all(len(k) == 32 for k in keys))


class WordListTests(unittest.TestCase):
    def test_at_least_two_thousand_words(self):
        self.assertGreaterEqual(len(WORDS), 2000)

    def test_no_duplicates(self):
        self.assertEqual(len(set(WORDS)), len(WORDS))

    def test_each_word_is_three_to_eight_lowercase_letters(self):
        for word in WORDS:
            self.assertRegex(word, r"^[a-z]{3,8}$")


if __name__ == "__main__":
    unittest.main()
