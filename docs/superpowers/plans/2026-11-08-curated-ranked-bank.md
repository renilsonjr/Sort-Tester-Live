# Curated Ranked Bank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn the reviewed chart content into a strict, immutable backend bank that can prepare a valid randomized 15-question assignment.

**Architecture:** add a separate Python package and versioned JSON artifacts; keep the approved source/copy separate from Practice decks. Explicit rule types preserve exact code meanings and exception priority. A pure selector chooses compatible questions; persistence and game endpoints remain later work.

**Tech Stack:** existing Python 3.14 environment, standard-library `dataclasses`, `json`, `hashlib`, `random`, `unittest`; existing Node regression suite and Windows CI. No new packages.

**Spec:** [[2026-11-08-curated-ranked-bank-design]]. Read it with [[2026-11-08-ranked-full-chart-review]], [[2026-11-08-ranked-expanded-wording-review]], [[2026-11-08-ranked-question-wording-review]] and [[2026-11-08-ranked-chart-reference]]. Tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5).

**Status:** owner-approved and implemented on `codex/ranked-mode`; all five task reviews approved. Local automated verification passed. Final-head hosted results are tracked in PR32; owner manual Windows verification remains pending. See [[2026-11-08-curated-ranked-bank-verification]].

## Global Constraints

- Work only in the Live checkout on shared `codex/ranked-mode`. Preserve the owner's existing-branch preference; create no extra branch/worktree and do not edit the private Sort-testing app. Check for concurrent/user changes before each task; never overwrite them.
- Preserve all 283 approved review entries, 103 Easy / 127 Medium / 53 Hard, exact bilingual copy and the original 17 approvals. Four broad NJ CHECK rows stay excluded. Do not silently merge, invent, drop or re-rank content; report an actual semantic collision for targeted review.
- Source authority is `twilight-2026-11-08-r2`. Keep leading zeros, exact hyphenated literals, printed source labels and source references. Region labels are retained as provenance/display; they cannot defeat listed exact-code exception priority.
- A quiz contains exactly five Easy, five Medium and five Hard questions. Randomize membership and final order. V1 uses fixed reviewed/derived representative codes; do not randomly rewrite approved code-specific feedback or interpolate new wording.
- +1 means PURPLE for any state/all four services; NY109 is an example. EAM is an NDA service qualifier with routing code separate. Reject combined +1/EAM/suffix cases whose precedence was not approved.
- Only work-methods tie-question content is deferred. Other tie rules are unchanged. This bank does not automatically replace the work-methods bank or close Issue5/remove Issue6 dependencies.
- Practice, `backend/main.py`, API routes, auth, timers, scoring, database, deployment and frontend files remain outside this plan. Public repository content is readable; this is not a secret-question system. Do not copy the private chart image or employee data.
- Use the existing environment directly. Windows: `backend\.venv\Scripts\python.exe`; Mac: `backend/.venv/bin/python`. CI already discovers `backend/tests/test*.py`; no workflow/dependency changes are needed.

## Review Focus

1. **Windows newlines, spaces in paths and zero-prefixed codes:** canonical JSON fingerprints and module-relative assets work across LF/CRLF; `010` never becomes `10`. Tests: Tasks1/4.
2. **Alias/language/presentation duplicates:** GND/GRD/Ground, translations or different example codes cannot create extra canonical slots. Tests: Tasks1/3/5.
3. **Exact-code and marker boundaries:** `575 3-6` is one literal; explicit exceptions override broad ranges across printed labels; mixed unapproved markers fail. Tests: Task2.
4. **Enough counts but incompatible coverage:** selection finds a complete compatible 5/5/5 set or returns unavailable, never a misleading partial result or a greedy false failure. Tests: Task5.
5. **Revision reuse and code/feedback drift:** old snapshots remain immutable; changing published content cannot reuse its revision, and approved 20 examples/copy stay paired. Tests: Tasks3/4/5.

---

## Files and Interfaces

