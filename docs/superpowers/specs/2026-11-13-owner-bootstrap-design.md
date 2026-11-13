# Auth follow-ups — owner bootstrap (Issue #47, slice 1)

First slice of #47. Launch (#23) and flag review (#25) need an owner account,
and today the only way to make one is a hand edit of the database. This slice
adds the "one-time local operator command" the security/operations design
asks for: "Bootstrap the sole owner role using a one-time local operator
command, never a public signup flag."

## Plan for #47

1. Owner bootstrap (this slice).
2. Registration hardening.
3. Self-service account deletion.
4. Hosting and the frontend login gate (needs #41).

## Design

**Schema.** Migration `0020` adds a partial unique index on
`accounts (is_owner) WHERE is_owner`: at most one owner account can exist,
whatever writes to the table.

**`backend/auth/owner.py`.**

- `designate_owner(conn, tag)` makes the account with that tag the owner and
  returns its id, username and tag. It refuses, changing nothing, when an
  owner already exists (`OwnerExistsError`) or when no active account has the
  tag (`AccountNotFoundError`; an account pending deletion is not active).
  Tags are matched case-insensitively.
- `main(argv)` is the command:

  ```
  python -m backend.auth.owner designate --tag A1B2
  ```

  It connects with the application's database settings, prints the account
  that became the owner, and exits 0; a refusal prints the reason to stderr
  and exits 1.

There is no HTTP route: only someone with access to the server machine can
run the command.

**Not included.** Changing the owner later. The owner role is sole, and a
handover is a rare manual step; a `transfer` command can be added if the
owner asks for one. The owner's second sign-in factor is #11/#13.

## Testing (TDD, live scratch PostgreSQL)

- Designating sets the flag and returns the account.
- A second designation, even of the same account, is refused; nothing changes.
- An unknown tag and an account pending deletion are refused.
- A lower-case tag matches.
- The database refuses a second owner written directly.
- The command prints the result and exits 0, and exits 1 with a message on a
  refusal.
- Migration 0020 in the full-chain test.
