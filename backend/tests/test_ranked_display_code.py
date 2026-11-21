"""The routing code shown for a range question varies across its valid
prefixes, so the same route is not always quizzed on one example, while the
answer (the belt) and every non-range example stay exactly as reviewed."""
import tempfile
import unittest
from random import Random

from backend.tests.ranked_helpers import raw_question, raw_bank, write_fixture, by_ref
from backend.ranked_bank.loading import load_bank
from backend.ranked_bank.coverage import available_range_prefixes
from backend.ranked_bank.display import displayed_routing_code, routing_code_for


def load(*questions):
    with tempfile.TemporaryDirectory() as directory:
        path, digest = write_fixture(directory, raw_bank(*questions))
        return load_bank(path, expected_revision='fixture-v1', expected_sha256=digest)


class DisplayCodeTests(unittest.TestCase):
    def range_question(self):
        # TX 750-779, the Sort-change BLACK range, shown as "750" when reviewed.
        return load(raw_question('G', parts=('750', '779'), correct_belt='BLACK',
                                 routing_code='750', region_label='TX')).questions[0]

    def test_range_code_is_always_a_valid_prefix(self):
        q = self.range_question()
        allowed = set(available_range_prefixes(q))
        for seed in range(50):
            self.assertIn(displayed_routing_code(q, rng=Random(seed)), allowed)

    def test_range_code_varies_across_the_span(self):
        q = self.range_question()
        seen = {displayed_routing_code(q, rng=Random(seed)) for seed in range(100)}
        self.assertGreater(len(seen), 1)
        self.assertNotEqual(seen, {'750'})

    def test_same_attempt_and_seq_is_stable(self):
        q = self.range_question()
        self.assertEqual(
            routing_code_for(q, attempt_id=4242, seq=3),
            routing_code_for(q, attempt_id=4242, seq=3),
        )

    def test_different_attempts_can_differ(self):
        q = self.range_question()
        codes = {routing_code_for(q, attempt_id=a, seq=1) for a in range(200)}
        self.assertGreater(len(codes), 1)

    def test_non_range_example_is_left_exactly_as_reviewed(self):
        bank = load(
            raw_question('P', parts=('148', '149'), routing_code='149', exclusion_refs=('X',)),
            raw_question('X', kind='qualified_code', parts=('148', '1'),
                         routing_code='148 1', correct_belt='BLUE'),
        )
        x = by_ref(bank, 'X')
        self.assertEqual(displayed_routing_code(x, rng=Random(0)), '148 1')
        self.assertEqual(routing_code_for(x, attempt_id=9, seq=9), '148 1')

    def test_excluded_prefix_is_never_shown(self):
        # 370-385 with a 376-378 range exception: those prefixes must never
        # appear as the shown code, or the quiz would teach the wrong belt.
        bank = load(
            raw_question('P', parts=('370', '385'), routing_code='370', exclusion_refs=('X',)),
            raw_question('X', parts=('376', '378'), routing_code='376', correct_belt='BLUE'),
        )
        p = by_ref(bank, 'P')
        shown = {displayed_routing_code(p, rng=Random(seed)) for seed in range(300)}
        self.assertFalse(shown & {'376', '377', '378'})


if __name__ == '__main__':
    unittest.main()
