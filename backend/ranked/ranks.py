"""Rank badges, point caps and the promotion entry rule (issue #8).

Pure functions over a points total; no database. The attempt engine uses them
to gate which kind of attempt may start, and scoring (#9) reuses them.

One balance controls rank. Each capped badge ends at its cap; passing a cap is
only possible through a perfect promotion attempt, which sets cap + 1.
"""

# (badge, cap) in rising order. Challenger sits above the last cap, uncapped.
CAPS = (("Iron", 1000), ("Bronze", 2000), ("Silver", 3000), ("Gold", 4000))
TOP_BADGE = "Challenger"

NORMAL = "normal"
PROMOTION = "promotion"


def badge_for(points: int) -> str:
    """Return the badge whose bracket holds ``points`` (negative totals are Iron)."""
    for badge, cap in CAPS:
        if points <= cap:
            return badge
    return TOP_BADGE


def cap_for(badge: str) -> int | None:
    """Return the badge's point cap, or ``None`` for the uncapped top badge."""
    return dict(CAPS).get(badge)


def entry_mode(points: int) -> str:
    """Return the only kind of Ranked attempt this total may start.

    Exactly at a badge's cap the only entry is a promotion attempt; anywhere
    else, including Challenger, it is an ordinary one.
    """
    if any(points == cap for _, cap in CAPS):
        return PROMOTION
    return NORMAL
