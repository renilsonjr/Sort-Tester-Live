"""The Handler best score belongs to a season (#417).

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-26

Owner decision, 2026-11-26: the Handler leaderboard starts over with each
season, and so does the personal best a player sees. Nothing is erased to
make that happen. A score is stored against the season it was made in, and
a new season simply has no rows yet, so every board and every personal best
opens empty. The earlier seasons' rows stay where they are.

No new table: this adds a column to the one 0041 created. Rows that already
exist were made before seasons applied to Handler, and they are given to the
newest season, which is the one they were played in.

**The runtime role needs DELETE on this table as well, before the image
that uses it is deployed.** Deleting an account now removes its Handler
scores outright instead of leaving them hidden behind the account's
deletion mark, and that is a DELETE the app runs. The full grant is now:

    GRANT SELECT, INSERT, UPDATE, DELETE ON handler_best_scores TO "<app-role>";

Run it against the application database first, then swap the image.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0042"
down_revision: Union[str, Sequence[str], None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE handler_best_scores"
        " ADD COLUMN season_id uuid REFERENCES seasons(id) ON DELETE CASCADE"
    )
    op.execute(
        "UPDATE handler_best_scores SET season_id ="
        " (SELECT id FROM seasons ORDER BY opened_at DESC LIMIT 1)"
    )
    # A score with no season to belong to cannot be shown on any board.
    op.execute("DELETE FROM handler_best_scores WHERE season_id IS NULL")
    op.execute("ALTER TABLE handler_best_scores ALTER COLUMN season_id SET NOT NULL")
    op.execute("ALTER TABLE handler_best_scores DROP CONSTRAINT handler_best_scores_pkey")
    op.execute("ALTER TABLE handler_best_scores ADD PRIMARY KEY (season_id, account_id, mode)")
    # The board is read as "this season, this mode, highest first".
    op.execute(
        "CREATE INDEX handler_best_scores_board"
        " ON handler_best_scores (season_id, mode, score DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS handler_best_scores_board")
    # One row per account and mode again: keep each one's highest.
    op.execute(
        """
        DELETE FROM handler_best_scores h USING handler_best_scores other
        WHERE h.account_id = other.account_id AND h.mode = other.mode
          AND (h.score, h.season_id::text) < (other.score, other.season_id::text)
        """
    )
    op.execute("ALTER TABLE handler_best_scores DROP CONSTRAINT handler_best_scores_pkey")
    op.execute("ALTER TABLE handler_best_scores ADD PRIMARY KEY (account_id, mode)")
    op.execute("ALTER TABLE handler_best_scores DROP COLUMN season_id")
