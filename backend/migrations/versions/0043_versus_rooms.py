"""Versus rooms: two players find each other before a duel.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-27

A room is the lobby of one duel and nothing more: who opened it, which
mini-game it will run, who joined, and when it stops waiting. The duel
itself (questions, scores, result) is a later slice and a later table;
nothing here touches Ranked points, prizes, badges or the Shift log.

One code can only belong to one open room, but a closed room keeps its
code in the row for the record, so the uniqueness is partial: among rooms
still open. Deleting an account closes the story the usual way: rooms it
hosted go with it, and a room it had joined merely loses its guest.

**This table needs a GRANT to the runtime role before the image that reads
it is deployed.** A new table does not inherit the privileges of the ones
beside it, so the app would start and then fail on the first read. Run the
grant against the application database first, then swap the image:

    GRANT SELECT, INSERT, UPDATE, DELETE ON versus_rooms TO "<app-role>";
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: Union[str, Sequence[str], None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GAMES = ("quiz", "handler")
STATES = ("waiting", "full", "closed")


def upgrade() -> None:
    games = ", ".join(f"'{game}'" for game in GAMES)
    states = ", ".join(f"'{state}'" for state in STATES)
    op.execute(
        f"""
        CREATE TABLE versus_rooms (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code text NOT NULL,
            game text NOT NULL CHECK (game IN ({games})),
            host_account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            guest_account_id uuid REFERENCES accounts(id) ON DELETE SET NULL,
            state text NOT NULL DEFAULT 'waiting' CHECK (state IN ({states})),
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            CHECK (guest_account_id IS DISTINCT FROM host_account_id)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX versus_rooms_open_code"
        " ON versus_rooms (code) WHERE state <> 'closed'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS versus_rooms")
