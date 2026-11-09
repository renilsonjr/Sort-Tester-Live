"""One-time, fail-closed authoring export. Runtime never imports review documents."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import tempfile
from backend.ranked_bank.models import Context, RouteRule, Exclusion
from backend.ranked_bank.identity import stable_question_id, canonical_key, canonical_json_digest
from backend.ranked_bank.loading import load_bank

REPO_ROOT=Path(__file__).resolve().parents[1]
SPEC=Path('docs/superpowers/specs')
SOURCE=SPEC/'2026-11-08-ranked-full-chart-review.json'
SHEET=SPEC/'2026-11-08-ranked-question-wording-review.md'
REVISION='ranked-routes-v1'

@dataclass(frozen=True,slots=True)
class ExportReport:
    bank_path: Path
    manifest_path: Path
    question_count: int
    review_ref_to_id: tuple[tuple[str,str],...]

def _initial_copy(sheet):
    # The approved sheet remains the authoring source; the test fixture is independent.
    if not all(s in sheet for s in ('Owner approved Spanish Easy','Owner approved Spanish Medium','Owner approved Spanish Hard','owner approved the English')):
        raise ValueError('initial bilingual approvals are incomplete')
    result={}
    for line in sheet.splitlines():
        cells=[s.strip() for s in line.split('|')[1:-1]]
        if cells and re.fullmatch('[EMH][1-7]',cells[0]):
            lang='en' if len(cells)==7 else 'es'
            result.setdefault(cells[0],{})[lang]={'prompt':'Which belt does this go to?' if lang=='en' else '¿A qué color va?','explanation':cells[-1]}
    if len(result)!=17 or any(set(v)!={'en','es'} for v in result.values()):raise ValueError('incomplete initial wording')
    return result

def _meaning(e):
    code=e['code']; mode='ordinary'
    if e.get('routingInterpretation',{}).get('kind')=='exact_code_literal':
        meta=e['routingInterpretation']
        if not meta.get('ownerConfirmed') or meta['value']!=code:raise ValueError('unapproved literal')
        rule=RouteRule('exact_literal',(code,))
    elif e.get('destinationModifier')=='+1': mode='+1';rule=RouteRule('any_route',())
    elif code=='ALL 1DA EAM':
        if not e.get('destinationInterpretation',{}).get('ownerConfirmed'):raise ValueError('unapproved EAM')
        mode='EAM';rule=RouteRule('any_route',())
    elif code in ('ends 1S','ends 2S'):mode='suffix:'+code[-2:];rule=RouteRule('suffix',(code[-2:],))
    elif code in ('MEXICO','CANADA','PR','WORLD'):rule=RouteRule('named_destination',(code,))
    elif re.fullmatch('[0-9]{3} [0-9]',code):rule=RouteRule('qualified_code',tuple(code.split()))
    elif re.fullmatch('[0-9]{3}(?:–[0-9]{3})?',code):rule=RouteRule('prefix_range',tuple(code.split('–')) if '–' in code else (code,code))
    else:raise ValueError('unsupported reviewed meaning: '+e['approvedReview']+' '+code)
    return Context(e['service'],mode),rule

def _json(value):return json.dumps(value,ensure_ascii=False,indent=2)+'\n'

def export_reviewed_bank(output_dir: Path, *, repo_root: Path=REPO_ROOT) -> ExportReport:
    output_dir=Path(output_dir)
    if output_dir.exists():raise FileExistsError(output_dir)
    raw=json.loads((repo_root/SOURCE).read_text(encoding='utf-8')); entries=raw['entries']
    if len(entries)!=283 or raw['contentReviewStatus']['status']!='owner-approved-review-content':raise ValueError('unapproved/incomplete source')
    for e in entries:
        if e['difficultyStatus']!='owner-approved' or e['wordingStatus'] not in ('owner-approved-bilingual','owner-approved-in-initial-sheet'):raise ValueError('unapproved content '+e['id'])
        if e['wordingStatus']=='owner-approved-bilingual' and any(e['wording'][lang]['approvalStatus']!='owner-approved' for lang in ('en','es')):raise ValueError('unapproved translation')
    initial=_initial_copy((repo_root/SHEET).read_text(encoding='utf-8'))
    meaning={e['approvedReview']:_meaning(e) for e in entries}
    if len(meaning)!=283:raise ValueError('duplicate review ref')
    questions=[]
    for e in entries:
        ref=e['approvedReview'];ctx,rule=meaning[ref]; exclusions=[]
        # Explicit numeric exceptions override containing broad primary ranges.
        if rule.kind=='prefix_range':
            for other in entries:
                oref=other['approvedReview'];oc,orr=meaning[oref]
                if oref==ref or oc!=ctx:continue
                prefix=orr.parts[0][:3] if orr.parts else ''
                if orr.kind in ('qualified_code','exact_literal') and rule.parts[0]<=prefix<=rule.parts[1]:exclusions.append(Exclusion(oref,orr))
                elif orr.kind=='prefix_range' and other['kind']=='exceptions' and e['kind']=='main' and rule.parts[0]<=orr.parts[0]<=orr.parts[1]<=rule.parts[1]:exclusions.append(Exclusion(oref,orr))
        exclusions=tuple(sorted(exclusions,key=lambda ex:canonical_key(ctx,ex.rule)))
        if rule.kind=='prefix_range':
            candidates=[f'{i:03}' for i in range(int(rule.parts[0]),int(rule.parts[1])+1)]
            for ex in exclusions:
                candidates=[c for c in candidates if not (ex.rule.parts[0]<=c<=ex.rule.parts[1] if ex.rule.kind=='prefix_range' else c==ex.rule.parts[0][:3])]
            if not candidates:raise ValueError('no unambiguous example '+ref)
            code=e.get('rangeExampleReview',{}).get('displayedRoutingCode',candidates[0]);region=e['state'];named=None
        elif rule.kind=='named_destination':code=None;region=e['state'];named=rule.parts[0]
        elif rule.kind=='suffix':code='109 '+rule.parts[0];region='NY';named=None
        elif rule.kind=='any_route':code='109';region='NY';named=None
        else:code=e['code'];region=e['state'];named=None
        if 'rangeExampleReview' in e and e['rangeExampleReview']['status']!='owner-approved-example-content':raise ValueError('unapproved example')
        copy=initial[ref] if e['wordingStatus']=='owner-approved-in-initial-sheet' else {lang:{k:e['wording'][lang][k] for k in ('prompt','explanation')} for lang in ('en','es')}
        questions.append(dict(canonical_id=stable_question_id(ctx,rule,exclusions),question_revision=1,source=dict(review_ref=ref,row_id=e['id'],row_kind=e['kind'],state_label=e['state'],code_label=e['code'],provenance=e['provenance']),context=dict(service=ctx.service,mode=ctx.mode),rule=dict(kind=rule.kind,parts=list(rule.parts)),exclusion_refs=[ex.review_ref for ex in exclusions],difficulty=e['difficulty'],correct_belt=e['expectedBelt'],copy=copy,presentation=dict(routing_code=code,region_label=region,named_destination=named)))
    questions.sort(key=lambda q:q['canonical_id'])
    bank=dict(schema_version=1,bank_revision=REVISION,source_revision=raw['sourceRevision'],questions=questions)
    pin=canonical_json_digest(bank); body=_json(bank)
    # Existing strict loader performs semantic, duplicate, reference and display checks before publication.
    with tempfile.TemporaryDirectory() as scratch:
        candidate=Path(scratch)/'candidate.json';candidate.write_text(body,encoding='utf-8')
        load_bank(candidate,expected_revision=REVISION,expected_sha256=pin)
    manifest=dict(schema_version=1,banks=[dict(revision=REVISION,file='routes-v1.json',sha256=pin)])
    output_dir.mkdir(parents=True,exist_ok=False)
    bank_path=output_dir/'routes-v1.json'; manifest_path=output_dir/'manifest.json'
    for path,value in ((bank_path,body),(manifest_path,_json(manifest))):
        with path.open('x',encoding='utf-8',newline='\n') as handle:handle.write(value)
    return ExportReport(bank_path,manifest_path,len(questions),tuple(sorted((q['source']['review_ref'],q['canonical_id']) for q in questions)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();report=export_reviewed_bank(args.output_dir);print(f'Exported {report.question_count} reviewed questions to {report.bank_path}')
