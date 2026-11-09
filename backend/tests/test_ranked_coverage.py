import tempfile
import unittest
from backend.tests.ranked_helpers import raw_question, raw_bank, write_fixture, by_ref
from backend.ranked_bank.loading import load_bank
from backend.ranked_bank.coverage import rules_overlap, available_range_prefixes
from backend.ranked_bank.models import BankValidationError

class CoverageTests(unittest.TestCase):
    def load(self,*questions):
        with tempfile.TemporaryDirectory() as directory:
            path,digest=write_fixture(directory,raw_bank(*questions))
            return load_bank(path,expected_revision='fixture-v1',expected_sha256=digest)

    def test_exact_exception_can_cross_printed_region_labels(self):
        bank=self.load(raw_question('P',parts=('832','839'),correct_belt='BROWN',exclusion_refs=('X',),routing_code='832',region_label='ID'),raw_question('X',kind='exact_literal',parts=('833 9-7',),correct_belt='ORANGE',routing_code='833 9-7',region_label='NV'))
        self.assertFalse(rules_overlap(*bank.questions))
        self.assertNotIn('833',available_range_prefixes(by_ref(bank,'P')))
        self.assertIn('832',available_range_prefixes(by_ref(bank,'P')))

    def test_qualified_code_exclusion_preserves_zero_and_digit(self):
        bank=self.load(raw_question('P',parts=('148','149'),exclusion_refs=('X',),routing_code='149'),raw_question('X',kind='qualified_code',parts=('148','1'),routing_code='148 1',correct_belt='BLUE'))
        self.assertFalse(rules_overlap(*bank.questions))
        self.assertEqual(('149',),available_range_prefixes(bank.questions[0]))
        bank=self.load(raw_question('Z',kind='qualified_code',parts=('010','0'),routing_code='010 0'))
        self.assertEqual(('010','0'),bank.questions[0].rule.parts)

    def test_TN_range_exception_subtracts_full_prefixes(self):
        bank=self.load(raw_question('P',parts=('370','385'),routing_code='370',exclusion_refs=('X',)),raw_question('X',parts=('376','378'),routing_code='376',correct_belt='BLUE'))
        self.assertFalse(rules_overlap(*bank.questions))
        self.assertNotIn('378',available_range_prefixes(bank.questions[0]))

    def test_literal_is_never_parsed_as_endpoints(self):
        q=self.load(raw_question('X',kind='exact_literal',parts=('575 3-6',),routing_code='575 3-6')).questions[0]
        self.assertEqual(('575 3-6',),q.rule.parts)

    def test_same_answer_partial_ranges_overlap(self):
        b=self.load(raw_question('A',service='2DA',parts=('609','619'),routing_code='609'),raw_question('B',service='2DA',parts=('609','629'),routing_code='629'))
        self.assertTrue(rules_overlap(*b.questions))

    def test_contexts_are_distinct(self):
        ordinary=self.load(raw_question('A')).questions[0]
        for kwargs in (dict(service='NDA'),dict(mode='+1',kind='any_route',parts=(),correct_belt='PURPLE'),dict(service='NDA',mode='EAM',kind='any_route',parts=()),dict(mode='suffix:1S',kind='suffix',parts=('1S',),routing_code='100 1S')):
            other=self.load(raw_question('B',**kwargs)).questions[0]
            self.assertFalse(rules_overlap(ordinary,other))

    def test_plus_one_is_not_NY_restricted(self):
        self.load(raw_question('A',mode='+1',kind='any_route',parts=(),routing_code='900',region_label='CA',correct_belt='PURPLE'))

    def test_reject_mixed_markers(self):
        for kwargs in (dict(mode='+1',routing_code='109 2S'),dict(mode='EAM',service='NDA',routing_code='109 1S'),dict(mode='EAM')):
            with self.assertRaises(BankValidationError):
                self.load(raw_question('A',kind='any_route',parts=(),**kwargs))

    def test_unsafe_prefix_example_is_rejected(self):
        with self.assertRaises(BankValidationError) as caught:
            self.load(raw_question('P',parts=('148','149'),routing_code='148',exclusion_refs=('X',)),raw_question('X',kind='qualified_code',parts=('148','1'),routing_code='148 1',correct_belt='BLUE'))
        self.assertEqual('invalid_presentation',caught.exception.code)

    def test_exclusion_must_be_contained_and_leaf(self):
        with self.assertRaises(BankValidationError):
            self.load(raw_question('P',exclusion_refs=('X',)),raw_question('X',parts=('200','209'),routing_code='200'))

    def test_endpoints_disjoint_and_literal_labels(self):
        a=self.load(raw_question('A',parts=('100','108'))).questions[0]
        for start, expected in (('108',True),('109',False)):
            b=self.load(raw_question('B',parts=(start,'110'),routing_code=start)).questions[0]
            self.assertEqual(expected,rules_overlap(a,b))
        a=self.load(raw_question('A',kind='exact_literal',parts=('575 3-6',),routing_code='575 3-6')).questions[0]
        b=self.load(raw_question('B',kind='exact_literal',parts=('575 3-6',),routing_code='575 3-6',region_label='SD')).questions[0]
        self.assertTrue(rules_overlap(a,b))

    def test_different_answer_overlap_rejected(self):
        with self.assertRaises(BankValidationError) as caught:
            self.load(raw_question('A'),raw_question('B',parts=('108','110'),routing_code='110',correct_belt='BLUE'))
        self.assertEqual('invalid_coverage',caught.exception.code)

    def test_exact_exclusion_does_not_erase_prefix_coverage(self):
        bank=self.load(raw_question('P',parts=('148','149'),exclusion_refs=('X',),routing_code='149'),raw_question('X',kind='qualified_code',parts=('148','1'),routing_code='148 1',correct_belt='BLUE'))
        other=self.load(raw_question('Y',kind='qualified_code',parts=('148','2'),routing_code='148 2')).questions[0]
        prefix=self.load(raw_question('R',parts=('148','148'),routing_code='148')).questions[0]
        self.assertTrue(rules_overlap(bank.questions[0],other))
        self.assertTrue(rules_overlap(bank.questions[0],prefix))

    def test_named_destination_is_separate_domain(self):
        numeric=self.load(raw_question('P')).questions[0]
        named=self.load(raw_question('N',kind='named_destination',parts=('CANADA',),routing_code=None,named_destination='CANADA')).questions[0]
        self.assertFalse(rules_overlap(numeric,named))

    def test_suffix_and_named_presentation_must_agree(self):
        for kwargs in (dict(mode='suffix:1S',kind='suffix',parts=('1S',),routing_code='100 2S'),dict(kind='named_destination',parts=('CANADA',),routing_code='100',named_destination='CANADA')):
            with self.assertRaises(BankValidationError):
                self.load(raw_question('A',**kwargs))

    def test_same_answer_exclusion_still_makes_prefix_example_unsafe(self):
        bank=self.load(raw_question('P',parts=('148','149'),exclusion_refs=('X',),routing_code='149'),raw_question('X',kind='qualified_code',parts=('148','1'),routing_code='148 1'))
        self.assertEqual(('149',),available_range_prefixes(bank.questions[0]))
        self.assertFalse(rules_overlap(*bank.questions))
