"""Ranked points maths (issue #9).

Turns the answers of one ended attempt into its result: raw score, applied
adjustment, and points and badge before and after. Pure arithmetic: no
database, no clock. Writing the result exactly once is the settlement step.

Rules are the owner's (decision record, Decisions 1-5): one capped balance,
the Quit penalty applied before the cap, the cap applied once to the final
result, and promotion replacing ordinary gains with cap + 1 on a perfect quiz.
"""
from dataclasses import dataclass

from backend.ranked import ranks

# difficulty -> (points when correct, points when wrong or timed out)
POINTS = {"easy": (10, -15), "medium": (20, -10), "hard": (30, -5)}
QUIT_PENALTY = -10

_PARTIAL_OUTCOMES = ("completed", "quit", "disconnect", "season_close")
_VOID_OUTCOMES = ("outage_void", "launch_reset")


@dataclass(frozen=True)
class Settlement:
    raw_score: int      # ordinary value of the answers, kept for history
    adjustment: int     # what was actually applied to the balance
    points_before: int
    points_after: int
    badge_before: str
    badge_after: str


def answer_points(difficulty: str, result: str | None) -> int:
    """Ordinary points for one question. Unanswered (``None``) scores 0."""
    try:
        correct, missed = POINTS[difficulty]
    except KeyError:
        raise ValueError(f"unknown difficulty: {difficulty!r}") from None
    if result is None:
        return 0
    if result == "correct":
        return correct
    if result in ("wrong", "timeout"):
        return missed
    raise ValueError(f"unknown answer result: {result!r}")


def raw_score(answers) -> int:
    """Sum of ordinary points over ``(difficulty, result)`` pairs."""
    return sum(answer_points(difficulty, result) for difficulty, result in answers)


def settle(points_before: int, mode: str, final_outcome: str, answers) -> Settlement:
    """Compute the result of one ended attempt."""
    if mode not in (ranks.NORMAL, ranks.PROMOTION):
        raise ValueError(f"unknown attempt mode: {mode!r}")
    if final_outcome not in _PARTIAL_OUTCOMES + _VOID_OUTCOMES:
        raise ValueError(f"unknown final outcome: {final_outcome!r}")
    answers = list(answers)
    raw = raw_score(answers)
    badge_before = ranks.badge_for(points_before)
    cap = ranks.cap_for(badge_before)

    if final_outcome in _VOID_OUTCOMES:
        points_after = points_before
    elif mode == ranks.PROMOTION:
        points_after = _promotion_result(points_before, cap, final_outcome, answers)
    else:
        penalty = QUIT_PENALTY if final_outcome == "quit" else 0
        points_after = points_before + raw + penalty
        if cap is not None:
            # one cap on the whole result; overflow is discarded, never banked
            points_after = min(points_after, cap)

    return Settlement(
        raw_score=raw,
        adjustment=points_after - points_before,
        points_before=points_before,
        points_after=points_after,
        badge_before=badge_before,
        badge_after=ranks.badge_for(points_after),
    )


def _promotion_result(points_before, cap, final_outcome, answers) -> int:
    perfect = (
        final_outcome == "completed"
        and bool(answers)
        and all(result == "correct" for _, result in answers)
    )
    if perfect and cap is not None:
        return cap + 1  # replaces the ordinary +300
    # correct answers add nothing; mistakes deduct their ordinary amount
    deductions = sum(
        min(answer_points(difficulty, result), 0) for difficulty, result in answers
    )
    penalty = QUIT_PENALTY if final_outcome == "quit" else 0
    return points_before + deductions + penalty
