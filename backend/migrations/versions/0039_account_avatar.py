"""The profile icon a player chose (issue #272).

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-23

One nullable column on ``accounts``. It holds a key from
``backend.auth.avatars``, never the emoji and never anything the player
typed, so the width is small on purpose: a value that does not fit was never
one of ours.

NULL means the player has never chosen. That is a real state, not a missing
one: the screens fall back to the initial letter they already show, so
nobody is given an icon they did not pick, and ten players who never chose
do not all appear as the same animal.

The allowed list is not a CHECK constraint. It is expected to change when
the owner approves different icons, and a list of fifteen words would then
need a migration to edit a sentence; ``avatars.is_allowed`` is the one gate,
and the route refuses anything else before it reaches here.

A column on an existing table needs no new GRANT for the runtime role: the
grant that covers ``accounts`` covers its columns.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039"
down_revision: Union[str, Sequence[str], None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE accounts ADD COLUMN avatar varchar(16) NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS avatar")
