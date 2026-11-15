"""The three hat winners of a season, once the prizes are final.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-15

Awarding the hats is more than the per-group placements: a vacancy a
Challenger exclusion leaves is filled from the next eligible player down
(settled Q14 backfill), and a clear points winner never joined a group at
all. ``season_prizes`` is the resolved answer -- the accounts that hold a
hat this season -- written once, when no tie-break round is open and no
owner selection is pending, so the leaderboard has a single, final place
to read winners from rather than piecing them together from groups.

``prizes_final_at`` on the season says the resolution has run and will not
change (no clawback, settled). Fewer than three rows is allowed and means
fewer hats were awarded; zero rows with a final mark means none were.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: Union[str, Sequence[str], None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE seasons ADD COLUMN prizes_final_at timestamptz")
    op.execute(
        """
        CREATE TABLE season_prizes (
            season_id uuid NOT NULL REFERENCES seasons(id),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            PRIMARY KEY (season_id, account_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS season_prizes")
    op.execute("ALTER TABLE seasons DROP COLUMN IF EXISTS prizes_final_at")
