"""Review closure on connection flags.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-13

An authorized reviewer closes a connection flag as network instability or as
insufficient evidence (decision record, Decision 8); leaving it open is not
closing. Closure changes no points or access. A closed flag and its detailed
connection events are deleted fifteen days after closure.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE connection_flags
            ADD COLUMN closed_at timestamptz NULL,
            ADD COLUMN closed_outcome varchar(32) NULL
                CHECK (closed_outcome IN ('network_instability', 'insufficient_evidence')),
            ADD CONSTRAINT connection_flags_closed_together
                CHECK ((closed_at IS NULL) = (closed_outcome IS NULL))
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE connection_flags DROP CONSTRAINT IF EXISTS connection_flags_closed_together"
    )
    op.execute("ALTER TABLE connection_flags DROP COLUMN IF EXISTS closed_outcome")
    op.execute("ALTER TABLE connection_flags DROP COLUMN IF EXISTS closed_at")
