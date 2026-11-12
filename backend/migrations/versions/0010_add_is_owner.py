"""Add owner flag to accounts for admin authorization.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # is_owner is a placeholder for bootstrap authorization; only one or
    # a small number of accounts should ever have this true.
    op.execute(
        """
        ALTER TABLE accounts
        ADD COLUMN is_owner boolean NOT NULL DEFAULT false
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS is_owner")
