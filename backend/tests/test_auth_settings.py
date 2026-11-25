import unittest

from backend.auth.settings import AuthSettings


class AuthSettingsTests(unittest.TestCase):
    # The Argon2 cost assertion that used to stand here read the settings
    # in force, which this suite now lowers on purpose so that hundreds of
    # database tests stop paying ~95ms each to re-prove that a hash is
    # expensive. It did not move because it was inconvenient: read that
    # way, it would pass at any strength the environment happened to set.
    # test_auth_cost_parameters.py asserts the same thing against the
    # defaults declared on the class -- what a deployment actually gets --
    # and covers time_cost and parallelism, which this never did.
    def test_auth_settings_loads_from_env(self):
        settings = AuthSettings()
        self.assertGreater(settings.session_ttl_seconds, 0)


if __name__ == "__main__":
    unittest.main()
