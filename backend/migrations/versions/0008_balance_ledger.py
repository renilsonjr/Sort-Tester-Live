"""Balance ledger: one row per account and immutable settlement history.

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

_BADGES = "'Iron', 'Bronze', 'Silver', 'Gold', 'Challenger'"


def upgrade() -> None:
    # balances: exactly one row per account — the PRIMARY KEY on account_id
    # IS the one-row-per-account rule, and the cascade keeps balances from
    # outliving their account. current_points is a cached projection of the
    # history rows below; the schema cannot enforce that pairing (that is
    # engine transaction logic, pinned by the atomicity tests), but the
    # default of 0 means a fresh account starts at zero points.
    op.execute(
        """
        CREATE TABLE balances (
            account_id uuid PRIMARY KEY
                REFERENCES accounts(id) ON DELETE CASCADE,
            current_points smallint NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # balance_history: insert-only settlement ledger. The UNIQUE key on
    # settlement_id mirrors the settlement PK: points apply at most once,
    # so one settlement can produce at most one history row. The FK targets
    # settlements(attempt_id) ON DELETE CASCADE, so deleting an attempt (and
    # thereby its settlement) removes the history entry with it. Scores,
    # adjustments, and the badge brackets before/after are recorded as-is;
    # recompute logic lives in the engine, never in row mutation.
    op.execute(
        f"""
        CREATE TABLE balance_history (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL
                REFERENCES accounts(id) ON DELETE CASCADE,
            settlement_id uuid NOT NULL UNIQUE
                REFERENCES settlements(attempt_id) ON DELETE CASCADE,
            raw_score smallint NOT NULL,
            adjustment smallint NOT NULL,
            points_before smallint NOT NULL,
            points_after smallint NOT NULL,
            badge_before varchar(16) NOT NULL
                CHECK (badge_before IN ({_BADGES})),
            badge_after varchar(16) NOT NULL
                CHECK (badge_after IN ({_BADGES})),
            recorded_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    # history references balances' account chain but not the balances table
    # itself, yet it must go first because its settlement FK is the only
    # outbound edge to drop; balances follows.
    op.drop_table("balance_history")
    op.drop_table("balances")