Paths below are repository-relative for Windows/Mac portability.

| File | Responsibility |
| --- | --- |
| `backend/ranked_bank/models.py` | frozen records, primitive validation, errors and service aliases |
| `backend/ranked_bank/identity.py` | semantic keys, stable IDs and content fingerprints |
| `backend/ranked_bank/loading.py` | strict JSON/schema loading and bank digest verification |
| `backend/ranked_bank/coverage.py` | effective coverage, conflicts and presentation validation |
| `backend/ranked_bank/catalog.py` | pinned manifest/version lookup and revision collision checks |
| `backend/ranked_bank/selection.py` | complete quota selection and internal immutable snapshots |
| `backend/ranked_bank/check.py` | read-only developer CLI for Windows/manual verification |
| `backend/ranked_bank/__init__.py` | documented public Python exports only |
| `backend/data/ranked/routes-v1.json`, `manifest.json` | first immutable reviewed data revision and pins |
| `tools/export_ranked_v1.py` | reproducible one-time authoring export; never used at runtime |
| `backend/tests/ranked_helpers.py` | synthetic fixture construction, not production hooks |
| `backend/tests/test_ranked_{loading,coverage,data,catalog,selection}.py` | meaningful unit/data/integration checks |
| `backend/tests/fixtures/ranked/initial-17-copy.json` | independent literal copy baseline for original 17 |
| `backend/README.md` | bank check/test commands and scope |

### Shared data contract — implementation choices for owner review

Use `@dataclass(frozen=True, slots=True)` records; nested collections are tuples/copy-in, with no mutable dict/list retained. Define normalize_service in models.py; identity.py imports it, keeping model imports acyclic:

- `Context(service, mode)`: services `GND,NDA,2DA,3DS`; modes `ordinary,+1,EAM,suffix:1S,suffix:2S`. `normalize_service(value: str) -> str` accepts those codes plus GRD and the four English service names, ignoring surrounding/repeated whitespace and case. EAM is NDA-only. Context mode is exclusive; ordinary rules never silently acquire a marker.
- `RouteRule(kind, parts: tuple[str,...])`: `prefix_range(start,end)` with ASCII three-digit strings; `qualified_code(prefix,digit)`; `exact_literal(full_code)`; `suffix(1S|2S)`; `named_destination(MEXICO|CANADA|PR|WORLD)`; `any_route()` for +1/EAM. Numeric range bounds must be ordered. Literal punctuation is preserved, not normalized into a range or five-digit number.
- `Exclusion(review_ref, rule)`, `SourceRef(review_ref,row_id,row_kind,state_label,code_label,provenance,source_revision)`, `CopyText(prompt,explanation)`, `LocalizedCopy(en,es)`, `Presentation(routing_code: str|None,region_label: str,named_destination: str|None)`.
- `Question(canonical_id,question_revision,source,context,rule,exclusions,difficulty,correct_belt,text,presentation)`. Difficulty is exactly Easy/Medium/Hard; belt is one of GOLD,BLUE,ORANGE,PINK,GREEN,YELLOW,BROWN,RED,PURPLE. Revision is a positive integer, not bool/float. `Bank(schema_version,revision,source_revision,sha256,questions)` and `AssignmentSnapshot(bank_revision,bank_sha256,source_revision,questions)` are immutable.
- `BankValidationError(code: str,path: str,message: str)` subclasses ValueError. Stable error codes: `invalid_json,invalid_schema,digest_mismatch,duplicate_canonical,invalid_reference,invalid_coverage,invalid_presentation,unknown_revision,revision_reused`. `BankUnavailableError` has code `insufficient_compatible_pool` and carries no partial assignment.

