"""Pending-purge deletion marker on accounts.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12

Deletion is pending-purge (owner decision, 2026-11-12): confirmed deletion
first sets accounts.deleted_at to mark the account inaccessible while the
background purge removes owned data (and, per #13, provider/backup copies);
only after the purge is verified is the row hard deleted, whose cascade clears
anything still attached. The season-ineligibility marker survives because
season_markers (0004) has no account foreign key.

The deleted_at column itself is owned by 0002; this migration only gives the
pending state a worker index and an integrity check. It does not implement the
deletion flow, session revocation, or purge orchestration (engine/service: #47).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The background purge worker enumerates accounts awaiting purge with
    # `WHERE deleted_at IS NOT NULL`; this partial index serves exactly that
    # query and keeps the (overwhelmingly larger) set of active accounts out
    # of the index entirely.
    op.execute(
        """
        CREATE INDEX accounts_pending_purge
            ON accounts (deleted_at)
            WHERE deleted_at IS NOT NULL
        """
    )
    # A pending timestamp cannot predate the account it marks.
    op.execute(
        """
        ALTER TABLE accounts
            ADD CONSTRAINT accounts_deleted_at_after_created
            CHECK (deleted_at IS NULL OR deleted_at >= created_at)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE accounts DROP CONSTRAINT IF EXISTS accounts_deleted_at_after_created"
    )
    op.execute("DROP INDEX IF EXISTS accounts_pending_purge")
