"""When this session last re-entered its login ID.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-15

The settled design asks for recent login-ID reauthentication before the
owner's eligibility, recovery and prize actions: "re-enter login ID /
equivalent short-lived reauth bound to the session ... within five
minutes". Account deletion already does this by asking for the login ID in
the same request. The owner's actions come in sequences -- approve three
sorters, hand over a recovery -- so typing the login ID into every one of
them would teach the owner to type it without reading.

So the proof is recorded on the **session**, not the account: a stolen
cookie on another device starts with nothing, and a reauthentication on
the owner's phone does not unlock their laptop. It is a timestamp and
nothing else; the login ID itself is never stored, here or anywhere.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, Sequence[str], None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN reauthenticated_at timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS reauthenticated_at")
