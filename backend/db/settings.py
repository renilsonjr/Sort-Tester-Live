"""Environment-only connection settings for test database tooling."""
import os

ENV_VAR = "SORT_TESTER_TEST_DATABASE_URL"
SCRATCH_DB_NAME = "sort_tester_unittest_scratch"
_POSTGRESQL_SCHEME = "postgresql://"


class DatabaseConfigError(Exception):
    """Raised when the test database connection setting is unset or malformed."""


def test_database_url() -> str:
    """Return the test database URL from the environment.

    The URL must be a postgresql conninfo URL whose database is the
    unittest scratch database. An empty query string is tolerated.
    """
    raw = os.environ.get(ENV_VAR, "")
    url = raw.strip()
    if not url:
        raise DatabaseConfigError(
            f"{ENV_VAR} is not set; export it with a postgresql:// URL "
            f"pointing at the {SCRATCH_DB_NAME} database."
        )
    if not url.startswith(_POSTGRESQL_SCHEME):
        raise DatabaseConfigError(
            f"{ENV_VAR} must start with {_POSTGRESQL_SCHEME}; "
            f"got a URL pointing at database {SCRATCH_DB_NAME} instead?"
        )
    path = url[len(_POSTGRESQL_SCHEME):].split("?", 1)[0].rpartition("/")[2].rstrip("/")
    expected_path = SCRATCH_DB_NAME
    if path != expected_path:
        raise DatabaseConfigError(
            f"{ENV_VAR} must point at the {expected_path} database so tooling "
            f"only ever touches {SCRATCH_DB_NAME}."
        )
    return url
