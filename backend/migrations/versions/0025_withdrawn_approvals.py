"""Remember which account a sorter held before an approval was withdrawn.

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-15

The owner's settled Q5 says the approved account is fixed for the official
season: recovery uses the same account, and there is no eligibility swap.
Withdrawing an approval has to stay possible, because the owner must be
able to take back one that should not stand, but once the row is deleted
nothing remembers that the sorter ever held it — so approving a different
account for the same person looked exactly like a first approval.

This table is that memory. It is written when an approval is withdrawn,
and read when a second account is proposed for the same roster reference:
if the withdrawn account has a completed official-season quiz, the
approval cannot move onto a different balance. A tag approved by mistake
and withdrawn straight away has no such quiz, so correcting a typo still
works.

``season_markers`` covers the other route, an account deleted outright,
and already survives the account on purpose. This table does not need to:
if the account is gone, so are the attempts that would be checked, and
the marker is what speaks then. So the account reference cascades.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, Sequence[str], None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE withdrawn_approvals (
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            roster_reference varchar(128) NOT NULL,
            withdrawn_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT withdrawn_approvals_account_reference_key
                UNIQUE (account_id, roster_reference)
        )
        """
    )
    op.execute(
        "CREATE INDEX withdrawn_approvals_reference_idx"
        " ON withdrawn_approvals (roster_reference)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS withdrawn_approvals")
