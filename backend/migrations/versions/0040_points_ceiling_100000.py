"""Raise how far a balance may travel, from 30000 to 100000.

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-25

Owner decision, 2026-11-25: 30000 is too low a stopping point for a
Challenger, so the ceiling becomes 100000 and the floor -100000.

The old ceiling was not a round number somebody liked. The columns holding
points are ``smallint``, which stops at 32767, and 0036 clamped the game to
+/-30000 to stay inside that. So raising the rule means widening the
columns first: a clamp at 100000 against a smallint column would be refused
by the database on the first settlement that passed 32767, and the account
would never finish another attempt -- exactly the breakage 0036 existed to
prevent.

``integer`` holds +/-2147483647, which is far past anything the game can
reach: a perfect quiz is worth +300, so 100000 is about 334 of them.

Every column that carries points moves together, including the ones in
``settlements``, which 0036 did not constrain but which are the same
smallint. ``raw_score`` is one quiz's own worth and never came near the
limit; it widens anyway so that no column in this group is the odd one out.

The tables are small and the rewrite is quick, but it is still a rewrite:
run this before the image that clamps at the new figure, never after. The
other order leaves the app writing totals the database refuses.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: Union[str, Sequence[str], None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_CEILING = 30000
CEILING = 100000
FLOOR = -CEILING

# table, column
POINT_COLUMNS = (
    ("balances", "current_points"),
    ("balance_history", "raw_score"),
    ("balance_history", "adjustment"),
    ("balance_history", "points_before"),
    ("balance_history", "points_after"),
    ("settlements", "raw_score"),
    ("settlements", "adjustment"),
)


def _widen(to_type: str) -> None:
    for table, column in POINT_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {to_type}")


def upgrade() -> None:
    # The bounds come off first: a CHECK naming the old figures would refuse
    # the new ones, and dropping them after the widening would leave a
    # window where the column is wide and the old rule still stands.
    op.execute("ALTER TABLE balances DROP CONSTRAINT IF EXISTS balances_points_range")
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_adjustment_range"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_points_after_range"
    )
    _widen("integer")
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
    """Back to the smallint columns and the 30000 rule.

    This fails, on purpose, if any row already holds a total the old columns
    cannot: going back has to be a decision about those rows, not a silent
    truncation of somebody's balance.
    """
    op.execute("ALTER TABLE balances DROP CONSTRAINT IF EXISTS balances_points_range")
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_adjustment_range"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_points_after_range"
    )
    _widen("smallint")
    op.execute(
        "ALTER TABLE balances"
        " ADD CONSTRAINT balances_points_range"
        f" CHECK (current_points BETWEEN {-OLD_CEILING} AND {OLD_CEILING})"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " ADD CONSTRAINT balance_history_adjustment_range"
        f" CHECK (adjustment BETWEEN {-OLD_CEILING * 2} AND {OLD_CEILING * 2})"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " ADD CONSTRAINT balance_history_points_after_range"
        f" CHECK (points_after BETWEEN {-OLD_CEILING} AND {OLD_CEILING})"
    )
