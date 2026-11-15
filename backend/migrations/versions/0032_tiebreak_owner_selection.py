"""Who settled a tie by selection, and when.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-15

When the rules send a tie to the owner, the owner's choice is final (owner
decision, 2026-11-15) and nothing in the app takes it back, which matches
the record's "no already-finalized-award clawback". A final decision with
no record of who made it is not auditable, so the group carries the
account that selected and the moment. Nothing else: no reason field, no
note, nothing that could turn into commentary about a player.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032"
down_revision: Union[str, Sequence[str], None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tiebreak_groups"
        " ADD COLUMN selected_by uuid REFERENCES accounts(id) ON DELETE SET NULL,"
        " ADD COLUMN selected_at timestamptz"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tiebreak_groups DROP COLUMN IF EXISTS selected_by,"
        " DROP COLUMN IF EXISTS selected_at"
    )
