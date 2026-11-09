"""Strict artifact loading; semantic coverage validation is a separate layer."""
import json
import math
from pathlib import Path
from .models import (BankValidationError, invalid, nonblank, Context, RouteRule,
    Exclusion, SourceRef, CopyText, LocalizedCopy, Presentation, Question, Bank)
from .identity import canonical_json_digest, canonical_key, stable_question_id

def _fields(value,names,path):
    if not isinstance(value,dict) or set(value)!=set(names.split()): invalid(path,'expected exactly: '+names)
    return value

def _strings(value,path):
    for key,item in value.items(): nonblank(item,f'{path}.{key}')

def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError(f'duplicate member {key}')
        result[key]=value
    return result

def _constant(value): raise ValueError(f'nonfinite number {value}')

def _float(value):
    parsed=float(value)
    if not math.isfinite(parsed): raise ValueError('nonfinite number '+value)
    return parsed

def _validate_unicode(value, path='$'):
    """Reject escaped lone surrogates before canonical UTF-8 hashing."""
    if isinstance(value,str):
        try: value.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise BankValidationError('invalid_json',path,'unpaired Unicode surrogate') from exc
    elif isinstance(value,list):
        for index,item in enumerate(value): _validate_unicode(item,f'{path}[{index}]')
    elif isinstance(value,dict):
        for key,item in value.items():
            _validate_unicode(key,path+'[object key]')
            _validate_unicode(item,path+'.'+key)

def load_bank(path: Path, *, expected_revision: str, expected_sha256: str) -> Bank:
    try: body=Path(path).read_text(encoding='utf-8')
    except OSError as exc: raise BankValidationError('invalid_schema',str(path),str(exc)) from exc
    except UnicodeError as exc: raise BankValidationError('invalid_json',str(path),'expected UTF-8') from exc
    try: raw=json.loads(body,object_pairs_hook=_pairs,parse_constant=_constant,parse_float=_float)
    except (ValueError,RecursionError) as exc: raise BankValidationError('invalid_json',str(path),str(exc)) from exc
    _validate_unicode(raw)
    _fields(raw,'schema_version bank_revision source_revision questions','$')
    if type(raw['schema_version']) is not int or raw['schema_version']!=1: invalid('$.schema_version','expected integer 1')
    nonblank(raw['bank_revision'],'$.bank_revision'); nonblank(raw['source_revision'],'$.source_revision')
    if not isinstance(raw['questions'],list): invalid('$.questions','expected array')
    digest=canonical_json_digest(raw)
    if raw['bank_revision']!=expected_revision: raise BankValidationError('unknown_revision','$.bank_revision','unexpected revision')
    if digest!=expected_sha256: raise BankValidationError('digest_mismatch','$','artifact pin does not match')
    prepared=[]; refs={}
    for i,q in enumerate(raw['questions']):
        p=f'$.questions[{i}]'
        _fields(q,'canonical_id question_revision source context rule exclusion_refs difficulty correct_belt copy presentation',p)
        nonblank(q['canonical_id'],p+'.canonical_id')
        if type(q['question_revision']) is not int or q['question_revision']<1: invalid(p+'.question_revision','expected positive integer')
        source=_fields(q['source'],'review_ref row_id row_kind state_label code_label provenance',p+'.source'); _strings(source,p+'.source')
        context=_fields(q['context'],'service mode',p+'.context')
        rule=_fields(q['rule'],'kind parts',p+'.rule')
        try: ctx=Context(**context); rr=RouteRule(**rule)
        except BankValidationError as exc: raise BankValidationError(exc.code,p+'.'+exc.path,str(exc)) from exc
        if not isinstance(rule['parts'],list): invalid(p+'.rule.parts','expected array')
        er=q['exclusion_refs']
        if not isinstance(er,list) or any(not isinstance(r,str) or not r.strip() for r in er): invalid(p+'.exclusion_refs','expected string array')
        if len(set(er))!=len(er): raise BankValidationError('invalid_reference',p+'.exclusion_refs','duplicate references')
        if q['difficulty'] not in ('Easy','Medium','Hard'): invalid(p+'.difficulty','unknown difficulty')
        if q['correct_belt'] not in ('GOLD','BLUE','ORANGE','PINK','GREEN','YELLOW','BROWN','RED','PURPLE'): invalid(p+'.correct_belt','unknown belt')
        copy=_fields(q['copy'],'en es',p+'.copy'); texts={}
        for lang in ('en','es'):
            text=_fields(copy[lang],'prompt explanation',p+'.copy.'+lang); _strings(text,p+'.copy.'+lang); texts[lang]=CopyText(**text)
        pres=_fields(q['presentation'],'routing_code region_label named_destination',p+'.presentation')
        nonblank(pres['region_label'],p+'.presentation.region_label')
        for key in ('routing_code','named_destination'):
            if pres[key] is not None: nonblank(pres[key],p+'.presentation.'+key)
        ref=source['review_ref']
        if ref in refs: raise BankValidationError('invalid_reference',p+'.source.review_ref','duplicate review reference')
        refs[ref]=len(prepared)
        prepared.append((q,p,SourceRef(**source,source_revision=raw['source_revision']),ctx,rr,LocalizedCopy(**texts),Presentation(**pres)))
    questions=[]; meanings=set()
    for q,p,source,ctx,rule,text,pres in prepared:
        exclusions=[]
        for ref in q['exclusion_refs']:
            if ref not in refs: raise BankValidationError('invalid_reference',p+'.exclusion_refs','missing reference '+ref)
            target=prepared[refs[ref]]
            if ref==source.review_ref or target[0]['exclusion_refs'] or target[3]!=ctx:
                raise BankValidationError('invalid_reference',p+'.exclusion_refs','requires same-context leaf reference')
            exclusions.append(Exclusion(ref,target[4]))
        exclusions=tuple(sorted(exclusions,key=lambda e:canonical_key(ctx,e.rule)))
        key=canonical_key(ctx,rule,exclusions)
        if key in meanings: raise BankValidationError('duplicate_canonical',p,'duplicate rule meaning')
        meanings.add(key)
        if q['canonical_id']!=stable_question_id(ctx,rule,exclusions): invalid(p+'.canonical_id','does not match rule meaning')
        questions.append(Question(q['canonical_id'],q['question_revision'],source,ctx,rule,exclusions,q['difficulty'],q['correct_belt'],text,pres))
    from .coverage import validate_bank_coverage
    bank = Bank(1,raw['bank_revision'],raw['source_revision'],digest,tuple(questions))
    validate_bank_coverage(bank)
    return bank
