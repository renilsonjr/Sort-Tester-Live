"""The shape of each kind of ranked attempt (issue #8).

The attempt engine reads these settings instead of assuming one quiz shape, so
a later kind of attempt (prize tie-breaks, #24) can bring its own without the
engine being rewritten. Only the kinds the engine can start today are listed;
tie-break settings depend on badge tier and round and arrive with #24.
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


def settings_for(mode: str) -> ModeSettings:
    """Return the settings for ``mode``; raise ``ValueError`` if it has none."""
    try:
        return SETTINGS[mode]
    except KeyError:
        raise ValueError(f"no attempt settings for mode: {mode!r}") from None
