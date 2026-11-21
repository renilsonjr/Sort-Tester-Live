"""Messages a locked-out player leaves for the owner (issue #251).

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-21

A player who lost their login ID cannot sign in, so they cannot open a
support ticket, and there is deliberately no email. This is the one thing
they can do from the sign-in screen: leave a message the owner reads.

It is not `recovery_requests`. That table records the owner standing in
front of an account they have identified, so it requires the account and
the owner. A message comes from nobody in particular: it names no account,
none is guessed from its text, and it proves nothing about who wrote it.
Restoring access still goes through `recovery_requests`, in person.

The row keeps the text, when it arrived, and when and by whom it was
marked resolved. It does not keep the network address it came from.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: Union[str, Sequence[str], None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE recovery_messages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            body text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz,
            resolved_by uuid REFERENCES accounts(id) ON DELETE SET NULL,
            CONSTRAINT recovery_messages_body_length CHECK (
                char_length(body) BETWEEN 1 AND 500
            ),
            CONSTRAINT recovery_messages_resolved_pair CHECK (
                resolved_by IS NULL OR resolved_at IS NOT NULL
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX recovery_messages_created_idx"
        " ON recovery_messages (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recovery_messages")
