import unittest

from backend.auth.settings import AuthSettings


class AuthSettingsTests(unittest.TestCase):
    def test_auth_settings_loads_from_env(self):
        settings = AuthSettings()
        self.assertGreaterEqual(settings.argon2_memory_cost, 65536)
        self.assertEqual(settings.login_id_total_groups, 4)
        self.assertEqual(settings.login_id_group_size, 4)
        self.assertEqual(settings.login_id_alphabet, "0123456789ABCDEFGHJKMNPQRSTVWXYZ")


if __name__ == "__main__":
    unittest.main()
