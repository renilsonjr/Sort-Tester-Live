"""Catalog pins and persisted revision history boundaries."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import tempfile
import unittest

from backend.ranked_bank import BankValidationError, canonical_json_digest
from backend.ranked_bank.catalog import Catalog, load_catalog, load_reviewed_bank
from backend.tests.ranked_helpers import raw_bank, raw_question


def write_catalog_fixture(directory, payloads):
    directory = Path(directory)
    entries = []
    for index, payload in enumerate(payloads):
        filename = f'bank-{index}.json'
        (directory / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        entries.append(dict(revision=payload['bank_revision'], file=filename, sha256=canonical_json_digest(payload)))
    path = directory / 'manifest.json'
    path.write_text(json.dumps(dict(schema_version=1, banks=entries)), encoding='utf-8')
    return path


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ranked catalog ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def versions(self):
        first = raw_bank(raw_question('T1'), revision='fixture-v1')
        second = deepcopy(first)
        second['bank_revision'] = 'fixture-v2'
        return first, second

    def test_changed_content_cannot_reuse_question_revision(self):
        first, second = self.versions()
        second['questions'][0]['copy']['en']['explanation'] = 'Changed feedback.'
        with self.assertRaises(BankValidationError) as error:
            load_catalog(write_catalog_fixture(self.directory, [first, second]))
        self.assertEqual(error.exception.code, 'revision_reused')

    def test_new_question_revision_can_coexist_with_old(self):
        first, second = self.versions()
        second['questions'][0]['question_revision'] = 2
        second['questions'][0]['copy']['es']['explanation'] = 'Cambió.'
        catalog = load_catalog(write_catalog_fixture(self.directory, [first, second]))
        old = catalog.get('fixture-v1')
        self.assertEqual(catalog.get('fixture-v2').questions[0].question_revision, 2)
        self.assertEqual(old.questions[0].question_revision, 1)
        self.assertEqual(old.questions[0].text.es.explanation, 'Use YELLOW.')

    def test_identical_question_revision_can_coexist(self):
        catalog = load_catalog(write_catalog_fixture(self.directory, self.versions()))
        self.assertEqual(len(catalog.banks), 2)

    def test_duplicate_bank_revision_is_rejected(self):
        first, _ = self.versions()
        with self.assertRaises(BankValidationError) as error:
            load_catalog(write_catalog_fixture(self.directory, [first, first]))
        self.assertEqual(error.exception.code, 'invalid_schema')

    def test_manifest_pin_and_filename_are_checked(self):
        for field, value, code in [('sha256', '0' * 64, 'digest_mismatch'), ('sha256', 'xyz', 'invalid_schema'), ('revision', 'other', 'unknown_revision'), ('file', '../bank-0.json', 'invalid_schema'), ('file', '/tmp/bank.json', 'invalid_schema'), ('file', 'folder\\bank.json', 'invalid_schema'), ('file', 'bank.txt', 'invalid_schema')]:
            with self.subTest(field=field, value=value):
                path = write_catalog_fixture(self.directory, [self.versions()[0]])
                raw = json.loads(path.read_text(encoding='utf-8'))
                raw['banks'][0][field] = value
                path.write_text(json.dumps(raw), encoding='utf-8')
                with self.assertRaises(BankValidationError) as error:
                    load_catalog(path)
                self.assertEqual(error.exception.code, code)

    def test_manifest_schema_is_strict(self):
        for raw in [dict(schema_version=True, banks=[]), dict(schema_version=1), dict(schema_version=1, banks=[], extra=1), dict(schema_version=1, banks=[dict(revision='x', file='a.json')]), dict(schema_version=1, banks={})]:
            with self.subTest(raw=raw):
                path = self.directory / 'manifest.json'
                path.write_text(json.dumps(raw), encoding='utf-8')
                with self.assertRaises(BankValidationError):
                    load_catalog(path)

    def test_duplicate_manifest_json_members_are_rejected(self):
        path = self.directory / 'manifest.json'
        path.write_text('{"schema_version":1,"schema_version":1,"banks":[]}', encoding='utf-8')
        with self.assertRaises(BankValidationError) as error:
            load_catalog(path)
        self.assertEqual(error.exception.code, 'invalid_json')

    def test_unknown_revision_never_falls_back(self):
        catalog = load_catalog(write_catalog_fixture(self.directory, [self.versions()[0]]))
        for get in [catalog.get, load_reviewed_bank]:
            with self.assertRaises(BankValidationError) as error:
                get('missing')
            self.assertEqual(error.exception.code, 'unknown_revision')

    def test_loading_from_cwd_with_spaces(self):
        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            bank = load_reviewed_bank()
        finally:
            os.chdir(previous)
        self.assertEqual(bank.revision, 'ranked-routes-v1')
        self.assertEqual(len(bank.questions), 283)

    def test_catalog_has_no_mutable_nested_data(self):
        banks = [load_reviewed_bank()]
        catalog = Catalog(banks)
        banks.clear()
        self.assertEqual(len(catalog.banks), 1)
        with self.assertRaises(FrozenInstanceError):
            catalog.banks = ()
        with self.assertRaises(FrozenInstanceError):
            catalog.banks[0].questions[0].text.en.prompt = 'changed'
        self.assertIsInstance(catalog.banks[0].questions[0].rule.parts, tuple)
