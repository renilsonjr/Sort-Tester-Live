"""The Argon2 parameters that ship must stay strong.

This suite lowers the Argon2 cost through the environment (see
``backend/tests/__init__.py``) so that 748 database tests do not each
pay about 95ms to re-prove that a hash is expensive. That is only safe
while the *declared* defaults -- what a deployment uses when nothing
sets the variables -- remain strong.

So these tests read ``AuthSettings.model_fields``, the defaults written
in the class, rather than ``get_auth_settings()``, which the suite's own
environment has already lowered. A test that read the running settings
would pass at any strength and guard nothing.
"""
import os
import unittest
from unittest import mock

from backend.auth.settings import AuthSettings, get_auth_settings

# OWASP Password Storage Cheat Sheet, Argon2id: m=19456 (19 MiB), t=2, p=1.
OWASP_MINIMUM_MEMORY_KIB = 19456
OWASP_MINIMUM_TIME_COST = 2
OWASP_MINIMUM_PARALLELISM = 1


def declared_default(field: str):
    """The default written on the class, not the value in force here."""
    return AuthSettings.model_fields[field].default


class Argon2ShippedCostTests(unittest.TestCase):
    def test_memory_cost_meets_the_owasp_minimum(self):
        self.assertGreaterEqual(
            declared_default("argon2_memory_cost"), OWASP_MINIMUM_MEMORY_KIB
        )

    def test_time_cost_meets_the_owasp_minimum(self):
        self.assertGreaterEqual(
            declared_default("argon2_time_cost"), OWASP_MINIMUM_TIME_COST
        )

    def test_parallelism_meets_the_owasp_minimum(self):
        self.assertGreaterEqual(
            declared_default("argon2_parallelism"), OWASP_MINIMUM_PARALLELISM
        )

    def test_a_deployment_setting_nothing_gets_the_strong_parameters(self):
        # The defaults are what an environment without the variables
        # produces. Reading them off the class is only meaningful if the
        # settings object actually falls back to them.
        without_overrides = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SORT_TESTER_ARGON2_")
        }
        with mock.patch.dict(os.environ, without_overrides, clear=True):
            shipped = AuthSettings()
        self.assertEqual(
            shipped.argon2_memory_cost, declared_default("argon2_memory_cost")
        )
        self.assertEqual(
            shipped.argon2_time_cost, declared_default("argon2_time_cost")
        )

    def test_the_suite_lowered_the_cost_without_touching_the_defaults(self):
        # Proves the two halves of the arrangement at once: the tests run
        # cheap, and the figure that ships is untouched by that.
        running = get_auth_settings()
        self.assertLess(running.argon2_memory_cost, OWASP_MINIMUM_MEMORY_KIB)
        self.assertGreaterEqual(
            declared_default("argon2_memory_cost"), OWASP_MINIMUM_MEMORY_KIB
        )


if __name__ == "__main__":
    unittest.main()
