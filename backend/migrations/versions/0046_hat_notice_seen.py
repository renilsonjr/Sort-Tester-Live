"""The approved player's hat notice is shown once (issue #517).

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-28

When the owner approves a sorter for the hat, the player sees a notice
the next time they open Home, once, on any device. The "seen" lives on
the approval row itself: a re-approval is a new row, so it shows again,
and a withdrawal deletes the row, so an unseen notice goes with it.

Approvals recorded before this migration start unseen on purpose: those
players were never told either.

No new table, so no GRANT: the runtime role already holds
`participant_links`. Check `has_column_privilege` on the new column
before the image swap all the same.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0046"
down_revision: Union[str, Sequence[str], None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE participant_links ADD COLUMN notice_seen_at timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE participant_links DROP COLUMN IF EXISTS notice_seen_at")
