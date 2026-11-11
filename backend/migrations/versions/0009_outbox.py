"""Durable outbox extension contract for later feature workers.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # outbox: a durable queue of work for later feature workers. The table
    # deliberately carries NO foreign keys to any feature table (emails,
    # accounts, or any table a later feature might add): pointing the row
    # at its real subject would force a cyclic later-feature dependency
    # between this migration and migrations that do not exist yet. The
    # subject reference instead travels inside the generic `payload` JSONB,
    # and `message_key` is the idempotency handle the worker dedupes on;
    # `recipient_destination_version` and `consent_version` pin the
    # destination and consent state the message was rendered for;
    # `attempt_count` and `worker_lease_until` are the bounded-retry and
    # lease knobs the dispatcher owns (payload is never rewritten).
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


def downgrade() -> None:
    op.drop_table("outbox")
