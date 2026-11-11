"""Alembic migration environment for the scratch test database.

The connection info is never hardcoded here: the DSN comes from the
environment via ``backend.db.settings`` unless a programmatic caller
(a test or ``backend.db.migrate``) provides a live connection through
``config.attributes["connection"]``.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

import psycopg
from alembic import context
from sqlalchemy import create_engine

# Make the backend package importable regardless of the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.db import settings  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = None


def _connect(conninfo: str):
    """Build a psycopg3-backed SQLAlchemy engine for *conninfo*."""
    return create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(conninfo))


def run_migrations_offline() -> None:
    """Configure the context with just a URL; no live DBAPI needed."""
    context.configure(
        url=settings.test_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations over a live psycopg3 connection."""
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        connectable = _connect(settings.test_database_url())

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
