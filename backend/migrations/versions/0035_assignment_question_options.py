"""The four belts each ordinary Ranked or promotion question offers.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-15

Owner decision 2026-11-15 (migration 0033's note): Ranked and tie-break
questions both show four belts, the right one and three drawn from the
others. Migration 0033 did this for a tie-break round's shared questions;
this is the same rule for an ordinary or promotion attempt's own
questions, which are personal to that attempt rather than shared.

Nullable and drawn lazily (``backend.ranked.engine._options_for_assignment``)
for the same reason as 0033: a row written before this column existed
gets its four options drawn and stored the first time its question is
served, rather than by a destructive backfill.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0035"
down_revision: Union[str, Sequence[str], None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE assignment_questions ADD COLUMN options varchar(16)[]"
    )
    # At most four, and at least one. The reviewed bank routes to nine
    # belts, so a real question always offers exactly four; a bank with
    # fewer belts than that offers fewer rather than failing to start a
    # quiz at all (backend.ranked.belt_options.draw_options).
    op.execute(
        "ALTER TABLE assignment_questions"
        " ADD CONSTRAINT assignment_questions_four_options"
        " CHECK (options IS NULL OR array_length(options, 1) BETWEEN 1 AND 4)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE assignment_questions DROP COLUMN IF EXISTS options")
