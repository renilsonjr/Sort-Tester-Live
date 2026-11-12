"""Opaque server-side sessions stored in PostgreSQL.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sessions holds opaque server-side session state. The raw session token
    # is never persisted; only its SHA-256 digest is stored. Revocation and
    # expiry are enforced server-side.
    op.execute(
        """
        CREATE TABLE sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            token_hash bytea NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz NULL,
            ip_address inet NULL,
            user_agent text NULL,
            CHECK (revoked_at IS NULL OR revoked_at >= created_at),
            CHECK (expires_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX sessions_account_id_idx ON sessions(account_id)
        """
    )
    op.execute(
        """
        CREATE INDEX sessions_token_hash_idx ON sessions(token_hash)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS sessions_token_hash_idx")
    op.execute("DROP INDEX IF EXISTS sessions_account_id_idx")
    op.execute("DROP TABLE sessions")
