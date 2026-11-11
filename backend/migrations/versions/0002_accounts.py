"""Accounts: stable id, case-insensitive username, permanent tag.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USERNAME_RE = r"^[A-Za-z0-9_]{3,24}$"
_USERNAME_LOWER_RE = r"^[a-z0-9_]{3,24}$"
_TAG_RE = r"^[A-Z0-9]{6}$"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            username varchar(24) NOT NULL
                CHECK (username ~ '{_USERNAME_RE}'),
            username_lower varchar(24) NOT NULL UNIQUE
                CHECK (username_lower ~ '{_USERNAME_LOWER_RE}'),
            tag varchar(6) NOT NULL UNIQUE
                CHECK (tag ~ '{_TAG_RE}'),
            created_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz NULL
        )
        """
    )


def downgrade() -> None:
    op.drop_table("accounts")
