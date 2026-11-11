"""Programmatic Alembic drivers for the unittest scratch database.

Every function takes an explicit conninfo so no DSN is ever hardcoded;
callers supply the URL from ``backend.db.settings``. Alembic's command
API runs against a live psycopg3 connection handed to ``env.py`` through
``config.attributes["connection"]``.
"""
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from backend.db import settings

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_INI_PATH = _BACKEND_DIR / "migrations.ini"


def _alembic_config(conninfo: str) -> Config:
    """Build an Alembic config wired to a psycopg3 connection for *conninfo*."""
    config = Config(str(_INI_PATH))
    config.attributes["connection"] = create_engine(
        "postgresql+psycopg://",
        creator=lambda: psycopg.connect(conninfo),
    )
    return config


def upgrade_to_head(conninfo: str) -> None:
    """Migrate the database at *conninfo* to the latest revision."""
    config = _alembic_config(conninfo)
    try:
        command.upgrade(config, "head")
    finally:
        config.attributes["connection"].dispose()


def downgrade_all(conninfo: str) -> None:
    """Downgrade the database at *conninfo* past the first revision."""
    config = _alembic_config(conninfo)
    try:
        command.downgrade(config, "base")
    finally:
        config.attributes["connection"].dispose()


def current_revision(conninfo: str) -> str | None:
    """Return the applied Alembic revision, or None before the first one."""
    with psycopg.connect(conninfo) as conn:
        applied = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'alembic_version'
            """
        ).fetchone()
        if not applied:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None


def table_exists(conninfo: str, name: str) -> bool:
    """Return True when *name* is a table in the public schema."""
    with psycopg.connect(conninfo) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (name,),
        ).fetchone()
        return row is not None


def _url_database(conninfo: str) -> str:
    """Return the effective database selected by PostgreSQL *conninfo*."""
    try:
        parameters = conninfo_to_dict(conninfo)
    except (psycopg.Error, ValueError):
        raise settings.DatabaseConfigError(
            "admin conninfo must be valid PostgreSQL conninfo."
        ) from None
    return parameters.get("dbname") or ""


def recreate_scratch_database(admin_conninfo: str, name: str) -> None:
    """Drop (forcing open connections) and recreate the database *name*.

    *admin_conninfo* must point at the same server but a maintenance
    database such as ``postgres``. CREATE DATABASE cannot run inside a
    transaction, so the admin connection is opened in autocommit mode.

    Raises :class:`~backend.db.settings.DatabaseConfigError` when *name*
    is not the unittest scratch database or when *admin_conninfo* does
    not point at the maintenance database. Both guards are checked
    before any network I/O.
    """
    if name != settings.SCRATCH_DB_NAME:
        raise settings.DatabaseConfigError(
            f"recreate_scratch_database only manages {settings.SCRATCH_DB_NAME}; "
            f"refusing to drop/recreate {name!r}."
        )
    conninfo_database = _url_database(admin_conninfo)
    if conninfo_database != settings.MAINTENANCE_DATABASE:
        raise settings.DatabaseConfigError(
            "admin conninfo must resolve to the maintenance database "
            f"{settings.MAINTENANCE_DATABASE!r} (as settings.admin_url() "
            "produces) so the scratch database is never the connection target."
        )
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
