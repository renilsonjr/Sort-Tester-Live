"""One approved account per sorter.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-15

The owner's settled Q5 is "one prize-eligible account and at most one hat
per sorter". ``participant_links`` already allowed only one row per
account, which stops one account being approved twice; it said nothing
about one **person** holding two approved accounts, and that is the side
the prize rule cares about. Two accounts for the same sorter, both
approved, would both stand in the standings and could take two of the
three hats.

The roster reference is who the person is on the owner's roster, so making
it unique is the schema saying what the rule says. A table that is empty
in every environment today takes the constraint without a backfill.

There is no accompanying ON DELETE behaviour to change: the row already
goes with its account, so a deleted account frees its sorter's reference
for a fresh approval, which is the recovery path the owner described.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE participant_links"
        " ADD CONSTRAINT participant_links_roster_reference_key"
        " UNIQUE (roster_reference)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE participant_links"
        " DROP CONSTRAINT IF EXISTS participant_links_roster_reference_key"
    )
