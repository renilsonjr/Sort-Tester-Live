"""Versus matches: the duel itself, scores and the shared draw.

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-27

Three pieces. `versus_matches` is one duel: which game, who plays, the
shared clock and, at the end, the winner. `versus_match_questions` is the
quiz duel's shared draw, the tie-break pattern reused: both players meet
the same questions in the same order, stored as question versions with
their four options, so what was asked can be answered later even after
the bank moves on. `versus_match_players` is each player's half of the
score: where they are, how many points, when they finished.

The boundary holds: nothing here references attempts, balances or
settlements, and no Versus point ever becomes a Ranked point.

**These tables need a GRANT to the runtime role before the image that
reads them is deployed**, like every new table:

    GRANT SELECT, INSERT, UPDATE, DELETE ON versus_matches TO "<app-role>";
    GRANT SELECT, INSERT, UPDATE, DELETE ON versus_match_questions TO "<app-role>";
    GRANT SELECT, INSERT, UPDATE, DELETE ON versus_match_players TO "<app-role>";
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0044"
down_revision: Union[str, Sequence[str], None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GAMES = ("quiz", "handler")
STATES = ("playing", "finished")


def upgrade() -> None:
    games = ", ".join(f"'{game}'" for game in GAMES)
    states = ", ".join(f"'{state}'" for state in STATES)
    op.execute(
        f"""
        CREATE TABLE versus_matches (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            game text NOT NULL CHECK (game IN ({games})),
            state text NOT NULL DEFAULT 'playing' CHECK (state IN ({states})),
            host_account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            guest_account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            seed text,
            question_count integer NOT NULL DEFAULT 0,
            started_at timestamptz NOT NULL,
            ends_at timestamptz NOT NULL,
            finished_at timestamptz,
            winner_account_id uuid REFERENCES accounts(id) ON DELETE SET NULL,
            CHECK (guest_account_id <> host_account_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE versus_match_questions (
            match_id uuid NOT NULL REFERENCES versus_matches(id) ON DELETE CASCADE,
            seq integer NOT NULL,
            question_version_id uuid NOT NULL REFERENCES question_versions(id),
            options varchar(16)[] NOT NULL,
            PRIMARY KEY (match_id, seq)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE versus_match_players (
            match_id uuid NOT NULL REFERENCES versus_matches(id) ON DELETE CASCADE,
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            score integer NOT NULL DEFAULT 0 CHECK (score >= 0),
            seq integer NOT NULL DEFAULT 1,
            correct_count integer NOT NULL DEFAULT 0,
            question_sent_at timestamptz,
            finished_at timestamptz,
            PRIMARY KEY (match_id, account_id)
        )
        """
    )
    # The room points at the match it became, so both waiting screens
    # learn the duel started from the poll they are already making.
    op.execute(
        "ALTER TABLE versus_rooms ADD COLUMN match_id uuid REFERENCES versus_matches(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE versus_rooms DROP COLUMN IF EXISTS match_id")
    op.execute("DROP TABLE IF EXISTS versus_match_players")
    op.execute("DROP TABLE IF EXISTS versus_match_questions")
    op.execute("DROP TABLE IF EXISTS versus_matches")
