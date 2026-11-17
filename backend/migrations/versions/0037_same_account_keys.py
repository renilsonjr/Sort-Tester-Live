"""Related rows must belong to the same account (audit M-10).

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-17

Every one of these tables already had a foreign key saying "this points at
a real row". None of them said "and it is the same player's row". The
difference only shows up when something goes wrong: a settlement written
against another account's attempt, a ledger entry under the wrong name, a
tie-break attempt belonging to somebody else. Today the code never does
that -- these keys are so that a future change, or a hand-written
statement at three in the morning, cannot either.

The pattern is the same each time: a uniqueness key on `(id, account_id)`
of the parent, so a child can point at both columns at once and the
database checks the pair rather than the id alone.

`settlements` gains `account_id` for this, backfilled from the attempt it
settles -- which is where the value already lived, so nothing is invented.

Two indexes go: `sessions_token_hash_idx` and
`login_credentials_lookup_key_idx` are plain btrees on columns that each
already carry a UNIQUE index. A unique index answers every lookup the
plain one would, so the duplicates cost write time and space for nothing.

**Not here, deliberately.** The plan for this task also proposed
`season_prizes.place` with `UNIQUE (season_id, place)`. The settled prize
rule has players tied inside the top three *share* a place -- 900, 900,
800 gives places 1, 1, 3 -- so that constraint would forbid the result
the rules require. `tooling_probe` was also to be dropped; it is the only
table the runtime role cannot read, and `test_runtime_db_role` uses that
to prove the role is limited. New tables are granted automatically, so
there would be no replacement for it.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0037"
down_revision: Union[str, Sequence[str], None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. settlements learns whose settlement it is. Added nullable, filled
    #    from the attempt, then made NOT NULL: a column cannot be NOT NULL
    #    while the rows that exist have nothing in it.
    op.execute("ALTER TABLE settlements ADD COLUMN account_id uuid")
    op.execute(
        "UPDATE settlements s SET account_id = a.account_id"
        " FROM attempts a WHERE a.id = s.attempt_id"
    )
    op.execute("ALTER TABLE settlements ALTER COLUMN account_id SET NOT NULL")
    op.execute(
        "ALTER TABLE settlements"
        " ADD CONSTRAINT settlements_attempt_account_key"
        " UNIQUE (attempt_id, account_id)"
    )
    # and it must be the attempt's own account, not merely a real one
    op.execute(
        "ALTER TABLE settlements"
        " ADD CONSTRAINT settlements_attempt_same_account_fkey"
        " FOREIGN KEY (attempt_id, account_id)"
        " REFERENCES attempts (id, account_id) ON DELETE CASCADE"
    )

    # 2. a ledger entry points at the settlement AND the account together,
    #    so it cannot record one player's points against another's result
    op.execute(
        "ALTER TABLE balance_history"
        " ADD CONSTRAINT balance_history_same_account_fkey"
        " FOREIGN KEY (settlement_id, account_id)"
        " REFERENCES settlements (attempt_id, account_id) ON DELETE CASCADE"
    )

    # 3. an attempt belongs to the assignment it was created from, and that
    #    assignment belongs to the same player
    op.execute(
        "ALTER TABLE assignments"
        " ADD CONSTRAINT assignments_id_account_key UNIQUE (id, account_id)"
    )
    op.execute(
        "ALTER TABLE attempts"
        " ADD CONSTRAINT attempts_assignment_same_account_fkey"
        " FOREIGN KEY (assignment_id, account_id)"
        " REFERENCES assignments (id, account_id)"
    )

    # 4. a tie-break seat and the attempt behind it are one player's
    op.execute(
        "ALTER TABLE tiebreak_attempts"
        " ADD CONSTRAINT tiebreak_attempts_same_account_fkey"
        " FOREIGN KEY (attempt_id, account_id)"
        " REFERENCES attempts (id, account_id) ON DELETE CASCADE"
    )

    # 5. duplicates of an existing UNIQUE index on the same column
    op.execute("DROP INDEX IF EXISTS sessions_token_hash_idx")
    op.execute("DROP INDEX IF EXISTS login_credentials_lookup_key_idx")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS login_credentials_lookup_key_idx"
        " ON login_credentials (lookup_key)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS sessions_token_hash_idx"
        " ON sessions (token_hash)"
    )
    op.execute(
        "ALTER TABLE tiebreak_attempts"
        " DROP CONSTRAINT IF EXISTS tiebreak_attempts_same_account_fkey"
    )
    op.execute(
        "ALTER TABLE attempts"
        " DROP CONSTRAINT IF EXISTS attempts_assignment_same_account_fkey"
    )
    op.execute(
        "ALTER TABLE assignments DROP CONSTRAINT IF EXISTS assignments_id_account_key"
    )
    op.execute(
        "ALTER TABLE balance_history"
        " DROP CONSTRAINT IF EXISTS balance_history_same_account_fkey"
    )
    op.execute(
        "ALTER TABLE settlements"
        " DROP CONSTRAINT IF EXISTS settlements_attempt_same_account_fkey"
    )
    op.execute(
        "ALTER TABLE settlements DROP CONSTRAINT IF EXISTS settlements_attempt_account_key"
    )
    op.execute("ALTER TABLE settlements DROP COLUMN IF EXISTS account_id")
