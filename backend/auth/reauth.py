"""Recent login-ID reauthentication for the owner's sensitive actions
(issue #11, box 5).

The settled design: before eligibility, recovery and prize actions, the
owner proves again that they hold the login ID -- "re-enter login ID /
equivalent short-lived reauth bound to the session ... within five
minutes". This app has no password, so the login ID is that proof.

Two decisions follow from the wording, and both are deliberate:

* **Bound to the session.** The proof is a timestamp on the session row,
  so it covers the device it was typed on and nothing else. A cookie
  copied to another device carries a session that never reauthenticated.
* **A window, not a prompt per action.** The owner's work comes in runs --
  approve several sorters, then hand over a recovery -- and asking for the
  login ID before every click would train the owner to type it without
  reading. Five minutes covers a run and expires before a phone left on a
  desk is much use to anybody.

The login ID is checked against the session's own account only, so this
cannot be used to test whether some other account's login ID is valid. A
wrong one counts as a failed login against the same limiter as sign-in.
"""

from datetime import timedelta

from backend.auth.credentials import normalize_login_id, verify_login_id
from backend.auth.sessions import _hash_token
from backend.db import migrate

REAUTH_WINDOW = timedelta(minutes=5)


class ReauthRequired(Exception):
    """The action needs a login ID re-entered on this session first."""


class WrongLoginId(Exception):
    """The login ID does not belong to this session's account."""


def _session(conn, raw_token: str):
    return migrate.fetch_one(
        conn,
        "SELECT id, account_id, reauthenticated_at FROM sessions"
        " WHERE token_hash = %s AND revoked_at IS NULL",
        (_hash_token(raw_token),),
    )


def reauthenticate(conn, raw_token: str, login_id: str, *, clock) -> None:
    """Check the login ID against this session's account and, if it
    matches, record the moment on the session."""
    session = _session(conn, raw_token)
    if session is None:
        raise WrongLoginId()
    try:
        normalized = normalize_login_id(login_id)
    except ValueError:
        raise WrongLoginId() from None
    credential = migrate.fetch_one(
        conn,
        "SELECT verifier FROM login_credentials"
        " WHERE account_id = %s AND revoked_at IS NULL",
        (session["account_id"],),
    )
    if credential is None or not verify_login_id(normalized, credential["verifier"]):
        raise WrongLoginId()
    migrate.execute(
        conn,
        "UPDATE sessions SET reauthenticated_at = %s WHERE id = %s",
        (clock.now(), session["id"]),
    )


def require_recent(conn, raw_token: str, *, clock, window=REAUTH_WINDOW) -> None:
    """Refuse unless this session re-entered its login ID within the
    window. Called before the action, so a refusal changes nothing."""
    session = _session(conn, raw_token)
    if session is None or session["reauthenticated_at"] is None:
        raise ReauthRequired()
    if clock.now() - session["reauthenticated_at"] > window:
        raise ReauthRequired()
