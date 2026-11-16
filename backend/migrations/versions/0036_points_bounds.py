"""How far a balance may travel, enforced by the database (audit M-3).

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-16

The balance columns are ``smallint``, which stops at 32767. Challenger is
deliberately uncapped and a perfect quiz is worth +300, so a dedicated
player passes that inside one season -- and every settlement after it
raises, leaving the account unable to finish another attempt ever.

``backend.ranked.scoring`` now clamps a settled total to +/-30000. This is
the same rule in the schema, following the project's convention that an
invariant belongs in the database and not only in the code that happens to
write it today: a balance written by anything else is bounded too.

The ledger's own bounds are wider on purpose. ``adjustment`` holds the
difference between two bounded totals, so it ranges over twice the span;
``points_before`` can legitimately hold a total written before this
migration existed, which is why its range is the column's own and not the
clamp's.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036"
down_revision: Union[str, Sequence[str], None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CEILING = 30000
FLOOR = -30000


def upgrade() -> None:
    op.execute(
        "ALTER TABLE balances"
        " ADD CONSTRAINT balances_points_range"
        f" CHECK (current_points BETWEEN {FLOOR} AND {CEILING})"
    )
    # The difference between two bounded totals spans twice the range.
    op.execute(
        "ALTER TABLE balance_history"
        " ADD CONSTRAINT balance_history_adjustment_range"
        f" CHECK (adjustment BETWEEN {FLOOR * 2} AND {CEILING * 2})"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " ADD CONSTRAINT balance_history_points_after_range"
        f" CHECK (points_after BETWEEN {FLOOR} AND {CEILING})"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_points_after_range"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_adjustment_range"
    )
    op.execute(
        "ALTER TABLE balances DROP CONSTRAINT IF EXISTS balances_points_range"
    )