Canonical identity is the code-based rule meaning, not the printed region label or presentation/copy. Named countries use their actual named-destination token. `canonical_key(context,rule,exclusions=()) -> str` serializes `[normalized_service,mode,[kind,list(parts)],sorted_exclusion_rule_keys]` as compact Unicode JSON. Exclusion keys contain rule kind/parts, not review IDs or answers. `stable_question_id(...) -> str` is `rq-{service.lower()}-{kind}-{full_sha256_of_key}`. Identical meaning with different labels, languages, answers, difficulty or examples is a duplicate to reject, not an extra question. These choices make label corrections traceable without changing a rule ID. Changed rule/exclusion meaning gets a new ID; answer/copy/difficulty/presentation changes retain the ID and require a new question revision.

Artifact root keys are exactly `schema_version:1,bank_revision,source_revision,questions`. Question keys are exactly `canonical_id,question_revision,source,context,rule,exclusion_refs,difficulty,correct_belt,copy,presentation`. Source contains the SourceRef fields except source_revision (inherited from root); context is `{service,mode}`, rule is `{kind,parts}`, copy contains exactly en/es prompt/explanation, presentation contains its three fields. Reject unknown/missing fields and coercions. Resolve exclusion review refs to immutable leaf rules; reject missing/self/nested/cyclic/cross-context exclusions. Do not infer precedence from input order.

`canonical_json_digest(raw: Mapping[str,object]) -> str` hashes UTF-8 compact JSON with sorted object keys, Unicode preserved, array order retained and nonfinite numbers forbidden. The exporter sorts questions by canonical ID and exclusions by semantic rule key. JSON whitespace/LF/CRLF do not change the pin. Reject duplicate JSON members before hashing. `question_content_digest(q) -> str` hashes canonical `dataclasses.asdict(q)`; it includes stored source/copy/presentation so reused `(canonical_id,question_revision)` cannot hide changed content.

## Task 1: Immutable schema, identity and strict pinned loader

**Files:** create models.py, identity.py, loading.py and __init__.py above; create `backend/tests/ranked_helpers.py` and `backend/tests/test_ranked_loading.py`.

**Interfaces:** produces all shared records, `normalize_service`, `canonical_key`, `stable_question_id`, `question_content_digest`, `canonical_json_digest`, and `load_bank(path: Path, *, expected_revision: str, expected_sha256: str) -> Bank`. Task2 adds semantic coverage validation to that loader. No bank is imported or loaded at FastAPI startup.

- [x] **Step 1: Write failing schema/identity tests.** Helpers use TemporaryDirectory and literal fixture data. Define `raw_question(review_ref, *, service='GND',mode='ordinary',kind='prefix_range',parts=('100','108'),difficulty='Easy',correct_belt='YELLOW',question_revision=1,exclusion_refs=(),routing_code='100',named_destination=None,region_label='NY') -> dict`, `raw_bank(*questions,revision='fixture-v1') -> dict`, `write_fixture(directory,payload) -> (Path,str)` and `by_ref(bank,ref) -> Question`. raw_bank resolves leaf exclusion references before using the separately tested identity function to fill fixture IDs, independently of row order; expected answers/copy remain independent literals.

```python
def test_identity_is_stable_across_service_aliases(self):
    rule = RouteRule('prefix_range', ('100', '108'))
    expected = 'rq-gnd-prefix_range-7be00a20fe02bb8c8c34bf2c34e1b8a967c314c55d59832135e11624e4201cbe'
    for alias in ('GND', 'GRD', 'Ground'):
        self.assertEqual(stable_question_id(Context(alias, 'ordinary'), rule), expected)

def test_missing_spanish_feedback_is_rejected(self):
    data = raw_bank(raw_question('T1'))
    del data['questions'][0]['copy']['es']['explanation']
    path, pin = write_fixture(self.directory, data)
    with self.assertRaises(BankValidationError) as error:
        load_bank(path, expected_revision='fixture-v1', expected_sha256=pin)
    self.assertEqual(error.exception.code, 'invalid_schema')
```

