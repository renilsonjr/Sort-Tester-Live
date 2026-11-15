"""Which attempt a player made in which tie-break round.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-15

Settled Decisions 9-10: one asynchronous attempt per player per round,
with no same-round retry after Quit, grace expiry or a refresh. The pair
(round, account) is unique, so a second attempt in the same round is
refused by the database and not only by the code that starts attempts.

A voided round is replaced by a new round row, so an outage restart gives
every player a fresh attempt without touching this rule.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, Sequence[str], None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tiebreak_attempts (
            round_id uuid NOT NULL REFERENCES tiebreak_rounds(id) ON DELETE CASCADE,
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            attempt_id uuid NOT NULL UNIQUE REFERENCES attempts(id) ON DELETE CASCADE,
            PRIMARY KEY (round_id, account_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tiebreak_attempts")
