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
