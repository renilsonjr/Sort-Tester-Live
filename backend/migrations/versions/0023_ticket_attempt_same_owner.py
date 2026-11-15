"""A ticket's attempt must belong to the ticket's account.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-15

``open_ticket`` already refuses an attempt that is not the caller's, so no
mismatched row can be written through the application today. The schema did
not say so, and the whole access model for Support rests on it: every read
filters by ``account_id``, and the ticket carries the attempt whose
connection events a reviewer is shown. A ticket pointing at somebody else's
attempt would hand that player's evidence to the wrong person while passing
every ownership check, because the check is on the ticket, not the attempt.

A composite foreign key makes that row impossible in the database, not only
in the code path that happens to create tickets today. It needs a unique
key on ``(id, account_id)`` in ``attempts`` to point at; ``id`` is already
the primary key, so the pair is unique and the index is cheap.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE attempts ADD CONSTRAINT attempts_id_account_key"
        " UNIQUE (id, account_id)"
    )
    # Replaces the single-column reference to attempts: the pair carries the
    # same ON DELETE CASCADE, so a deleted account still takes its tickets.
    op.execute(
        "ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_attempt_id_fkey"
    )
    op.execute(
        "ALTER TABLE support_tickets"
        " ADD CONSTRAINT support_tickets_attempt_same_account_fkey"
        " FOREIGN KEY (attempt_id, account_id)"
        " REFERENCES attempts (id, account_id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE support_tickets"
        " DROP CONSTRAINT IF EXISTS support_tickets_attempt_same_account_fkey"
    )
    op.execute(
        "ALTER TABLE support_tickets"
        " ADD CONSTRAINT support_tickets_attempt_id_fkey"
        " FOREIGN KEY (attempt_id) REFERENCES attempts (id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE attempts DROP CONSTRAINT IF EXISTS attempts_id_account_key"
    )
