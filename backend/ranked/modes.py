"""The shape of each kind of ranked attempt (issue #8).

The attempt engine reads these settings instead of assuming one quiz shape, so
a later kind of attempt (prize tie-breaks, #24) can bring its own without the
engine being rewritten. Tie-break settings depend on the round and arrived
with #24.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModeSettings:
    question_count: int    # questions in one attempt
    question_seconds: int  # server deadline for each question, from first send


SETTINGS = {
    "normal": ModeSettings(question_count=15, question_seconds=10),
    "promotion": ModeSettings(question_count=15, question_seconds=10),
}


# Prize tie-breaks (#24): five questions, and the clock tightens with the
# round. The record words it by tier -- Challenger rounds and lower-rank
# rounds 1-3 at five seconds, lower-rank round 4 at four, round 5 at three --
# but Challenger has at most three rounds, so in practice the seconds depend
# on the round number alone.
TIEBREAK_QUESTIONS = 5
TIEBREAK_SECONDS = {1: 5, 2: 5, 3: 5, 4: 4, 5: 3}


def settings_for(mode: str, tiebreak_round: int | None = None) -> ModeSettings:
    """Return the settings for ``mode``; raise ``ValueError`` if it has none.

    A tie-break needs its round number, because the seconds depend on it.
    """
    if mode == "tiebreak":
        if tiebreak_round not in TIEBREAK_SECONDS:
            raise ValueError(f"no tie-break settings for round: {tiebreak_round!r}")
        return ModeSettings(
            question_count=TIEBREAK_QUESTIONS,
            question_seconds=TIEBREAK_SECONDS[tiebreak_round],
        )
    try:
        return SETTINGS[mode]
    except KeyError:
        raise ValueError(f"no attempt settings for mode: {mode!r}") from None