Add named tests/assertions: `test_nested_records_are_immutable` (setattr question/text raises FrozenInstanceError; mutating input lists cannot change stored tuples); `test_lf_crlf_have_same_digest` (same parsed artifact loads against one pin); `test_leading_zero_range_is_preserved` (parts010/024 and shown010 stay strings); `test_duplicate_alias_meaning_is_rejected` (two aliases/translated-copy/example variants of one rule fail); `test_strict_json_rejects_duplicate_members_and_nonfinite` (invalid_json); `test_schema_rejects_unknown_fields_bool_revisions_and_CHECK` (invalid_schema); `test_bad_pin_is_rejected` (digest_mismatch). Region labels and copy must not change the ID; changing their stored content changes the content digest.

- [x] **Step 2: Verify red.** Mac: `backend/.venv/bin/python -m unittest backend.tests.test_ranked_loading -v`. Expected: new module/API unavailable or the required behavior fails, not a fixture typo.
- [x] **Step 3: Implement the specified immutable records, ID contract and loader.** JSON decode is strict UTF-8/duplicate-member/nonfinite handling. Validate exactly the schema above; missing files use invalid_schema and invalid content uses the corresponding BankValidationError code with a useful field path. Verify expected revision/digest; resolve references without nested exclusions; compare supplied IDs with computed meaning and reject duplicate keys. Copy text is validated as nonblank but not rewritten. Keep runtime imports independent of review Markdown/Practice.
- [x] **Step 4: Verify green.** Run the focused command, then `backend/.venv/bin/python -m unittest discover -s backend/tests -v`. Existing health/CORS tests must remain green.
- [x] **Step 5: Commit only the new package/helper/loading test files.** Suggested message: `feat: add immutable ranked bank schema and pinned loading`.

## Task 2: Effective routing coverage and safe presentations

**Files:** create `backend/ranked_bank/coverage.py` and `backend/tests/test_ranked_coverage.py`; modify loading.py to invoke semantic validation; extend ranked_helpers.py only for fixtures.

**Interfaces:** consumes Task1 records/loader; produces `rules_overlap(left: Question,right: Question) -> bool`, `available_range_prefixes(question: Question) -> tuple[str,...]`, `validate_presentation(question: Question) -> None` and `validate_bank_coverage(bank: Bank) -> None`.

- [x] **Step 1: Write failing coverage tests.** A fixture can hold same-answer overlapping rules; assignment will avoid co-selecting them. Different-answer overlaps without an explicit exclusion are invalid. Compare bare parent/child loaded separately when testing raw overlap.

```python
def test_exact_exception_can_cross_printed_region_labels(self):
    parent = raw_question('P1', parts=('832','839'), correct_belt='BROWN',
                          exclusion_refs=('X1',), routing_code='832', region_label='ID')
    child = raw_question('X1', kind='exact_literal', parts=('833 9-7',),
                         correct_belt='ORANGE', routing_code='833 9-7', region_label='NV')
    bank = self.load(parent, child)  # helper writes then uses the real pinned loader
    self.assertFalse(rules_overlap(by_ref(bank,'P1'), by_ref(bank,'X1')))
    self.assertNotIn('833', available_range_prefixes(by_ref(bank,'P1')))
    self.assertIn('832', available_range_prefixes(by_ref(bank,'P1')))
```

Define the `self.load(*questions) -> Bank` test wrapper using write_fixture/load_bank. Add tests: `test_qualified_code_exclusion_preserves_zero_and_digit` (NY148–149 excludes148 1; qualified code has parts148/1, never a numeric range); `test_TN_range_exception_subtracts_full_prefixes` (370–385 minus376–378); `test_literal_is_never_parsed_as_endpoints` (575 3-6 remains exactly that string); `test_same_answer_partial_ranges_overlap` (2DA609–619 versus609–629 returns True); `test_contexts_are_distinct` (ordinary versus+1/EAM/suffix and different services do not conflict); `test_plus_one_is_not_NY_restricted` (ordinary presentation CA900 under+1 validates/PURPLE; literal sample NY109 is not a condition); `test_reject_mixed_markers` (+1 with shown109 2S, EAM with suffix, and EAM on Ground fail); `test_unsafe_prefix_example_is_rejected` (shown148 for a rule excluding148 1 is ambiguous and fails;149 passes); `test_exclusion_must_be_contained_and_leaf` (unknown/self/nested/cross-service targets fail).

