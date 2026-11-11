"""Question versions and frozen assignments.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # insert-only: the digest pins the exact reviewed content (the content
    # itself stays in backend/ranked_bank, never in the database)
    op.execute(
        """
        CREATE TABLE question_versions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            bank_key varchar(128) NOT NULL,
            difficulty varchar(8) NOT NULL
                CHECK (difficulty IN ('easy', 'medium', 'hard')),
            content_sha256 char(64) NOT NULL,
            CONSTRAINT question_versions_bank_key_digest
                UNIQUE (bank_key, content_sha256)
        )
        """
    )
    # season_id has deliberately NO foreign key until Task 3 (the seasons
    # table does not exist yet); Task 3 adds the FK — do not add one here.
    op.execute(
        """
        CREATE TABLE assignments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            mode varchar(16) NOT NULL
                CHECK (mode IN ('normal', 'promotion', 'tiebreak')),
            season_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # the 15-row 5/5/5 composition is an application invariant (issue #5
    # owns bank sufficiency); the no-repeat rule is the unique index below
    op.execute(
        """
        CREATE TABLE assignment_questions (
            assignment_id uuid NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
            seq smallint NOT NULL CHECK (seq BETWEEN 1 AND 15),
            question_version_id uuid NOT NULL REFERENCES question_versions(id),
            PRIMARY KEY (assignment_id, seq),
            CONSTRAINT assignment_questions_no_repeat
                UNIQUE (assignment_id, question_version_id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_question_versions_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'question_versions is immutable';
        END;
        $$;
        CREATE TRIGGER question_versions_immutable
            BEFORE UPDATE ON question_versions
            FOR EACH ROW EXECUTE FUNCTION reject_question_versions_update();

        CREATE FUNCTION reject_assignments_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'assignments are immutable';
        END;
        $$;
        CREATE TRIGGER assignments_immutable
            BEFORE UPDATE ON assignments
            FOR EACH ROW EXECUTE FUNCTION reject_assignments_update();

        CREATE FUNCTION reject_assignment_questions_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'assignment_questions are immutable';
        END;
        $$;
        CREATE TRIGGER assignment_questions_immutable
            BEFORE UPDATE ON assignment_questions
            FOR EACH ROW EXECUTE FUNCTION reject_assignment_questions_update()
        """
    )


def downgrade() -> None:
    op.drop_table("assignment_questions")
    op.drop_table("assignments")
    op.drop_table("question_versions")
    op.execute("DROP FUNCTION IF EXISTS reject_assignment_questions_update()")
    op.execute("DROP FUNCTION IF EXISTS reject_assignments_update()")
    op.execute("DROP FUNCTION IF EXISTS reject_question_versions_update()")
