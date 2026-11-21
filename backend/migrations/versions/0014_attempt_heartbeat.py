"""Last-heartbeat timestamp on attempts.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-12

The ranked attempt engine (#8) decides connection loss and the fifteen-second
grace from the last time the page was heard from: loss is declared three
seconds after it, and the grace deadline is fifteen seconds after that. Both
are derived from this stored instant, never from when the server happened to
notice the silence.

The column is nullable so existing rows stay valid; the engine falls back to
started_at when it is NULL.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE attempts ADD COLUMN last_heartbeat_at timestamptz NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE attempts DROP COLUMN IF EXISTS last_heartbeat_at")