- [x] **Step 2: Verify red.** Run `backend/.venv/bin/python -m unittest backend.tests.test_ranked_coverage -v`; confirm the missing coverage behavior fails.
- [x] **Step 3: Implement coverage and integrate it with loading.** Only equal normalized service/mode can overlap. Named destinations form a separate domain from numeric rules. Numeric prefix ranges include qualified/literal codes sharing their first three digits; explicit exclusions subtract their actual full rule, not a whole prefix just because a literal starts there. For two ranges, compare their prefix intersection after subtracting prefix-range exclusions; finite exact-code exclusions cannot erase an entire prefix. A range versus an exact leaf overlaps only if the leaf is covered and not excluded. Leaf equality uses typed full values. Source region labels do not block explicit exact-code exclusions.

  V1 range presentations are three-digit examples. Conservatively remove any prefix containing a narrower different-belt exclusion from available_range_prefixes; this protects a whole-prefix example without redefining source coverage. Empty eligible examples fail invalid_presentation; do not invent longer codes. Validate context/route/presentation agreement: suffix-only questions have matching endings; +1/EAM use an ordinary code with no combined marker; named destinations have routing_code=None and their own named token. Reject unsupported ambiguity. This is not a general postal-address validator.
- [x] **Step 4: Verify green.** Run focused coverage/loading tests, then full backend discovery. Include inclusive endpoint, disjoint-range and same-literal/different-region cases.
- [x] **Step 5: Commit coverage, loader hook and coverage fixtures/tests.** Suggested message: `feat: validate ranked routing coverage and presentation safety`.

## Task 3: Export and audit the complete reviewed V1 artifact

**Files:** create `tools/export_ranked_v1.py`, `backend/data/ranked/routes-v1.json`, `backend/data/ranked/manifest.json`, `backend/tests/test_ranked_data.py` and `backend/tests/fixtures/ranked/initial-17-copy.json`.

**Interfaces:** consumes Tasks1/2; produces `export_reviewed_bank(output_dir: Path, *, repo_root: Path=REPO_ROOT) -> ExportReport`, with ExportReport fields bank_path, manifest_path, question_count and immutable review_ref_to_id pairs. CLI: `python -m tools.export_ranked_v1 --output-dir backend/data/ranked`. This authoring tool reads the approved review JSON and initial17 wording sheet; runtime never reads them.

- [x] **Step 1: Write failing data/export tests.** Copy original17 EN/ES cells into the independent literal fixture and check it against the approved sheet; do not derive expected copy using the exporter. Expanded266 expectations come directly from their approved review records.

```python
def test_full_artifact_preserves_approved_content(self):
    report = export_reviewed_bank(self.output_dir)
    bank = load_bank(report.bank_path, expected_revision='ranked-routes-v1',
                     expected_sha256=read_manifest_pin(report.manifest_path))
    self.assertEqual(len(bank.questions), 283)
    self.assertEqual(Counter(q.difficulty for q in bank.questions),
                     {'Easy':103, 'Medium':127, 'Hard':53})
    self.assertEqual(by_ref(bank,'G74').rule, RouteRule('exact_literal',('833 9-7',)))
    self.assertEqual(by_ref(bank,'S47').presentation.routing_code, '900')
```

Define `read_manifest_pin(path) -> str` in test helpers to read the single expected revision entry. Add tests: `test_original17_copy_and_ids_map_once`; `test_all266_expanded_copies_match_verbatim`; `test_no_CHECK_or_photo_is_exported`; `test_export_refuses_unapproved_content`; `test_export_refuses_existing_output_without_writes`; `test_export_is_reproducible_across_output_directories`; `test_all20_approved_examples_are_preserved`; `test_all_source_rows_are_accounted_for`. Compare every question's service/source fields/answer/label/copy against independent approved references, not only totals.

