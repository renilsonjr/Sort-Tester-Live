import dataclasses
import tempfile
import unittest
from backend.tests.ranked_helpers import *
from backend.ranked_bank.loading import load_bank
from backend.ranked_bank.models import BankValidationError
from backend.ranked_bank.identity import question_content_digest

class LoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.directory=self.temp.name
    def load(self,data):
        path,pin=write_fixture(self.directory,data)
        return load_bank(path,expected_revision='fixture-v1',expected_sha256=pin)
    def test_identity_is_stable_across_service_aliases(self):
        for alias in ('GND','GRD','Ground'):
            self.assertEqual(stable_question_id(Context(alias,'ordinary'),RouteRule('prefix_range',('100','108'))),'rq-gnd-prefix_range-7be00a20fe02bb8c8c34bf2c34e1b8a967c314c55d59832135e11624e4201cbe')
    def test_missing_spanish_feedback_is_rejected(self):
        data=raw_bank(raw_question('T1')); del data['questions'][0]['copy']['es']['explanation']
        with self.assertRaises(BankValidationError) as e: self.load(data)
        self.assertEqual(e.exception.code,'invalid_schema')
    def test_nested_records_are_immutable(self):
        data=raw_bank(raw_question('T1')); q=self.load(data).questions[0]
        for obj,field in ((q,'difficulty'),(q.text.en,'prompt')):
            with self.assertRaises(dataclasses.FrozenInstanceError): setattr(obj,field,'other')
        data['questions'][0]['rule']['parts'][0]='999'; self.assertEqual(q.rule.parts,('100','108'))
    def test_lf_crlf_have_same_digest(self):
        data=raw_bank(raw_question('T1')); path,pin=write_fixture(self.directory,data)
        path.write_bytes(json.dumps(data,indent=2).replace('\n','\r\n').encode())
        self.assertEqual(load_bank(path,expected_revision='fixture-v1',expected_sha256=pin).sha256,pin)
    def test_leading_zero_range_is_preserved(self):
        q=self.load(raw_bank(raw_question('T1',parts=('010','024'),routing_code='010'))).questions[0]
        self.assertEqual(q.rule.parts,('010','024')); self.assertEqual(q.presentation.routing_code,'010')
    def test_duplicate_alias_meaning_is_rejected(self):
        with self.assertRaises(BankValidationError) as e: self.load(raw_bank(raw_question('A'),raw_question('B',service='Ground',routing_code='105',region_label='Other')))
        self.assertEqual(e.exception.code,'duplicate_canonical')
    def test_strict_json_rejects_duplicate_members_and_nonfinite(self):
        for body in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}','{"a":1e999}'):
            path=Path(self.directory)/'bank.json'; path.write_text(body)
            with self.assertRaises(BankValidationError) as e: load_bank(path,expected_revision='fixture-v1',expected_sha256='x')
            self.assertEqual(e.exception.code,'invalid_json')
    def test_schema_rejects_unknown_fields_bool_revisions_and_CHECK(self):
        for field,value in (('extra',1),('question_revision',True),('correct_belt','CHECK')):
            data=raw_bank(raw_question('A')); data['questions'][0][field]=value
            with self.assertRaises(BankValidationError) as e:self.load(data)
            self.assertEqual(e.exception.code,'invalid_schema')
    def test_bad_pin_is_rejected(self):
        path,pin=write_fixture(self.directory,raw_bank(raw_question('A')))
        with self.assertRaises(BankValidationError) as e:load_bank(path,expected_revision='fixture-v1',expected_sha256='bad')
        self.assertEqual(e.exception.code,'digest_mismatch')
    def test_labels_copy_affect_content_not_identity(self):
        a=self.load(raw_bank(raw_question('A'))).questions[0]
        data=raw_bank(raw_question('A',region_label='Other')); data['questions'][0]['copy']['en']['prompt']='Changed question'
        b=self.load(data).questions[0]
        self.assertEqual(a.canonical_id,b.canonical_id); self.assertNotEqual(question_content_digest(a),question_content_digest(b))
    def test_leaf_references_resolve_independently_of_order(self):
        def fixture(reverse):
            broad=raw_question('A',parts=('100','199'),exclusion_refs=('B',))
            leaf=raw_question('B',kind='exact_literal',parts=('148 1',),routing_code='148 1')
            return raw_bank(*( (leaf,broad) if reverse else (broad,leaf)))
        a=by_ref(self.load(fixture(False)),'A'); b=by_ref(self.load(fixture(True)),'A')
        self.assertEqual(a.canonical_id,b.canonical_id)
        self.assertEqual(a.exclusions,(Exclusion('B',RouteRule('exact_literal',('148 1',))),))
    def test_invalid_references_are_rejected(self):
        for case in ('missing','self','nested','cycle','cross'):
            a=raw_question('A',parts=('100','199'),exclusion_refs=('B',))
            b=raw_question('B',kind='exact_literal',parts=('148 1',))
            data=raw_bank(a,b)
            if case=='missing': a['exclusion_refs']=['Z']
            elif case=='self': a['exclusion_refs']=['A']
            elif case in ('nested','cycle'): b['exclusion_refs']=['A']
            else: b['context']['service']='NDA'
            with self.assertRaises(BankValidationError) as e:self.load(data)
            self.assertEqual(e.exception.code,'invalid_reference',case)
    def test_primitive_rules_and_context_are_strict(self):
        for rule in (('prefix_range',('024','010')),('prefix_range',('10','024')),('prefix_range',('١٠٠','١٠٨')),('qualified_code',('100','12')),('any_route',('100',))):
            with self.assertRaises(BankValidationError): RouteRule(*rule)
        with self.assertRaises(BankValidationError): Context('GND','EAM')
    def test_missing_file_and_invalid_utf8(self):
        path=Path(self.directory)/'missing.json'
        with self.assertRaises(BankValidationError) as e:load_bank(path,expected_revision='fixture-v1',expected_sha256='x')
        self.assertEqual(e.exception.code,'invalid_schema')
        path.write_bytes(b'\xff')
        with self.assertRaises(BankValidationError) as e:load_bank(path,expected_revision='fixture-v1',expected_sha256='x')
        self.assertEqual(e.exception.code,'invalid_json')
    def test_wrong_revision_and_id_are_rejected(self):
        data=raw_bank(raw_question('A')); data['questions'][0]['canonical_id']='wrong'
        with self.assertRaises(BankValidationError) as e:self.load(data)
        self.assertEqual(e.exception.code,'invalid_schema')
        path,pin=write_fixture(self.directory,raw_bank(raw_question('A')))
        with self.assertRaises(BankValidationError) as e:load_bank(path,expected_revision='other',expected_sha256=pin)
        self.assertEqual(e.exception.code,'unknown_revision')
