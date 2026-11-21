"""At most one owner account.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-13

The owner role is sole (security/operations design: "Bootstrap the sole owner
role using a one-time local operator command"). This partial unique index
makes a second owner impossible, whatever writes to the table.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX accounts_single_owner ON accounts (is_owner) WHERE is_owner"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS accounts_single_owner")
