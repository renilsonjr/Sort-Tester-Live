"""The four belts offered for one question.

Owner decision 2026-11-15: Ranked, promotion and tie-break questions all
offer four belts -- the right one and three others -- drawn with the
server's randomness and **stored**, never derived from anything the player
can see (the same reasoning as migration 0033: since the three wrong belts
come from "every belt but the right one", a formula keyed on anything
visible would let a player try each candidate answer and read the options
back, which leaks the answer).

Shared by the engine (ordinary and promotion attempts, migration 0035) and
by :mod:`backend.ranked.tiebreaks` (tie-break rounds, where the same four
must also be shared by everyone in the round rather than drawn per player).
"""
import secrets

OPTIONS_PER_QUESTION = 4

# Unpredictable rather than reproducible: a player who could work out a
# question's options from anything else would have them before asking.
SYSTEM_RANDOM = secrets.SystemRandom()


def all_belts(bank) -> list:
    """Every belt the bank routes to, in a fixed order."""
    return sorted({q.correct_belt for q in bank.questions})


def draw_options(correct, belts, random_=None) -> list:
    """The right belt and three others drawn at random, in random order.

    A bank with fewer than four belts to draw from yields fewer options
    rather than raising: the reviewed bank routes to nine, so production
    always gets four, but a bank too small to fill them is a content
    problem to see on a screen, not a reason for starting a quiz to crash.
    """
    random_ = random_ or SYSTEM_RANDOM
    others = [b for b in belts if b != correct]
    take = min(len(others), OPTIONS_PER_QUESTION - 1)
    options = random_.sample(others, take) + [correct]
    random_.shuffle(options)
    return options
