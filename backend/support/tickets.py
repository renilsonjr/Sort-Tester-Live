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
