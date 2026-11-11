"""Tooling probe: verifies the Alembic pipeline runs end to end.

Revision ID: 0001
Revises:
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tooling_probe",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("note", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tooling_probe")
