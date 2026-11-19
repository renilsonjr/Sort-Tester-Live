"""What routing code a question is shown with.

A range question (`prefix_range`) is quizzed on a single example code in the
reviewed bank, so the same route always appears as the same number. Here the
shown code is drawn from the range's valid prefixes instead, which keeps the
Ranked game dynamic without touching the answer: the belt, the copy and every
non-range example stay exactly as reviewed, and the draw is deterministic per
attempt and position, so a reload shows the same code and nothing is stored.
"""
import hashlib
from random import Random

from backend.ranked_bank.coverage import available_range_prefixes


def displayed_routing_code(question, *, rng: Random) -> str | None:
    """The code to show for ``question``, drawn with ``rng`` for range rules.

    For a ``prefix_range`` rule the code is one of the range's valid prefixes
    (exclusions already removed by ``available_range_prefixes``). Every other
    rule keeps its reviewed ``presentation.routing_code`` unchanged. If a range
    somehow has no valid prefix, the reviewed example is used as a safe default.
    """
    if question.rule.kind == 'prefix_range':
        prefixes = available_range_prefixes(question)
        if prefixes:
            return rng.choice(prefixes)
    return question.presentation.routing_code


def _seed(attempt_id, seq) -> int:
    digest = hashlib.sha256(f'{attempt_id}:{seq}'.encode()).digest()
    return int.from_bytes(digest[:8], 'big')


def routing_code_for(question, *, attempt_id, seq) -> str | None:
    """The shown code for one question of one attempt, stable on every serve.

    The seed comes from the attempt and the question's position, so the same
    (attempt, seq) always yields the same code and different attempts vary it,
    with no dependence on Python's per-process hash randomization.
    """
    return displayed_routing_code(question, rng=Random(_seed(attempt_id, seq)))