- [x] **Step 2: Verify red.** Run `backend/.venv/bin/python -m unittest backend.tests.test_ranked_data -v`; missing exporter/artifact must fail before creating it.
- [x] **Step 3: Implement the authoring export and create the initial files.** Require complete owner approval in both languages. Interpret metadata before raw code syntax: six exact literals first; +1/EAM become any_route with separate mode; endings become suffix rules; five named destinations remain named; four-digit qualified codes remain structured prefix/digit; numeric source rows become prefix_range, including single prefixes. Expected profiles:174 prefix_range,85 qualified_code,6 exact_literal,8 suffix,5 named_destination,5 any_route. If a true duplicate/unsupported meaning appears, abort for targeted owner review rather than silently merge/drop/re-rank.

  Resolve listed numeric exclusions from the reviewed source under the approved precedence policy, retaining full exact literals and explicit range exceptions. Do not invent priority between conflicting primary rows. Preserve all20 approved display codes. For other range rules choose the lowest available three-digit prefix deterministically; keep their already-approved range-level feedback unchanged. There is no random within-rule code generation in V1, so code-specific feedback cannot drift. Qualified/literal displays retain source punctuation; +1 keeps its approved NY109 examples without making NY a rule condition. Implementation defaults for plan review: suffix displays use NY109 1S/109 2S; EAM displays NDA EAM with ordinary code109/NY, separate from source label ALL 1DA EAM. Named destinations have no invented numeric routing code. These presentation defaults follow the approved universal rules; report all resulting codes in the Task3 audit for inspection.

  Emit bank_revision=`ranked-routes-v1`, schema_version=1 and question_revision=1. Manifest is `{schema_version:1,banks:[{revision,file,sha256}]}`; pin the canonical JSON digest. Sort output deterministically. Validate in memory before writing; output_dir must not already exist and file creation is exclusive. No --force/overwrite path. Future corrections use new files/revisions, not a rerun over published V1.
- [x] **Step 4: Verify green and inspect data.** Run focused tests plus full backend discovery. Record 283 source-to-ID mappings, exact label/type totals, original17 preservation, all266 copy comparisons and all chosen presentations. Review the typed artifact instead of trusting count alone. Keep the review docs as source evidence, not runtime input.
- [x] **Step 5: Commit exporter, versioned data, independent copy fixture and data tests.** Suggested message: `feat: add reviewed ranked routes v1 artifact`.

## Task 4: Version catalog and immutable revision boundaries

**Files:** create `backend/ranked_bank/catalog.py` and `backend/tests/test_ranked_catalog.py`; extend __init__.py, identity.py/helper fixtures only as required by the interfaces below.

**Interfaces:** consumes the pinned loader and content digest; produces immutable `Catalog(banks: tuple[Bank,...])` with `get(revision: str) -> Bank`, `load_catalog(manifest_path: Path) -> Catalog`, and `load_reviewed_bank(revision: str='ranked-routes-v1') -> Bank`. Default manifest path is resolved from the module to `backend/data/ranked/manifest.json`, never from the current working directory.

- [x] **Step 1: Write failing catalog tests.** Define helper `write_catalog_fixture(directory, payloads: Sequence[dict]) -> Path` to write test version files and pins. Same canonical ID/revision may occur in multiple banks only with identical stored question content.

```python
def test_changed_content_cannot_reuse_question_revision(self):
    first = raw_bank(raw_question('T1'), revision='fixture-v1')
    second = deepcopy(first); second['bank_revision'] = 'fixture-v2'
    second['questions'][0]['copy']['en']['explanation'] = 'Changed feedback.'
    manifest = write_catalog_fixture(self.directory, [first, second])
    with self.assertRaises(BankValidationError) as error:
        load_catalog(manifest)
    self.assertEqual(error.exception.code, 'revision_reused')
```

