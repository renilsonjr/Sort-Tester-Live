"""Player-requested Support tickets (issue #26).

Decision 8: Support holds Tickets and nothing else, and **only a player
request creates one**. Nothing in this module is reachable from settlement,
from a connection flag, or from any automatic sweep: a ticket exists because
somebody asked for it.

A ticket carries the attempt it is about and an optional description. It
changes no points and no access, which is why nothing here writes to a
balance, an attempt or an account.

Players see only their own tickets. Every read in this module takes the
account whose tickets are wanted, so a missing check is a missing argument
rather than a silently wider query.
"""
from backend.db import migrate

CLOSING_OUTCOMES = ("network_instability", "insufficient_evidence")


class AttemptNotYoursError(Exception):
    """The attempt belongs to another account, or does not exist."""


class TicketAlreadyOpenError(Exception):
    """This account already has an open ticket about this attempt."""


class NotAuthorizedError(Exception):
    """The caller is not an authorized reviewer."""


class TicketNotFoundError(Exception):
    """No such ticket."""


def open_ticket(conn, account_id, attempt_id, *, description=None):
    """Open a ticket for this account about one of its own attempts.

    Returns the new ticket's id. Does not commit: the caller owns the
    transaction.

    A description is optional, and a blank one is stored as no description
    rather than as an empty string. Raises :class:`AttemptNotYoursError` if
    the attempt is not this account's, and :class:`TicketAlreadyOpenError` if
    an open ticket about it already exists — a second request about the same
    attempt is the same case, not a new one.
    """
    owner = migrate.fetch_one(
        conn,
        "SELECT account_id FROM attempts WHERE id = %s",
        (attempt_id,),
    )
    if owner is None or owner["account_id"] != account_id:
        # Same answer either way: whether an attempt exists is not something
        # one player gets to learn about another.
        raise AttemptNotYoursError(attempt_id)

    text = description.strip() if description else ""
    row = migrate.fetch_one(
        conn,
        "INSERT INTO support_tickets (account_id, attempt_id, description)"
        " VALUES (%s, %s, %s)"
        " ON CONFLICT DO NOTHING RETURNING id",
        (account_id, attempt_id, text or None),
    )
    if row is None:
        raise TicketAlreadyOpenError(attempt_id)
    return row["id"]


def tickets_for(conn, account_id) -> list[dict]:
    """This account's tickets, newest first.

    Takes the account, so there is no form of this call that returns
    somebody else's tickets.
    """
    return migrate.fetch_all(
        conn,
        "SELECT id, attempt_id, description, opened_at, closed_at, closed_outcome"
        " FROM support_tickets WHERE account_id = %s"
        " ORDER BY opened_at DESC, id",
        (account_id,),
    )


def ticket_for(conn, account_id, ticket_id) -> dict | None:
    """One of this account's tickets, or None.

    None covers both "no such ticket" and "somebody else's ticket": a player
    cannot tell those apart, and does not need to.
    """
    return migrate.fetch_one(
        conn,
        "SELECT id, attempt_id, description, opened_at, closed_at, closed_outcome"
        " FROM support_tickets WHERE id = %s AND account_id = %s",
        (ticket_id, account_id),
    )


def _require_reviewer(conn, admin_account_id):
    """Raise unless this account is the owner.

    Decision 8 allows authorized administrators to review tickets. Today the
    owner is the only such role (`accounts.is_owner`, migration 0012); when
    more exist, this is the one place that changes.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT 1 AS ok FROM accounts WHERE id = %s AND is_owner = true",
        (admin_account_id,),
    )
    if row is None:
        raise NotAuthorizedError(admin_account_id)


def open_tickets_for_review(conn, admin_account_id) -> list[dict]:
    """Open tickets, oldest first, with only what a reviewer needs.

    The player's display identity, the attempt, the description they wrote
    and that attempt's connection events. Nothing else about the player is
    returned: not their balance, not their badge, not their other tickets,
    not their email — there is none — and not another player's case.
    """
    _require_reviewer(conn, admin_account_id)
    rows = migrate.fetch_all(
        conn,
        "SELECT t.id, t.attempt_id, t.description, t.opened_at,"
        " ac.username, ac.tag"
        " FROM support_tickets t"
        " JOIN accounts ac ON ac.id = t.account_id"
        " WHERE t.closed_at IS NULL"
        " ORDER BY t.opened_at, t.id",
    )
    for row in rows:
        row["events"] = migrate.fetch_all(
            conn,
            "SELECT kind, occurred_at FROM attempt_connection_events"
            " WHERE attempt_id = %s ORDER BY occurred_at, kind",
            (row["attempt_id"],),
        )
    return rows


def close_ticket(conn, admin_account_id, ticket_id, outcome, *, clock) -> str:
    """Close an open ticket with a review outcome; return the stored outcome.

    The outcomes are the two Decision 8 allows: ``network_instability``, and
    ``insufficient_evidence``, which ends a case without accusing anybody.
    Leaving a ticket open for follow-up is not closing it, so it has no
    outcome here.

    Closing an already closed ticket changes nothing and returns the outcome
    it already had, so a repeated request cannot rewrite a decision or move
    the fifteen-day clock. **Closure touches no points and no access**: this
    function writes to one table, and that table has no column that could.
    """
    if outcome not in CLOSING_OUTCOMES:
        raise ValueError(f"unknown review outcome: {outcome!r}")
    _require_reviewer(conn, admin_account_id)
    row = migrate.fetch_one(
        conn,
        "SELECT closed_outcome FROM support_tickets WHERE id = %s FOR UPDATE",
        (ticket_id,),
    )
    if row is None:
        raise TicketNotFoundError(ticket_id)
    if row["closed_outcome"] is not None:
        return row["closed_outcome"]
    migrate.execute(
        conn,
        "UPDATE support_tickets SET closed_at = %s, closed_outcome = %s WHERE id = %s",
        (clock.now(), outcome, ticket_id),
    )
    return outcome


def reopen_ticket(conn, admin_account_id, ticket_id) -> None:
    """Reopen a closed ticket for follow-up.

    Clears the closure, which also stops the fifteen-day cleanup: evidence an
    open case still needs must not be deleted underneath it. Reopening an
    open ticket changes nothing.
    """
    _require_reviewer(conn, admin_account_id)
    row = migrate.fetch_one(
        conn,
        "SELECT closed_at FROM support_tickets WHERE id = %s FOR UPDATE",
        (ticket_id,),
    )
    if row is None:
        raise TicketNotFoundError(ticket_id)
    if row["closed_at"] is None:
        return
    migrate.execute(
        conn,
        "UPDATE support_tickets SET closed_at = NULL, closed_outcome = NULL"
        " WHERE id = %s",
        (ticket_id,),
    )
