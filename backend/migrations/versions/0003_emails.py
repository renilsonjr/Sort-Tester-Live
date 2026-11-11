"""Emails: alias-preserving addresses, lifecycle state, reminder consent gate.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE emails (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            address varchar(254) NOT NULL,
            address_normalized varchar(254) NOT NULL
                CHECK (address_normalized = lower(address)),
            state varchar(16) NOT NULL
                CHECK (state IN ('pending','verified','retired')),
            reminder_opt_in boolean NOT NULL DEFAULT false,
            reminder_opt_in_at timestamptz NULL,
            consent_season varchar(64) NULL,
            verified_at timestamptz NULL,
            CONSTRAINT emails_consent_gate CHECK
                (reminder_opt_in = false
                 OR (state = 'verified' AND reminder_opt_in_at IS NOT NULL))
        )
        """
    )
    # one non-retired row per address_normalized: alias folding (dots, plus-tags)
    # is never applied — only lowercasing — so a.b@, ab@ and a+b@ stay distinct
    op.execute(
        """
        CREATE UNIQUE INDEX emails_active_address_normalized_key
        ON emails (address_normalized)
        WHERE state <> 'retired'
        """
    )
    # one non-retired row per account
    op.execute(
        """
        CREATE UNIQUE INDEX emails_active_account_key
        ON emails (account_id)
        WHERE state <> 'retired'
        """
    )


def downgrade() -> None:
    # the partial unique indexes are dropped with the table
    op.drop_table("emails")
