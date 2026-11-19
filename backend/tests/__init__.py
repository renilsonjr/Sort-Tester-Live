"""Suite-wide defaults, applied before any test module is imported.

Argon2 is slow on purpose. At the shipped parameters one hash costs
about 98ms and one verification about 92ms, and most of this suite's
748 database tests register or sign in at least once. Measured on the
heaviest file, that is 13 of its 82 seconds; across the suite it is
roughly a minute spent re-proving that a password hash is expensive.

Lowering the cost here lets those tests exercise the authentication
code instead of the hash function. It does not weaken anything that
ships: production reads the defaults declared on ``AuthSettings``, and
``test_auth_cost_parameters.py`` asserts those stay at or above the
OWASP minimum, reading the declared defaults rather than the running
settings so the variables set below cannot make it pass.

``setdefault``, so a caller that wants the real parameters can still
export its own and have them honoured.
"""
import os

os.environ.setdefault("SORT_TESTER_ARGON2_TIME_COST", "1")
os.environ.setdefault("SORT_TESTER_ARGON2_MEMORY_COST", "8192")
