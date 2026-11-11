"""Seasons, phase guards, and unique settlement keys.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # seasons: one row per Pre-Season/official season instance; cutover
    # happens by opening the next row, never by mutating history. There is
    # deliberately NO trigger blocking post-close writes: that guard is
    # engine transaction logic (issues #8/#23), not schema — the structural
    # pieces here are (a) settlement's season_id FK, (b) the attempt's
    # frozen season_id, and (c) seasons.closed_at being queryable.
    op.execute(
        """
        CREATE TABLE seasons (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            phase varchar(16) NOT NULL
                CHECK (phase IN ('pre_season', 'official')),
            label varchar(64) NOT NULL UNIQUE,
            opened_at timestamptz NOT NULL DEFAULT now(),
            closed_at timestamptz NULL,
            CHECK (closed_at IS NULL OR closed_at >= opened_at)
        )
        """
    )
    # settlements: the PK on attempt_id IS the unique settlement key —
    # points are applied at most once, and a repeated terminal request
    # finds the existing row instead of writing again
    op.execute(
        """
        CREATE TABLE settlements (
            attempt_id uuid PRIMARY KEY
                REFERENCES attempts(id) ON DELETE CASCADE,
            season_id uuid NOT NULL REFERENCES seasons(id),
            raw_score smallint NOT NULL
                CHECK (raw_score BETWEEN -150 AND 300),
            adjustment smallint NOT NULL,
            final_outcome varchar(24) NOT NULL
                CHECK (final_outcome IN (
                    'completed', 'quit', 'disconnect', 'season_close',
                    'launch_reset', 'outage_void')),
            settled_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # the deferred FKs land here (Tasks 1–2 left season_id un-keyed on
    # purpose); 0007 owns these constraints so the earlier migration files
    # are never edited
    op.execute(
        """
        ALTER TABLE assignments ADD CONSTRAINT assignments_season_id_fk
            FOREIGN KEY (season_id) REFERENCES seasons(id)
        """
    )
    op.execute(
        """
        ALTER TABLE attempts ADD CONSTRAINT attempts_season_id_fk
            FOREIGN KEY (season_id) REFERENCES seasons(id)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE attempts DROP CONSTRAINT IF EXISTS attempts_season_id_fk"
    )
    op.execute(
        "ALTER TABLE assignments DROP CONSTRAINT IF EXISTS assignments_season_id_fk"
    )
    op.execute("DROP TABLE settlements")
    op.execute("DROP TABLE seasons")
