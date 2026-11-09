"""Pinned immutable bank history; assets resolve relative to this module."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

from .identity import question_content_digest
from .loading import _constant, _fields, _float, _pairs, _validate_unicode, load_bank
from .models import Bank, BankValidationError, invalid, nonblank


@dataclass(frozen=True, slots=True)
class Catalog:
    banks: tuple[Bank, ...]

    def __post_init__(self):
        banks = tuple(self.banks)
        revisions = set()
        content = {}
        for bank in banks:
            if not isinstance(bank, Bank):
                invalid('banks', 'expected Bank records')
            if bank.revision in revisions:
                invalid('banks', 'duplicate bank revision')
            revisions.add(bank.revision)
            for question in bank.questions:
                key = (question.canonical_id, question.question_revision)
                digest = question_content_digest(question)
                if key in content and content[key] != digest:
                    raise BankValidationError('revision_reused', bank.revision,
                                              'changed question content requires a new revision')
                content[key] = digest
        object.__setattr__(self, 'banks', banks)

    def get(self, revision: str) -> Bank:
        for bank in self.banks:
            if bank.revision == revision:
                return bank
        raise BankValidationError('unknown_revision', 'revision', 'bank revision is not in the catalog')


def load_catalog(manifest_path: Path) -> Catalog:
    path = Path(manifest_path)
    try:
        body = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise BankValidationError('invalid_schema', str(path), str(exc)) from exc
    except UnicodeError as exc:
        raise BankValidationError('invalid_json', str(path), 'expected UTF-8') from exc
    try:
        raw = json.loads(body, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (ValueError, RecursionError) as exc:
        raise BankValidationError('invalid_json', str(path), str(exc)) from exc
    _validate_unicode(raw)
    _fields(raw, 'schema_version banks', '$')
    if type(raw['schema_version']) is not int or raw['schema_version'] != 1:
        invalid('$.schema_version', 'expected integer 1')
    if not isinstance(raw['banks'], list):
        invalid('$.banks', 'expected array')
    entries = []
    revisions = set()
    for index, entry in enumerate(raw['banks']):
        location = f'$.banks[{index}]'
        _fields(entry, 'revision file sha256', location)
        for field in ('revision', 'file', 'sha256'):
            nonblank(entry[field], location + '.' + field)
        filename = entry['file']
        if (filename in ('.', '..') or '/' in filename or '\\' in filename
                or ':' in filename or not filename.endswith('.json')):
            invalid(location + '.file', 'expected basename-only JSON filename')
        if not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            invalid(location + '.sha256', 'expected lowercase SHA-256 hex pin')
        if entry['revision'] in revisions:
            invalid(location + '.revision', 'duplicate bank revision')
        revisions.add(entry['revision'])
        entries.append(entry)
    return Catalog(tuple(load_bank(path.parent / entry['file'],
                                   expected_revision=entry['revision'],
                                   expected_sha256=entry['sha256']) for entry in entries))


def load_reviewed_bank(revision: str = 'ranked-routes-v1') -> Bank:
    manifest = Path(__file__).resolve().parents[1] / 'data' / 'ranked' / 'manifest.json'
    return load_catalog(manifest).get(revision)
