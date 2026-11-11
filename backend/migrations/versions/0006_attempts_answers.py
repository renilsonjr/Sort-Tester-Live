"""Attempts, active-attempt lock, and answer acceptance.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # season_id has deliberately NO foreign key until Task 3 (the seasons
    # table does not exist yet); Task 3 adds the FK — do not add one here.
    # The state CHECKs carry the terminal-serialization contract: finalized
    # requires both final_outcome and settled_at, so a finalized attempt
    # always records its single outcome.
    op.execute(
        """
        CREATE TABLE attempts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            assignment_id uuid NOT NULL UNIQUE REFERENCES assignments(id),
            mode varchar(16) NOT NULL
                CHECK (mode IN ('normal', 'promotion', 'tiebreak')),
            tiebreak_round smallint NULL
                CHECK (tiebreak_round IS NULL
                       OR (mode = 'tiebreak' AND tiebreak_round BETWEEN 1 AND 5)),
            season_id uuid NOT NULL,
            state varchar(24) NOT NULL
                CHECK (state IN ('active', 'grace', 'terminal_pending', 'finalized')),
            CHECK (state <> 'grace' OR grace_deadline_at IS NOT NULL),
            CHECK (state NOT IN ('terminal_pending', 'finalized')
                   OR final_outcome IS NOT NULL),
            CHECK (state <> 'finalized' OR settled_at IS NOT NULL),
            started_at timestamptz NOT NULL DEFAULT now(),
            grace_deadline_at timestamptz NULL,
            final_outcome varchar(24) NULL
                CHECK (final_outcome IN (
                    'completed', 'quit', 'disconnect', 'season_close',
                    'launch_reset', 'outage_void')),
            settled_at timestamptz NULL
        )
        """
    )
    # active-attempt lock: one unfinished attempt per account across all
    # modes; finalized rows stop counting, so a new active attempt can start
    op.execute(
        """
        CREATE UNIQUE INDEX attempts_one_unfinished_per_account
            ON attempts (account_id)
            WHERE state IN ('active', 'grace', 'terminal_pending')
        """
    )
    # insert-only answer acceptance: rows are written at send time and
    # accepted once; answer NULL means sent-but-unanswered at settlement
    op.execute(
        """
        CREATE TABLE attempt_answers (
            attempt_id uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
            seq smallint NOT NULL CHECK (seq BETWEEN 1 AND 15),
            question_version_id uuid NOT NULL REFERENCES question_versions(id),
            first_sent_at timestamptz NOT NULL,
            deadline_at timestamptz NOT NULL CHECK (deadline_at > first_sent_at),
            answer varchar(16) NULL
                CHECK (answer IN ('correct', 'wrong', 'timeout')),
            outcome varchar(16) NOT NULL
                CHECK (outcome IN ('correct', 'wrong', 'timeout', 'unsent')),
            accepted_at timestamptz NULL
                CHECK ((answer IS NOT NULL) = (accepted_at IS NOT NULL)),
            PRIMARY KEY (attempt_id, seq)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_attempt_answers_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.attempt_id IS DISTINCT FROM OLD.attempt_id
               OR NEW.seq IS DISTINCT FROM OLD.seq
               OR NEW.question_version_id IS DISTINCT FROM OLD.question_version_id
               OR NEW.first_sent_at IS DISTINCT FROM OLD.first_sent_at
               OR NEW.deadline_at IS DISTINCT FROM OLD.deadline_at
               OR NEW.outcome IS DISTINCT FROM OLD.outcome
               OR NOT (
                   NEW.answer IS DISTINCT FROM OLD.answer
                   AND NEW.accepted_at IS DISTINCT FROM OLD.accepted_at
                   AND OLD.answer IS NULL
                   AND OLD.accepted_at IS NULL
                   AND NEW.answer IS NOT NULL
                   AND NEW.accepted_at IS NOT NULL
               )
            THEN
                RAISE EXCEPTION 'attempt_answers is immutable except for the one-way acceptance of an answer';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER attempt_answers_immutable
            BEFORE UPDATE ON attempt_answers
            FOR EACH ROW EXECUTE FUNCTION reject_attempt_answers_update()
        """
    )


def downgrade() -> None:
    op.drop_table("attempt_answers")
    op.execute("DROP FUNCTION IF EXISTS reject_attempt_answers_update()")
    op.drop_index("attempts_one_unfinished_per_account", table_name="attempts")
    op.drop_table("attempts")
