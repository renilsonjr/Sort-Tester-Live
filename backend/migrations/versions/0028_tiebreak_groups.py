"""Prize tie-break groups and their rounds (issue #24, slice 1).

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-15

A tie-break exists only when more players are competing for the three
hats than there are hats: the owner's rule of 2026-11-15 is that players
tied inside the top three simply share their place, and a quiz runs only
when the tie crosses the third-place cut. So a group records the tied
score, the players at it, and how many hats are left for them once the
players strictly above have taken theirs.

A group plays rounds. Round 1's deadline is the season's **scheduled**
close plus 24 hours (settled Decisions 9-10), not the moment the season
happened to freeze. Later rounds and outage restarts arrive in later
slices; the table already allows them so the first slice does not have to
be undone.

One season-close group per season at most: detection runs inside the same
transaction as the freeze, and the partial unique index makes running it
twice a no-op instead of a duplicate. Replacement groups, after a
withdrawal or deletion, come with a different reason and are not limited
by it.

Accounts cascade: a deleted player leaves the group. What happens to the
group then -- a backfill, a smaller group, fewer hats -- is a later slice
and is decided by the rules, not by the foreign key.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, Sequence[str], None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tiebreak_groups (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            season_id uuid NOT NULL REFERENCES seasons(id),
            reason varchar(16) NOT NULL,
            tied_points integer NOT NULL,
            hats_available smallint NOT NULL,
            opened_at timestamptz NOT NULL,
            status varchar(24) NOT NULL DEFAULT 'open',
            CONSTRAINT tiebreak_groups_reason_check
                CHECK (reason IN ('season_close', 'replacement')),
            CONSTRAINT tiebreak_groups_status_check
                CHECK (status IN ('open', 'resolved', 'owner_selection')),
            CONSTRAINT tiebreak_groups_hats_check
                CHECK (hats_available BETWEEN 1 AND 3)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX tiebreak_groups_one_season_close"
        " ON tiebreak_groups (season_id) WHERE reason = 'season_close'"
    )
    op.execute(
        """
        CREATE TABLE tiebreak_group_members (
            group_id uuid NOT NULL REFERENCES tiebreak_groups(id) ON DELETE CASCADE,
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, account_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tiebreak_rounds (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id uuid NOT NULL REFERENCES tiebreak_groups(id) ON DELETE CASCADE,
            round_number smallint NOT NULL,
            opened_at timestamptz NOT NULL,
            deadline_at timestamptz NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'open',
            CONSTRAINT tiebreak_rounds_number_check CHECK (round_number BETWEEN 1 AND 5),
            CONSTRAINT tiebreak_rounds_status_check
                CHECK (status IN ('open', 'closed', 'void')),
            CONSTRAINT tiebreak_rounds_deadline_after_open
                CHECK (deadline_at > opened_at)
        )
        """
    )
    # one live round per group and number; a voided round is replaced by a
    # new one with the same number, so void rows are left out of the rule
    op.execute(
        "CREATE UNIQUE INDEX tiebreak_rounds_one_live_per_number"
        " ON tiebreak_rounds (group_id, round_number) WHERE status <> 'void'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tiebreak_rounds")
    op.execute("DROP TABLE IF EXISTS tiebreak_group_members")
    op.execute("DROP TABLE IF EXISTS tiebreak_groups")
