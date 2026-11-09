"""Code meaning identities and canonical content fingerprints."""
import hashlib
import json
from dataclasses import asdict
from .models import normalize_service

def _json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)

def canonical_key(context,rule,exclusions=()):
    keys=sorted([[e.rule.kind,list(e.rule.parts)] for e in exclusions],key=_json)
    return _json([normalize_service(context.service),context.mode,[rule.kind,list(rule.parts)],keys])

def stable_question_id(context,rule,exclusions=()):
    digest=hashlib.sha256(canonical_key(context,rule,exclusions).encode('utf-8')).hexdigest()
    return f'rq-{normalize_service(context.service).lower()}-{rule.kind}-{digest}'

def canonical_json_digest(raw):
    encoded=json.dumps(raw,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()

def question_content_digest(q):
    return canonical_json_digest(asdict(q))
