"""Login credentials: one verifier per account, looked up by non-secret key.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # login_credentials stores the verifier for the system-generated login ID.
    # The raw login ID is never persisted; only a non-secret lookup key and an
    # Argon2id verifier are kept here. One *active* row per account; credential
    # rotation or admin recovery revokes the old row and creates a new one.
    op.execute(
        """
        CREATE TABLE login_credentials (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            lookup_key varchar(32) NOT NULL UNIQUE,
            verifier text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz NULL,
            CHECK (revoked_at IS NULL OR revoked_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX login_credentials_active_account_idx
            ON login_credentials(account_id)
            WHERE revoked_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX login_credentials_lookup_key_idx
            ON login_credentials(lookup_key)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS login_credentials_lookup_key_idx")
    op.execute("DROP INDEX IF EXISTS login_credentials_active_account_idx")
    op.execute("DROP TABLE login_credentials")
