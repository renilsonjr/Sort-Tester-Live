"""Complete compatible quota selection; no attempt or score is created here."""
from dataclasses import asdict
import json
from random import Random, SystemRandom

from .coverage import rules_overlap
from .models import AssignmentSnapshot, Bank, BankUnavailableError

_DIFFICULTIES = ('Easy', 'Medium', 'Hard')

# Routes the owner changed in the SORT CHANGE pass carry this provenance. At
# least one of them is forced into every quiz so the new belts (TX BLACK, and
# the IL/NY moves) are always practiced, not left to the 2-in-284 draw odds.
FEATURED_PROVENANCE = 'owner-override-10'


def select_assignment(bank: Bank, *, rng: Random | None = None) -> AssignmentSnapshot:
    """Search all compatible choices if necessary, without mutating the bank.

    Candidate order comes only from tuple order and the supplied generator, never
    hash iteration. Failed states encode remaining candidates and quotas, which
    fully determine whether any completion exists.

    One featured (SORT CHANGE) route is pinned first and the rest of the quiz is
    filled around it, so every quiz holds at least one. A bank with no featured
    route, or one where no featured choice can be completed, falls back to the
    ordinary search unchanged.
    """
    generator = SystemRandom() if rng is None else rng
    pools = []
    for difficulty in _DIFFICULTIES:
        pool = [q for q in bank.questions if q.difficulty == difficulty]
        generator.shuffle(pool)
        pools.append(tuple(pool))
    failed = set()

    def search(eligible, quotas):
        if not any(quotas):
            return ()
        state = (eligible, quotas)
        if state in failed:
            return None
        if any(len(eligible[i]) < quotas[i] for i in range(3)):
            failed.add(state)
            return None
        # Fewest spare candidates first; deterministic Easy/Medium/Hard ties.
        category = min((i for i in range(3) if quotas[i]), key=lambda i: (len(eligible[i]) - quotas[i], i))
        candidates = eligible[category]
        for offset, index in enumerate(candidates):
            if len(candidates) - offset < quotas[category]:
                break
            question = pools[category][index]
            remaining = []
            for i in range(3):
                source = candidates[offset + 1:] if i == category else eligible[i]
                remaining.append(tuple(j for j in source if not rules_overlap(question, pools[i][j])))
            needed = list(quotas)
            needed[category] -= 1
            result = search(tuple(remaining), tuple(needed))
            if result is not None:
                return (question,) + result
        failed.add(state)
        return None

    def completed(result):
        selected = list(result)
        generator.shuffle(selected)
        return AssignmentSnapshot(bank.revision, bank.sha256, bank.source_revision, tuple(selected))

    # Pin one featured route, then fill the other 14 around it with the ordinary
    # search. Try the featured routes in a shuffled order so which one appears
    # varies, and fall through to an unforced selection if none can complete.
    featured = [
        (category, index)
        for category in range(3)
        for index, question in enumerate(pools[category])
        if question.source.provenance == FEATURED_PROVENANCE
    ]
    generator.shuffle(featured)
    for forced_category, forced_index in featured:
        forced = pools[forced_category][forced_index]
        eligible = tuple(
            tuple(
                index
                for index in range(len(pools[category]))
                if not (category == forced_category and index == forced_index)
                and not rules_overlap(forced, pools[category][index])
            )
            for category in range(3)
        )
        quotas = tuple(5 - (1 if category == forced_category else 0) for category in range(3))
        failed.clear()
        rest = search(eligible, quotas)
        if rest is not None:
            return completed((forced,) + rest)

    failed.clear()
    result = search(tuple(tuple(range(len(pool))) for pool in pools), (5, 5, 5))
    if result is None:
        raise BankUnavailableError('No compatible five-question set exists for every difficulty')
    return completed(result)


def serialize_assignment(snapshot: AssignmentSnapshot) -> dict[str, object]:
    """Return an independent, JSON-primitive internal snapshot including answers."""
    return json.loads(json.dumps(asdict(snapshot), ensure_ascii=False, allow_nan=False))
