"""Connection events for ranked attempts.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-12

The attempt engine (#8) declares a connection loss three seconds after the
last heartbeat, accepts a return until the fifteen-second grace deadline, and
ends the attempt as a disconnect at that deadline. This table records those
moments so the connection review feature (#25) can read them without the
engine depending on it.

One loss per uninterrupted interruption: a loss's occurred_at is derived from
the stored heartbeat, so noticing the same silence again yields the same row,
which the unique key discards. Rows hold only an attempt, a kind and a time,
and are removed with the attempt (and so with the account).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE attempt_connection_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            attempt_id uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
            kind varchar(16) NOT NULL
                CHECK (kind IN ('loss', 'recovery', 'expiry')),
            occurred_at timestamptz NOT NULL,
            UNIQUE (attempt_id, kind, occurred_at)
        )
        """
    )


def downgrade() -> None:
    op.drop_table("attempt_connection_events")
