"""Remove email storage after Decision 15 was withdrawn.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-15

The owner settled on 2026-11-14 that the app collects no email address at
all: Decision 15 (the one-time launch reminder) is withdrawn and Decision 14
no longer keeps an optional private email. The official season start is
announced in the app instead. Issue #27 is closed with nothing left to
build.

Two tables go:

* ``emails`` held the address, its verification state and the reminder
  consent gate. All three exist only for the withdrawn feature, and while
  the table stands the system still has somewhere to put an address no
  screen asks for.
* ``outbox`` was written as a general durable queue for later feature
  workers, not as a mail queue. Nothing in the application has ever written
  to it, and its only planned writer was #27. The owner chose to drop it
  rather than keep an unused table that the next reader has to understand;
  its design stays in this file and in the history of 0009.

Dropping ``emails`` also drops its rows, which is the point: the wipe in
Decision 14 is about leaving nothing behind.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both partial unique indexes on emails are dropped with the table.
    op.execute("DROP TABLE IF EXISTS emails")
    op.execute("DROP TABLE IF EXISTS outbox")


def downgrade() -> None:
    # Recreated exactly as 0003 and 0009 defined them, so a downgrade lands
    # on the same schema the earlier migrations produced. The rows are gone
    # for good; this restores the shape, never the data.
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
    op.execute(
        """
        CREATE UNIQUE INDEX emails_active_address_normalized_key
        ON emails (address_normalized)
        WHERE state <> 'retired'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX emails_active_account_key
        ON emails (account_id)
        WHERE state <> 'retired'
        """
    )
    op.execute(
        """
        CREATE TABLE outbox (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            message_key varchar(128) NOT NULL UNIQUE,
            payload jsonb NOT NULL,
            recipient_destination_version varchar(64) NOT NULL,
            consent_version varchar(64) NULL,
            attempt_count smallint NOT NULL DEFAULT 0
                CHECK (attempt_count >= 0),
            worker_lease_until timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
