"""A Versus duel belongs to a season, so its leaderboard can.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-27

The Versus leaderboard starts over with each season, like the Handler's
(#417). The season is stamped on the match when it starts: the one
admitting Ranked play at that moment, the same answer Ranked itself uses.
A duel played between seasons carries none and counts on no board.

No new table, so no GRANT: the runtime role already holds
`versus_matches`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0045"
down_revision: Union[str, Sequence[str], None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE versus_matches ADD COLUMN season_id uuid REFERENCES seasons(id)"
    )
    op.execute(
        "CREATE INDEX versus_matches_season ON versus_matches (season_id)"
        " WHERE state = 'finished'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS versus_matches_season")
    op.execute("ALTER TABLE versus_matches DROP COLUMN IF EXISTS season_id")
