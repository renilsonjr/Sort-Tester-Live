"""Confirmed outages and private connection review flags.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-13

Connection review flags (#25, decision record Decision 7) mark attempts whose
connection events contain a run of four close losses. A flag is a private
instability signal for review: it never changes points or access.

confirmed_outages records server-wide outages the owner confirmed, so losses
the server caused never count toward a flag. One flag per attempt: the primary
key on connection_flags.attempt_id is that rule, and the cascade removes a
flag with its attempt, and so with the account.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE confirmed_outages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            starts_at timestamptz NOT NULL,
            ends_at timestamptz NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(),
            CHECK (ends_at >= starts_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE connection_flags (
            attempt_id uuid PRIMARY KEY REFERENCES attempts(id) ON DELETE CASCADE,
            first_loss_at timestamptz NOT NULL,
            last_loss_at timestamptz NOT NULL,
            flagged_at timestamptz NOT NULL,
            CHECK (last_loss_at >= first_loss_at)
        )
        """
    )


def downgrade() -> None:
    op.drop_table("connection_flags")
    op.drop_table("confirmed_outages")
