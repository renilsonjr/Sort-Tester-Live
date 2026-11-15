"""Who plays each round, what each player scored, and where each ended up.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-15

Three things the closing of a round needs to write down:

* **Round players.** A later round is played only by the players still
  tied after the one before it (settled: preserve valid prior relative
  order), so the group's membership is no longer who may play. Each round
  names its own players. Tie-breaks were introduced today and no round has
  been played anywhere, so there is nothing to backfill.
* **Round results.** At the deadline every player of the round gets one
  line: completed with a score of 0 to 5, incomplete, or no-show. A
  completed 0/5 is still completed (settled), so the score is kept
  separately from the outcome. Released to players only after the deadline.
* **Placements.** Where each member of the group ended up: a hat, no hat,
  excluded (Challenger), or waiting for the owner's selection. One row per
  member and group, written once the group's question about them is
  settled; a player still being decided by a later round has no row yet.

``round_deadline`` joins the attempt outcomes for a tie-break attempt that
was still running when its round's 24 hours ran out. The existing outcomes
all mean something else (``season_close`` is the season's own window), and
reusing one would make a later reader misread what happened.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, Sequence[str], None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE attempts DROP CONSTRAINT attempts_final_outcome_check")
    op.execute(
        "ALTER TABLE attempts ADD CONSTRAINT attempts_final_outcome_check"
        " CHECK (final_outcome IN ('completed', 'quit', 'disconnect', 'season_close',"
        " 'launch_reset', 'outage_void', 'round_deadline'))"
    )
    # A later round can decide fewer hats than the group started with: three
    # tied for two hats, one wins outright in round 1, the other two play
    # round 2 for the one hat left. The round carries its own count.
    op.execute("ALTER TABLE tiebreak_rounds ADD COLUMN hats smallint")
    op.execute("UPDATE tiebreak_rounds r SET hats = g.hats_available"
               " FROM tiebreak_groups g WHERE g.id = r.group_id")
    op.execute("ALTER TABLE tiebreak_rounds ALTER COLUMN hats SET NOT NULL")
    op.execute(
        "ALTER TABLE tiebreak_rounds ADD CONSTRAINT tiebreak_rounds_hats_check"
        " CHECK (hats BETWEEN 1 AND 3)"
    )
    op.execute(
        """
        CREATE TABLE tiebreak_round_players (
            round_id uuid NOT NULL REFERENCES tiebreak_rounds(id) ON DELETE CASCADE,
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            PRIMARY KEY (round_id, account_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tiebreak_round_results (
            round_id uuid NOT NULL REFERENCES tiebreak_rounds(id) ON DELETE CASCADE,
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            outcome varchar(16) NOT NULL,
            score smallint,
            PRIMARY KEY (round_id, account_id),
            CONSTRAINT tiebreak_round_results_outcome_check
                CHECK (outcome IN ('completed', 'incomplete', 'no_show')),
            CONSTRAINT tiebreak_round_results_score_only_when_completed CHECK (
                (outcome = 'completed' AND score BETWEEN 0 AND 5)
                OR (outcome <> 'completed' AND score IS NULL)
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tiebreak_placements (
            group_id uuid NOT NULL REFERENCES tiebreak_groups(id) ON DELETE CASCADE,
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            status varchar(16) NOT NULL,
            decided_in_round smallint NOT NULL,
            PRIMARY KEY (group_id, account_id),
            CONSTRAINT tiebreak_placements_status_check
                CHECK (status IN ('hat', 'no_hat', 'excluded', 'owner_selection'))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tiebreak_placements")
    op.execute("DROP TABLE IF EXISTS tiebreak_round_results")
    op.execute("DROP TABLE IF EXISTS tiebreak_round_players")
    op.execute("ALTER TABLE tiebreak_rounds DROP COLUMN IF EXISTS hats")
    op.execute("ALTER TABLE attempts DROP CONSTRAINT attempts_final_outcome_check")
    op.execute(
        "ALTER TABLE attempts ADD CONSTRAINT attempts_final_outcome_check"
        " CHECK (final_outcome IN ('completed', 'quit', 'disconnect', 'season_close',"
        " 'launch_reset', 'outage_void'))"
    )
