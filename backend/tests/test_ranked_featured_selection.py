"""Every Ranked quiz includes at least one SORT CHANGE route, so the owner's
recently changed belts (TX BLACK, IL and NY) are always practiced, while the
5/5/5 difficulty quota, uniqueness and non-overlap guarantees are preserved and
a bank without any featured route still selects normally."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from random import Random

from backend.ranked_bank import load_reviewed_bank
from backend.ranked_bank.coverage import rules_overlap
from backend.ranked_bank.selection import select_assignment, FEATURED_PROVENANCE
from backend.tests.ranked_helpers import make_unconstrained_bank


def is_featured(question):
    return question.source.provenance == FEATURED_PROVENANCE


class FeaturedSelectionTests(unittest.TestCase):
    def setUp(self):
        self.bank = load_reviewed_bank()

    def test_every_assignment_includes_a_sort_change_route(self):
        for seed in range(80):
            snapshot = select_assignment(self.bank, rng=Random(seed))
            self.assertTrue(
                any(is_featured(q) for q in snapshot.questions),
                f'seed {seed} drew no SORT CHANGE route',
            )

    def test_quota_uniqueness_and_non_overlap_are_preserved(self):
        for seed in range(40):
            snapshot = select_assignment(self.bank, rng=Random(seed))
            self.assertEqual(len(snapshot.questions), 15)
            self.assertEqual(
                Counter(q.difficulty for q in snapshot.questions),
                dict(Easy=5, Medium=5, Hard=5),
            )
            self.assertEqual(len({q.canonical_id for q in snapshot.questions}), 15)
            for i, q in enumerate(snapshot.questions):
                for other in snapshot.questions[i + 1:]:
                    self.assertFalse(rules_overlap(q, other))

    def test_which_featured_route_appears_varies(self):
        seen = set()
        for seed in range(100):
            snapshot = select_assignment(self.bank, rng=Random(seed))
            seen |= {q.source.review_ref for q in snapshot.questions if is_featured(q)}
        self.assertGreater(len(seen), 1, 'the forced route should not always be the same one')

    def test_bank_without_featured_routes_still_selects(self):
        with tempfile.TemporaryDirectory() as directory:
            bank = make_unconstrained_bank(Path(directory))
            snapshot = select_assignment(bank, rng=Random(0))
            self.assertEqual(len(snapshot.questions), 15)
            self.assertFalse(any(is_featured(q) for q in snapshot.questions))


if __name__ == '__main__':
    unittest.main()
