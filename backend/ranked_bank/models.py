"""Immutable values shared by Ranked bank components."""
from dataclasses import dataclass

class BankValidationError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(f'{path}: {message}')

class BankUnavailableError(ValueError):
    code = 'insufficient_compatible_pool'


def invalid(path, message):
    raise BankValidationError('invalid_schema', path, message)

def nonblank(value, path):
    if not isinstance(value,str) or not value.strip(): invalid(path,'expected nonblank string')
    return value

def normalize_service(value: str) -> str:
    nonblank(value,'service')
    aliases={'gnd':'GND','grd':'GND','ground':'GND','nda':'NDA','next day air':'NDA','2da':'2DA','2nd day air':'2DA','3ds':'3DS','3 day select':'3DS'}
    result=aliases.get(' '.join(value.lower().split()))
    if result is None: invalid('service','unknown service')
    return result

@dataclass(frozen=True,slots=True)
class Context:
    service: str
    mode: str
    def __post_init__(self):
        object.__setattr__(self,'service',normalize_service(self.service))
        if self.mode not in ('ordinary','+1','EAM','suffix:1S','suffix:2S'): invalid('context.mode','unknown mode')
        if self.mode=='EAM' and self.service!='NDA': invalid('context.mode','EAM requires NDA')

@dataclass(frozen=True,slots=True)
class RouteRule:
    kind: str
    parts: tuple[str,...]
    def __post_init__(self):
        if not isinstance(self.parts,(tuple,list)) or any(not isinstance(p,str) for p in self.parts): invalid('rule.parts','expected string sequence')
        object.__setattr__(self,'parts',tuple(self.parts))
        p=self.parts
        digit3=lambda s:len(s)==3 and s.isascii() and s.isdigit()
        valid=False
        if self.kind=='prefix_range': valid=len(p)==2 and all(digit3(x) for x in p) and p[0]<=p[1]
        elif self.kind=='qualified_code': valid=len(p)==2 and digit3(p[0]) and len(p[1])==1 and p[1] in '0123456789'
        elif self.kind=='exact_literal': valid=len(p)==1 and bool(p[0].strip())
        elif self.kind=='suffix': valid=len(p)==1 and p[0] in ('1S','2S')
        elif self.kind=='named_destination': valid=len(p)==1 and p[0] in ('MEXICO','CANADA','PR','WORLD')
        elif self.kind=='any_route': valid=len(p)==0
        if not valid: invalid('rule','invalid kind or parts')

@dataclass(frozen=True,slots=True)
class Exclusion:
    review_ref: str
    rule: RouteRule

@dataclass(frozen=True,slots=True)
class SourceRef:
    review_ref: str
    row_id: str
    row_kind: str
    state_label: str
    code_label: str
    provenance: str
    source_revision: str

@dataclass(frozen=True,slots=True)
class CopyText:
    prompt: str
    explanation: str

@dataclass(frozen=True,slots=True)
class LocalizedCopy:
    en: CopyText
    es: CopyText

@dataclass(frozen=True,slots=True)
class Presentation:
    routing_code: str | None
    region_label: str
    named_destination: str | None

@dataclass(frozen=True,slots=True)
class Question:
    canonical_id: str
    question_revision: int
    source: SourceRef
    context: Context
    rule: RouteRule
    exclusions: tuple[Exclusion,...]
    difficulty: str
    correct_belt: str
    text: LocalizedCopy
    presentation: Presentation
    def __post_init__(self): object.__setattr__(self,'exclusions',tuple(self.exclusions))

@dataclass(frozen=True,slots=True)
class Bank:
    schema_version: int
    revision: str
    source_revision: str
    sha256: str
    questions: tuple[Question,...]
    def __post_init__(self): object.__setattr__(self,'questions',tuple(self.questions))

@dataclass(frozen=True,slots=True)
class AssignmentSnapshot:
    bank_revision: str
    bank_sha256: str
    source_revision: str
    questions: tuple[Question,...]
    def __post_init__(self): object.__setattr__(self,'questions',tuple(self.questions))
