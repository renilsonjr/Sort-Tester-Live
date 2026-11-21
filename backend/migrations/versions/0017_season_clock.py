"""Scheduled end and freeze marker on seasons.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-12

A season ends by the clock (#23, owner decision 2026-11-12): closes_at is the
scheduled end, after which the server admits no new Ranked attempt without
anyone acting. Pre-Season has no scheduled end, so the column is nullable.

frozen_at marks the moment a season's points became final, after its
unfinished attempts were ended and settled. It is set by the season-close
flow, not here.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE seasons
            ADD COLUMN closes_at timestamptz NULL
                CHECK (closes_at IS NULL OR closes_at >= opened_at),
            ADD COLUMN frozen_at timestamptz NULL
                CHECK (frozen_at IS NULL OR frozen_at >= opened_at)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE seasons DROP COLUMN IF EXISTS frozen_at")
    op.execute("ALTER TABLE seasons DROP COLUMN IF EXISTS closes_at")
