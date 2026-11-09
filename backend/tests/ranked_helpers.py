import json
from pathlib import Path
from backend.ranked_bank.identity import stable_question_id, canonical_json_digest
from backend.ranked_bank.models import Context, RouteRule, Exclusion

def raw_question(review_ref, *, service='GND', mode='ordinary', kind='prefix_range', parts=('100','108'), difficulty='Easy', correct_belt='YELLOW', question_revision=1, exclusion_refs=(), routing_code='100', named_destination=None, region_label='NY'):
    return dict(canonical_id='', question_revision=question_revision, source=dict(review_ref=review_ref,row_id=review_ref,row_kind='range',state_label=region_label,code_label='100–108',provenance='fixture'),context=dict(service=service,mode=mode),rule=dict(kind=kind,parts=list(parts)),exclusion_refs=list(exclusion_refs),difficulty=difficulty,correct_belt=correct_belt,copy=dict(en=dict(prompt='Where does 100 go?',explanation='Use YELLOW.'),es=dict(prompt='¿Dónde va 100?',explanation='Use YELLOW.')),presentation=dict(routing_code=routing_code,region_label=region_label,named_destination=named_destination))

def raw_bank(*questions, revision='fixture-v1'):
    refs={q['source']['review_ref']:q for q in questions}
    for q in questions:
        exclusions=tuple(Exclusion(r,RouteRule(**refs[r]['rule'])) for r in q['exclusion_refs'])
        q['canonical_id']=stable_question_id(Context(**q['context']),RouteRule(**q['rule']),exclusions)
    return dict(schema_version=1,bank_revision=revision,source_revision='fixture-source',questions=list(questions))

def write_fixture(directory,payload):
    path=Path(directory)/'bank.json'; path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    return path,canonical_json_digest(payload)

def by_ref(bank,ref):
    return next(q for q in bank.questions if q.source.review_ref==ref)


def _selection_fixture(directory, *, trap=False, unavailable=False):
    import tempfile
    from backend.ranked_bank.loading import load_bank
    target = Path(tempfile.mkdtemp(dir=directory))
    rows = []
    for difficulty, label, base in (('Easy', 'E', 1), ('Medium', 'M', 110 if trap else 301), ('Hard', 'H', 210 if trap else 401)):
        for number in range(1, 6 if unavailable else 7):
            lo = f'{100 + number - 1:03}' if unavailable and label == 'E' else f'{base + number - 1:03}'
            hi = '199' if unavailable and label == 'E' else lo
            if trap and label == 'E' and number == 6:
                lo, hi = '100', '199'
            ref = 'TRAP' if trap and label == 'E' and number == 6 else f'{label}{number}'
            rows.append(raw_question(ref, parts=(lo, hi), difficulty=difficulty, correct_belt='GOLD', routing_code=lo))
    payload = raw_bank(*rows)
    path, digest = write_fixture(target, payload)
    return load_bank(path, expected_revision=payload['bank_revision'], expected_sha256=digest)


def make_trap_bank(directory):
    return _selection_fixture(directory, trap=True)


def make_unavailable_bank(directory):
    return _selection_fixture(directory, unavailable=True)


def make_unconstrained_bank(directory):
    return _selection_fixture(directory)
