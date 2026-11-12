import unittest

from backend.auth.credentials import (
    derive_lookup_key,
    generate_login_id,
    hash_login_id,
    normalize_login_id,
    verify_login_id,
)
from backend.auth.settings import AuthSettings


class CredentialsTests(unittest.TestCase):
    def test_generate_and_verify_login_id(self):
        settings = AuthSettings()
        login_id = generate_login_id(settings)
        self.assertEqual(
            len(login_id.replace("-", "")),
            settings.login_id_total_groups * settings.login_id_group_size,
        )
        hashed = hash_login_id(login_id)
        self.assertTrue(verify_login_id(login_id, hashed))
        self.assertFalse(verify_login_id("WRONG-WRONG-WRNG-WRNG", hashed))

    def test_normalize_login_id_strips_dashes_and_whitespace(self):
        self.assertEqual(normalize_login_id("abcd-efgh-jkmn-prst"), "ABCDEFGHJKMNPRST")
        self.assertEqual(normalize_login_id("  abcd efgh jkmn prst  "), "ABCDEFGHJKMNPRST")

    def test_normalize_rejects_ambiguous_characters(self):
        with self.assertRaises(ValueError):
            normalize_login_id("ABCD-EFGH-JKLM-NPQR-I")  # I is not allowed
        with self.assertRaises(ValueError):
            normalize_login_id("ABCD-EFGH-JKLM-NPQO")  # O is not allowed

    def test_different_login_ids_do_not_collide_on_lookup_key(self):
        settings = AuthSettings()
        lookup_keys = set()
        for _ in range(500):
            login_id = generate_login_id(settings)
            lookup_keys.add(derive_lookup_key(login_id))
        self.assertEqual(len(lookup_keys), 500)


if __name__ == "__main__":
    unittest.main()
