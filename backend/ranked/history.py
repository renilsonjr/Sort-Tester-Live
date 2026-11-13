"""Account-private ranked history (issue #23).

A player's own settled attempts, by season. Decision 12 keeps completed and
launch-ended Pre-Season attempts for a private "pre season history": only the
account itself may read it, with no administrator exception. This module
therefore takes one account id and never looks up any other.
"""
from backend.db import migrate

PHASES = ("pre_season", "official")


def account_history(conn, account_id, phase=None) -> list[dict]:
    """Return the account's settled attempts, newest first.

    ``phase`` limits the list to ``'pre_season'`` or ``'official'``. An
    attempt ended at launch appears with ``final_outcome='launch_reset'`` and
    a zero adjustment; nothing is invented for answers never given.
    """
    if phase is not None and phase not in PHASES:
        raise ValueError(f"unknown season phase: {phase!r}")
    sql = (
        "SELECT a.id AS attempt_id, s.phase, s.label, a.mode, st.final_outcome,"
        " st.raw_score, st.adjustment, h.points_before, h.points_after,"
        " h.badge_before, h.badge_after, st.settled_at"
        " FROM settlements st"
        " JOIN attempts a ON a.id = st.attempt_id"
        " JOIN seasons s ON s.id = st.season_id"
        " JOIN balance_history h ON h.settlement_id = st.attempt_id"
        " WHERE a.account_id = %s"
    )
    params = [account_id]
    if phase is not None:
        sql += " AND s.phase = %s"
        params.append(phase)
    return migrate.fetch_all(
        conn, sql + " ORDER BY st.settled_at DESC, a.id", tuple(params)
    )
