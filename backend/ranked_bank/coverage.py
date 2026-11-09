"""Effective routing domains and conservative fixed-example validation."""
import re
from .models import BankValidationError


def _fail(code, question, message):
    raise BankValidationError(code, question.source.review_ref, message)


def _prefix(rule):
    value = rule.parts[0] if rule.parts else ''
    return value[:3] if re.match(r'^[0-9]{3}(?:$| )', value) else None


def _contains(parent, child):
    if parent.kind == 'any_route':
        return child.kind != 'named_destination'
    if parent.kind == 'prefix_range':
        if child.kind == 'prefix_range':
            return parent.parts[0] <= child.parts[0] <= child.parts[1] <= parent.parts[1]
        prefix = _prefix(child) if child.kind in ('qualified_code', 'exact_literal') else None
        return prefix is not None and parent.parts[0] <= prefix <= parent.parts[1]
    return parent == child


def _prefixes(question):
    start, end = question.rule.parts
    result = {f'{number:03}' for number in range(int(start), int(end) + 1)}
    for exclusion in question.exclusions:
        if exclusion.rule.kind == 'prefix_range':
            lo, hi = exclusion.rule.parts
            result.difference_update(f'{number:03}' for number in range(int(lo), int(hi) + 1))
    return result


def available_range_prefixes(question):
    if question.rule.kind != 'prefix_range':
        return ()
    prefixes = _prefixes(question)
    # Any narrow exception makes a three-digit example potentially ambiguous.
    for exclusion in question.exclusions:
        if exclusion.rule.kind in ('qualified_code', 'exact_literal'):
            prefixes.discard(_prefix(exclusion.rule))
    return tuple(sorted(prefixes))


def _covers_leaf(question, rule):
    return _contains(question.rule, rule) and not any(_contains(e.rule, rule) for e in question.exclusions)


def rules_overlap(left, right):
    if left.context != right.context:
        return False
    a, b = left.rule, right.rule
    if a.kind == b.kind == 'prefix_range':
        return bool(_prefixes(left) & _prefixes(right))
    if a.kind == 'prefix_range':
        return _covers_leaf(left, b) and _covers_leaf(right, b)
    if b.kind == 'prefix_range':
        return _covers_leaf(right, a) and _covers_leaf(left, a)
    if a.kind == 'any_route':
        return _covers_leaf(left, b) and _covers_leaf(right, b)
    if b.kind == 'any_route':
        return _covers_leaf(right, a) and _covers_leaf(left, a)
    return a == b and _covers_leaf(left, a) and _covers_leaf(right, b)


def validate_presentation(question):
    rule, presentation, mode = question.rule, question.presentation, question.context.mode
    code = presentation.routing_code
    def reject(message):
        _fail('invalid_presentation', question, message)
    if rule.kind == 'named_destination':
        if mode != 'ordinary' or code is not None or presentation.named_destination != rule.parts[0]:
            reject('named destination requires its own token and no routing code')
        return
    if presentation.named_destination is not None or code is None:
        reject('numeric route requires a routing code and no named destination')
    suffix = re.search(r'(?:^|\s)(1S|2S)$', code)
    if mode.startswith('suffix:'):
        if rule.kind != 'suffix' or rule.parts[0] != mode[7:] or not suffix or suffix[1] != rule.parts[0]:
            reject('suffix mode, rule and example must agree')
        if not re.fullmatch(r'[0-9]{3}(?: [0-9]| [0-9]-[0-9])? (?:1S|2S)',code):
            reject('unsupported suffix example')
        return
    if suffix or '+1' in code or 'EAM' in code.upper():
        reject('combined markers have no approved precedence')
    if mode in ('+1', 'EAM'):
        if rule.kind != 'any_route' or not re.fullmatch(r'[0-9]{3}(?: [0-9]| [0-9]-[0-9])?', code):
            reject('qualifier requires an ordinary code and any_route')
        if mode == '+1' and question.correct_belt != 'PURPLE':
            reject('+1 requires PURPLE')
        return
    if rule.kind == 'prefix_range':
        if code not in available_range_prefixes(question):
            reject('example is outside the eligible unambiguous prefixes')
    elif rule.kind == 'qualified_code':
        if code != ' '.join(rule.parts):
            reject('qualified example must preserve prefix and digit')
    elif rule.kind == 'exact_literal':
        if code != rule.parts[0]:
            reject('literal example must preserve the entire code')
    else:
        reject('rule does not agree with ordinary context')


def validate_bank_coverage(bank):
    for question in bank.questions:
        for exclusion in question.exclusions:
            if not _contains(question.rule, exclusion.rule):
                _fail('invalid_reference', question, 'exclusion must be contained in parent rule')
        validate_presentation(question)
    for index, left in enumerate(bank.questions):
        for right in bank.questions[index + 1:]:
            if left.correct_belt != right.correct_belt and rules_overlap(left, right):
                _fail('invalid_coverage', left, 'conflicting effective coverage with ' + right.source.review_ref)
