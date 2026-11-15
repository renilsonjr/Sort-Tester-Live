"""The five shared questions of each tie-break round.

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-15

Each round plays five Hard questions from the owner-approved regular bank,
the same five for every player in the group (owner decision 2026-11-15,
#136). Questions are pinned through ``question_versions`` like every
ordinary assignment, so a later bank revision cannot change a round that
was already played.

The settled rule is that no question is reused, across valid and
outage-replaced rounds alike. That is enforced here rather than trusted to
the code: the season and the question's canonical identity are carried on
the row, and the pair is unique. A second round of the same season simply
cannot be given a question an earlier round had -- even one that was later
voided, because its players saw it.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, Sequence[str], None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tiebreak_round_questions (
            round_id uuid NOT NULL REFERENCES tiebreak_rounds(id) ON DELETE CASCADE,
            seq smallint NOT NULL,
            question_version_id uuid NOT NULL REFERENCES question_versions(id),
            season_id uuid NOT NULL REFERENCES seasons(id),
            bank_key varchar(128) NOT NULL,
            PRIMARY KEY (round_id, seq),
            CONSTRAINT tiebreak_round_questions_seq_check CHECK (seq BETWEEN 1 AND 5),
            CONSTRAINT tiebreak_round_questions_never_reused
                UNIQUE (season_id, bank_key)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tiebreak_round_questions")
