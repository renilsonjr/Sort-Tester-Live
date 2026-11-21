"""The four belts each tie-break question offers.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-15

Owner decision 2026-11-15: Ranked and tie-break questions show four belts,
the right one and three drawn from the others, and in a tie-break round the
same four for every player.

They are drawn once, with the server's randomness, and **stored**. Deriving
them from something the player can see -- the round id, the question
number -- would be reproducible, and since the three wrong belts are drawn
from "every belt but the right one", anybody with the code could try each
candidate answer and see which one reproduces the four on screen: the
options would give the answer away. Stored random options carry no such
information.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: Union[str, Sequence[str], None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable on purpose rather than filled by deleting what exists: a row
    # written before this column gets its four options drawn and stored the
    # first time its question is served (tiebreaks.options_for). New rounds
    # always get them when their questions are assigned.
    op.execute(
        "ALTER TABLE tiebreak_round_questions ADD COLUMN options varchar(16)[]"
    )
    op.execute(
        "ALTER TABLE tiebreak_round_questions"
        " ADD CONSTRAINT tiebreak_round_questions_four_options"
        " CHECK (options IS NULL OR array_length(options, 1) = 4)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tiebreak_round_questions DROP COLUMN IF EXISTS options")
