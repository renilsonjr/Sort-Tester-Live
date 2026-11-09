import contextlib
from collections import Counter
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
from random import Random
import tempfile
import unittest
from unittest.mock import patch

from backend.ranked_bank import load_reviewed_bank, BankUnavailableError, AssignmentSnapshot
from backend.ranked_bank.coverage import rules_overlap, validate_presentation
from backend.ranked_bank.selection import select_assignment, serialize_assignment
from backend.ranked_bank import check
from backend.tests.ranked_helpers import make_trap_bank, make_unavailable_bank, make_unconstrained_bank


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def assert_assignment(self, snapshot):
        self.assertEqual(len(snapshot.questions), 15)
        self.assertEqual(Counter(q.difficulty for q in snapshot.questions), dict(Easy=5, Medium=5, Hard=5))
        self.assertEqual(len({q.canonical_id for q in snapshot.questions}), 15)
        for i, q in enumerate(snapshot.questions):
            validate_presentation(q)
            for other in snapshot.questions[i + 1:]:
                self.assertFalse(rules_overlap(q, other))

    def test_complete_search_does_not_get_stuck_on_a_greedy_choice(self):
        for seed in range(20):
            snapshot = select_assignment(make_trap_bank(self.directory), rng=Random(seed))
            self.assert_assignment(snapshot)
            self.assertNotIn('TRAP', {q.source.review_ref for q in snapshot.questions})

    def test_no_partial_assignment_when_counts_are_incompatible(self):
        with self.assertRaises(BankUnavailableError):
            select_assignment(make_unavailable_bank(self.directory), rng=Random(42))

    def test_fewer_than_five_in_a_category_is_unavailable(self):
        bank = make_unconstrained_bank(self.directory)
        with self.assertRaises(BankUnavailableError):
            select_assignment(replace(bank, questions=tuple(q for q in bank.questions if q.source.review_ref not in ('E1', 'E2'))))

    def test_seeded_selection_is_reproducible(self):
        bank = load_reviewed_bank()
        self.assertEqual(select_assignment(bank, rng=Random(42)), select_assignment(bank, rng=Random(42)))

    def test_inputs_are_not_shuffled_or_mutated(self):
        bank = load_reviewed_bank()
        before = asdict(bank)
        select_assignment(bank, rng=Random(42))
        self.assertEqual(asdict(bank), before)

    def test_unique_ids_and_disjoint_effective_coverage(self):
        self.assert_assignment(select_assignment(load_reviewed_bank(), rng=Random(42)))

    def test_real_V1_over_50_seeds(self):
        bank = load_reviewed_bank()
        memberships = set()
        for seed in range(50):
            snapshot = select_assignment(bank, rng=Random(seed))
            self.assert_assignment(snapshot)
            self.assertTrue(all(q in bank.questions for q in snapshot.questions))
            memberships.add(frozenset(q.canonical_id for q in snapshot.questions))
        self.assertGreater(len(memberships), 1)

    def test_every_candidate_is_reachable_in_unconstrained_6_each_fixture(self):
        bank = make_unconstrained_bank(self.directory)
        reached = {q.canonical_id for seed in range(100) for q in select_assignment(bank, rng=Random(seed)).questions}
        self.assertEqual(reached, {q.canonical_id for q in bank.questions})

    def test_old_snapshot_survives_new_bank_version(self):
        bank = load_reviewed_bank()
        snapshot = select_assignment(bank, rng=Random(42))
        before = serialize_assignment(snapshot)
        updated = replace(bank, revision='v2', sha256='f' * 64, questions=tuple(replace(q, question_revision=2) for q in bank.questions))
        select_assignment(updated, rng=Random(42))
        self.assertEqual(serialize_assignment(snapshot), before)
        with self.assertRaises(AttributeError):
            snapshot.questions[0].difficulty = 'Hard'

    def test_serialized_snapshot_is_a_defensive_copy(self):
        snapshot = select_assignment(load_reviewed_bank(), rng=Random(42))
        before = serialize_assignment(snapshot)
        changed = serialize_assignment(snapshot)
        changed['questions'][0]['text']['en']['prompt'] = 'changed'
        changed['questions'].clear()
        self.assertEqual(serialize_assignment(snapshot), before)
        self.assertIsInstance(before['questions'], list)
        self.assertIn('correct_belt', before['questions'][0])

    def test_approved_code_specific_feedback_stays_paired(self):
        bank = load_reviewed_bank()
        # Exhaustively verify the internal snapshot preserves every reviewed pair,
        # including the twenty approved code-specific examples (not just a seed's subset).
        snapshot = AssignmentSnapshot(bank.revision, bank.sha256, bank.source_revision, bank.questions)
        serialized = serialize_assignment(snapshot)
        for q, stored in zip(bank.questions, serialized['questions'], strict=True):
            self.assertEqual(stored['presentation'], asdict(q.presentation))
            self.assertEqual(stored['text'], asdict(q.text))
        source_path = Path(__file__).resolve().parents[2] / 'docs/superpowers/specs/2026-11-08-ranked-full-chart-review.json'
        source = json.loads(source_path.read_text(encoding='utf-8'))
        by_ref = {q['source']['review_ref']: q for q in serialized['questions']}
        examples = [entry for entry in source['entries'] if 'rangeExampleReview' in entry]
        self.assertEqual(len(examples), 20)
        for entry in examples:
            stored = by_ref[entry['approvedReview']]
            self.assertEqual(stored['presentation']['routing_code'], entry['rangeExampleReview']['displayedRoutingCode'])
            for lang in ('en', 'es'):
                self.assertEqual(stored['text'][lang], {key: entry['wording'][lang][key] for key in ('prompt', 'explanation')})
        for seed in range(50):
            for selected in select_assignment(bank, rng=Random(seed)).questions:
                self.assertEqual(selected, next(q for q in bank.questions if q.canonical_id == selected.canonical_id))

    def test_check_cli_returns_counts_and_no_partial_output_on_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(check.main(['--revision', 'ranked-routes-v1', '--seed', '42']), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result['question_count'], 15)
        self.assertEqual(result['counts'], dict(Easy=5, Medium=5, Hard=5))
        self.assertNotIn('correct_belt', out.getvalue())
        self.assertEqual(len(result['selected_review_refs']), 15)
        for failure in (BankUnavailableError('unavailable'),):
            out, err = io.StringIO(), io.StringIO()
            with patch.object(check, 'load_reviewed_bank', side_effect=failure), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(check.main([]), 1)
            self.assertEqual(out.getvalue(), '')
            self.assertTrue(err.getvalue())
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(check.main(['--revision', 'missing']), 1)
        self.assertEqual(out.getvalue(), '')
        self.assertTrue(err.getvalue())