Add tests: `test_new_question_revision_can_coexist_with_old`; `test_duplicate_bank_revision_is_rejected`; `test_manifest_pin_and_filename_are_checked` (basename-only JSON files; no absolute/traversal fallback); `test_unknown_revision_never_falls_back`; `test_loading_from_cwd_with_spaces`; `test_catalog_has_no_mutable_nested_data`. Load real V1 and tiny independent fixture versions.

- [x] **Step 2: Verify red.** Run `backend/.venv/bin/python -m unittest backend.tests.test_ranked_catalog -v`.
- [x] **Step 3: Implement catalog validation.** Validate every pin/revision and compare stored content digests for every reused `(canonical_id,question_revision)` across manifest banks. Fail revision reuse with changed content; do not use a process-local seen-ID cache as a substitute for persisted artifact history. Preserve old files/records; no database is introduced.
- [x] **Step 4: Verify green.** Run catalog tests plus full backend discovery. Confirm loading another version never mutates the previously loaded bank. Future durable assignment/version constraints remain Issue6.
- [x] **Step 5: Commit catalog, exports and catalog tests.** Suggested message: `feat: add pinned ranked bank revision catalog`.

## Task 5: Complete randomized 5/5/5 selection, snapshots and developer check

**Files:** create `backend/ranked_bank/selection.py`, `backend/ranked_bank/check.py`, `backend/tests/test_ranked_selection.py`; extend __init__.py/ranked_helpers.py; update `backend/README.md` with the verified bank commands.

**Interfaces:** consumes validated Bank/Question records and rules_overlap; produces `select_assignment(bank: Bank, *, rng: random.Random|None=None) -> AssignmentSnapshot`, `serialize_assignment(snapshot: AssignmentSnapshot) -> dict[str,object]` and `check.main(argv: Sequence[str]|None=None) -> int`. Snapshot fields are defined in the shared contract. Serialization is an internal full snapshot (includes answers/copy), not a public question DTO.

- [x] **Step 1: Write failing selection tests.** Helpers use the real loader. `make_trap_bank(directory) -> Bank` contains six Easy candidates (five disjoint prefixes001–005 plus a broad100–199 trap), six Medium prefixes110–115, six Hard prefixes210–215, all ordinary Ground and the same valid GOLD answer. Use review refs E1–E5 for the small Easy rules, TRAP for the broad Easy rule, M1–M6 and H1–H6 for the other pools. Each helper call uses a fresh temporary subdirectory. The trap makes five Medium questions impossible; a complete set exists without it. `make_unavailable_bank(directory) -> Bank` has five overlapping Easy ranges100–199/101–199/102–199/103–199/104–199, five disjoint Medium301–305 and Hard401–405, all GOLD:raw counts suffice but compatible selection does not.

```python
def test_complete_search_does_not_get_stuck_on_a_greedy_choice(self):
    for seed in range(20):
        snapshot = select_assignment(make_trap_bank(self.directory), rng=Random(seed))
        self.assertEqual(Counter(q.difficulty for q in snapshot.questions),
                         {'Easy':5, 'Medium':5, 'Hard':5})
        self.assertNotIn('TRAP', {q.source.review_ref for q in snapshot.questions})

def test_no_partial_assignment_when_counts_are_incompatible(self):
    with self.assertRaises(BankUnavailableError):
        select_assignment(make_unavailable_bank(self.directory), rng=Random(42))
```

Add tests: `test_fewer_than_five_in_a_category_is_unavailable`; `test_seeded_selection_is_reproducible`; `test_inputs_are_not_shuffled_or_mutated`; `test_unique_ids_and_disjoint_effective_coverage`; `test_real_V1_over_50_seeds` (15,5/5/5,no duplicates, varying membership and valid fixed presentations); `test_every_candidate_is_reachable_in_unconstrained_6_each_fixture` (100 deterministic seeds); `test_old_snapshot_survives_new_bank_version`; `test_serialized_snapshot_is_a_defensive_copy`; `test_approved_code_specific_feedback_stays_paired` (all20 code values/copy unchanged); `test_check_cli_returns_counts_and_no_partial_output_on_error`.

