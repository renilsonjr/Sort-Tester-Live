"""Participant links and minimal season-ineligibility marker.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE participant_links (
            account_id uuid NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
            roster_reference varchar(128) NOT NULL,
            established_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Q10 deletion-survival requirement: season_markers has deliberately NO foreign key to accounts — markers must survive account deletion, so do not "fix" this.
    op.execute(
        """
        CREATE TABLE season_markers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            roster_reference varchar(128) NOT NULL,
            season varchar(64) NOT NULL,
            ineligible boolean NOT NULL,
            CONSTRAINT season_markers_reference_season_key
                UNIQUE (roster_reference, season)
        )
        """
    )


def downgrade() -> None:
    op.drop_table("season_markers")
    op.drop_table("participant_links")
