"""The hosted app's cookie switch comes from the environment (issue #41).

`SORT_TESTER_COOKIE_SECURE` decides whether the session cookie is marked
`Secure`. It must be on wherever the app is served over HTTPS, and off for
plain-HTTP local development, so the value has to come from the
environment rather than from a default nobody changes. The cookie is
actually issued with these flags in the app-image workflow, against a real
container and database.
"""
import os
import unittest
from unittest.mock import patch

from backend.auth.settings import get_auth_settings


class CookieSecureSettingTests(unittest.TestCase):
    def setting(self, value=None):
        environment = {} if value is None else {"SORT_TESTER_COOKIE_SECURE": value}
        with patch.dict(os.environ, environment, clear=True):
            return get_auth_settings().cookie_secure

    def test_off_by_default_for_plain_http_development(self):
        self.assertFalse(self.setting())

    def test_turned_on_by_the_environment(self):
        for value in ("true", "True", "1", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(self.setting(value))

    def test_turned_off_by_the_environment(self):
        for value in ("false", "False", "0", "no", "off"):
            with self.subTest(value=value):
                self.assertFalse(self.setting(value))


if __name__ == "__main__":
    unittest.main()
