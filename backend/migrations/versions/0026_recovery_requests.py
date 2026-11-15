"""The owner's record of in-person access recoveries.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-15

The settled recovery policy turns on a trusted participant link
"established before the request". For that to mean anything, the request
needs a moment of its own: a link recorded in the same breath as the
recovery proves nothing, because it is just the owner asserting twice.
So a recovery is opened first, with its own timestamp, and completing it
requires a link older than that.

It is also the one-use handoff. The new login ID is shown once and
**not stored here**: only its hash exists, in login_credentials, like
every other credential. ``completed_at`` says the handoff happened, so a
second reading is refused rather than issuing a second secret.

The table keeps who, when and whether it completed, and nothing else. It
is not an audit trail of a player's behaviour, and nothing about how
anybody has played belongs in it. The account reference cascades: a
deleted account takes its recovery records with it, so these rows cannot
become a retained record of a deleted player.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, Sequence[str], None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE recovery_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            opened_by uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            opened_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz,
            completed_by uuid REFERENCES accounts(id) ON DELETE SET NULL,
            CONSTRAINT recovery_requests_completed_pair CHECK (
                (completed_at IS NULL AND completed_by IS NULL)
                OR completed_at IS NOT NULL
            ),
            CONSTRAINT recovery_requests_completed_after_open CHECK (
                completed_at IS NULL OR completed_at >= opened_at
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX recovery_requests_account_idx"
        " ON recovery_requests (account_id, opened_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recovery_requests")