- [x] **Step 2: Verify red.** Run `backend/.venv/bin/python -m unittest backend.tests.test_ranked_selection -v`.
- [x] **Step 3: Implement complete compatibility search and snapshots.** Copy/shuffle candidate pools; use SystemRandom by default and injected Random for tests. Backtrack with remaining-quota/eligible-count pruning, memoized failed states and a most-constrained-difficulty choice (tie order Easy,Medium,Hard). Do not return unavailable solely because a greedy/random first choice failed; do not report a search-time budget as proof of impossibility. Select exactly5 each and shuffle final order. Preserve the bank and fixed presentation/copy, then return an immutable snapshot with bank revision/digest/source revision and complete selected questions. Serialize via a deep primitive copy. This helper does not create attempts/scores or implement database freezing; later callers must invoke it before starting an attempt.

  The CLI reads the reviewed manifest/bank and selects once: `python -m backend.ranked_bank.check --revision ranked-routes-v1 --seed 42`. Print JSON with bank_revision,bank_sha256,question_count=15,counts and selected review refs; no answer key. On invalid/unavailable bank exit nonzero with stderr and no partial assignment output. No server, port, employee data or database is needed.
- [ ] **Step 4: Verify green on Mac, hosted Windows and with the owner.** Run backend discovery, `node --test tests/*.test.mjs`, `backend/.venv/bin/python -m pip check`, the CLI and `git diff --check`. Current baseline is386 Node checks and10 backend checks; report the actual new totals rather than reusing those numbers. CI must pass at the final PR head. On the Windows computer, from the repository root, have the owner run these read-only checks and compare results:

```powershell
& backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
& backend\.venv\Scripts\python.exe -m backend.ranked_bank.check --revision ranked-routes-v1 --seed 42
node --test tests/*.test.mjs
```

Expected CLI:15 questions and Easy5/Medium5/Hard5; repeated seed42 produces the same ordered review refs on both machines. Explain each command first; keep its output/limits in the PR. No browser/deployment claim follows from these backend checks.
- [x] **Step 5: Commit selection/CLI/tests/README and update the issue evidence.** Suggested message: `feat: prepare compatible ranked assignments from reviewed bank`. Keep #5 open for genuinely remaining gates/deferred tie content. Do not merge, publish, change branch protection or remove dependencies on the owner's behalf.

## Self-review and execution handoff

Execution note: all implementation steps and task reviews are complete. Task5 Step4 stays unchecked because the owner’s manual Windows commands have not yet been run; automated and hosted evidence is recorded separately. The handoff rules below describe the approved workflow, not a request to approve this plan again.

- Spec coverage:Tasks1/3 preserve identity/source/copy and all283 approved entries; Task2 implements type/exception/marker semantics; Tasks1/4 enforce immutable versions; Task5 proves compatible quotas/snapshots. Deferred work-methods content and future persistence/API/UI stay separate.
- Interface check:all tasks use the same Context,RouteRule,Question,Bank,AssignmentSnapshot fields and named helper functions above. Public exports are added as their owning tasks land. No task assumes a future API/DB helper exists.
- Review Focus maps to explicit tests in the owning tasks; the complete bank audit compares approved reference data, not expected values computed by the exporter. The tests/algorithms above are requirements for execution, not results already obtained.
- Execute sequentially on the shared branch. Preserve the owner's earlier task-agent implementation/review preference:use subagent-driven-development after plan approval, with a fresh implementer and required review gates for each task and a final whole-branch review. No concurrent writers to shared files. If the owner changes execution method, follow that instruction.
- Before implementation, the owner reviews this plan. After implementation, present the verified artifacts/changes and actual Windows/CI evidence for owner review. An unexpected semantic ambiguity blocks the affected work until clarified; it does not authorize silent content edits or re-ranking unchanged questions.
