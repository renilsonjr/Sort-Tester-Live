"""Page-instance capability hash on attempts.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-12

An attempt is bound to a random capability held only in the memory of the page
that started it (#8, decision record Decision 6). The server stores only the
SHA-256 of that token, so a database read does not yield a usable capability.
The raw token is never stored.

The column is nullable so existing rows stay valid; an attempt without a
stored capability cannot be continued by any page.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE attempts
            ADD COLUMN page_capability_sha256 bytea NULL
                CHECK (page_capability_sha256 IS NULL
                       OR octet_length(page_capability_sha256) = 32)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE attempts DROP COLUMN IF EXISTS page_capability_sha256")
