"""Player-requested Support tickets.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-15

Decision 8: Support holds Tickets and nothing else. **Only a player request
creates a ticket** — the system never opens one, and a connection flag never
becomes one. A ticket carries the attempt it is about; a written description
is optional.

A ticket closes as network instability, or as insufficient evidence without
any accusation, or stays open for follow-up. None of those changes points or
access, so this table has no column that could: it holds the request, its
subject and its outcome, and nothing else.

The description and the attempt's unshared detailed connection events are
deleted fifteen days after closure, which is why ``closed_at`` is stored
rather than only an outcome.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE support_tickets (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            attempt_id uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
            description text NULL,
            opened_at timestamptz NOT NULL DEFAULT now(),
            closed_at timestamptz NULL,
            closed_outcome varchar(32) NULL
                CHECK (closed_outcome IN ('network_instability', 'insufficient_evidence')),
            CONSTRAINT support_tickets_closed_together
                CHECK ((closed_at IS NULL) = (closed_outcome IS NULL)),
            -- An empty description is not a description: the field is optional,
            -- and a blank string would survive the 15-day cleanup as a row with
            -- nothing in it.
            CONSTRAINT support_tickets_description_not_blank
                CHECK (description IS NULL OR length(btrim(description)) > 0)
        )
        """
    )
    # A player's own tickets, newest first: the list screen's only query.
    op.execute(
        """
        CREATE INDEX support_tickets_account_opened_key
        ON support_tickets (account_id, opened_at DESC)
        """
    )
    # Closed tickets due for cleanup, found without scanning open ones.
    op.execute(
        """
        CREATE INDEX support_tickets_closed_at_key
        ON support_tickets (closed_at)
        WHERE closed_at IS NOT NULL
        """
    )
    # One open ticket per attempt per account: a second request about the same
    # attempt is the same case, not a new one. Closed ones do not block a new
    # request about that attempt.
    op.execute(
        """
        CREATE UNIQUE INDEX support_tickets_one_open_per_attempt_key
        ON support_tickets (account_id, attempt_id)
        WHERE closed_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS support_tickets")
