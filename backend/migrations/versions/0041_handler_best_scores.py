"""The Handler mini-game's best score, one per account per mode (#396).

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-26

This is the ONLY thing the first Handler release stores. The spec's
persistence boundary is deliberate: mini-game results never reach Ranked
points, prizes, badges, the leaderboard or the Shift log, and nothing here
records a round, an attempt or a timestamp. A leaderboard is a later stage
and waits on an owner decision about showing real employee names.

Four modes, named here rather than left open, so a typo cannot quietly
create a fifth scoreboard nobody can see. A score is a whole number and
never negative, which is rule 17 written where the database can enforce it.

**This table needs a GRANT to the runtime role before the image that reads
it is deployed.** A new table does not inherit the privileges of the ones
beside it, so the app would start and then fail on the first read. Run the
grant against the application database first, then swap the image:

    GRANT SELECT, INSERT, UPDATE ON handler_best_scores TO "<app-role>";

Deleting an account takes its scores with it, like every other table that
references accounts.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: Union[str, Sequence[str], None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODES = ("easy", "medium", "hard", "expert")


def upgrade() -> None:
    modes = ", ".join(f"'{mode}'" for mode in MODES)
    op.execute(
        f"""
        CREATE TABLE handler_best_scores (
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            mode text NOT NULL CHECK (mode IN ({modes})),
            score integer NOT NULL CHECK (score >= 0),
            PRIMARY KEY (account_id, mode)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS handler_best_scores")
