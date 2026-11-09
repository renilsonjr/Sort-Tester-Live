"""Independent approved-source comparisons for the one-time V1 export."""
import json
from collections import Counter
from pathlib import Path
import re
import tempfile
import unittest
from tools.export_ranked_v1 import export_reviewed_bank
from backend.ranked_bank.loading import load_bank

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('docs/superpowers/specs/2026-11-08-ranked-full-chart-review.json')
def read_manifest_pin(path):
    manifest=json.loads(path.read_text(encoding='utf-8'))
    assert len(manifest['banks']) == 1
    assert manifest['banks'][0]['revision']=='ranked-routes-v1'
    return manifest['banks'][0]['sha256']

class ReviewedDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.output_dir=Path(self.tmp.name)/'bank'
        self.source=json.loads((ROOT/SOURCE).read_text(encoding='utf-8'))
    def export(self):
        report=export_reviewed_bank(self.output_dir)
        return report,load_bank(report.bank_path,expected_revision='ranked-routes-v1',expected_sha256=read_manifest_pin(report.manifest_path))
    def test_full_artifact_preserves_approved_content(self):
        report,bank=self.export(); self.assertEqual(report.question_count,283)
        self.assertEqual(Counter(q.difficulty for q in bank.questions),{'Easy':103,'Medium':127,'Hard':53})
        self.assertEqual(Counter(q.rule.kind for q in bank.questions),{'prefix_range':174,'qualified_code':85,'exact_literal':6,'suffix':8,'named_destination':5,'any_route':5})
        by={q.source.review_ref:q for q in bank.questions}
        self.assertEqual(by['G74'].rule.parts,('833 9-7',)); self.assertEqual(by['S47'].presentation.routing_code,'900')
    def test_original17_copy_and_ids_map_once(self):
        report,bank=self.export(); fixture=json.loads((ROOT/'backend/tests/fixtures/ranked/initial-17-copy.json').read_text(encoding='utf-8'))
        self.assertEqual(len(fixture),17); mapping=dict(report.review_ref_to_id)
        sheet=(ROOT/'docs/superpowers/specs/2026-11-08-ranked-question-wording-review.md').read_text(encoding='utf-8')
        for line in sheet.splitlines():
            cells=[cell.strip() for cell in line.split('|')[1:-1]]
            if cells and re.fullmatch('[EMH][1-7]',cells[0]):
                language='en' if len(cells)==7 else 'es'
                self.assertEqual(fixture[cells[0]][language]['explanation'],cells[-1])
        for q in bank.questions:
            if q.source.review_ref in fixture:
                for lang in ('en','es'):
                    self.assertEqual(vars_copy(getattr(q.text,lang)),fixture[q.source.review_ref][lang])
                self.assertEqual(mapping[q.source.review_ref],q.canonical_id)
    def test_all266_expanded_copies_match_verbatim(self):
        _,bank=self.export(); by={q.source.review_ref:q for q in bank.questions}; count=0
        for e in self.source['entries']:
            if 'wording' in e:
                count+=1
                for lang in ('en','es'):
                    self.assertEqual(vars_copy(getattr(by[e['approvedReview']].text,lang)),{k:e['wording'][lang][k] for k in ('prompt','explanation')})
        self.assertEqual(count,266)
    def test_no_CHECK_or_photo_is_exported(self):
        _,bank=self.export(); self.assertFalse(any(q.correct_belt=='CHECK' for q in bank.questions))
        self.assertEqual(set(p.name for p in self.output_dir.iterdir()),{'routes-v1.json','manifest.json'})
    def test_export_refuses_unapproved_content(self):
        root=Path(self.tmp.name)/'source'; (root/SOURCE.parent).mkdir(parents=True)
        self.source['entries'][0]['difficultyStatus']='pending'
        (root/SOURCE).write_text(json.dumps(self.source),encoding='utf-8')
        with self.assertRaises(ValueError):export_reviewed_bank(self.output_dir,repo_root=root)
        self.assertFalse(self.output_dir.exists())
    def test_export_refuses_unapproved_translation(self):
        root=Path(self.tmp.name)/'source'; (root/SOURCE.parent).mkdir(parents=True)
        next(e for e in self.source['entries'] if 'wording' in e)['wording']['es']['approvalStatus']='pending'
        (root/SOURCE).write_text(json.dumps(self.source),encoding='utf-8')
        with self.assertRaises(ValueError):export_reviewed_bank(self.output_dir,repo_root=root)
        self.assertFalse(self.output_dir.exists())
    def test_export_refuses_combined_markers_without_output(self):
        for code in ('ends 1S', 'ends 2S', 'ALL 1DA EAM'):
            with self.subTest(code=code):
                root=Path(self.tmp.name)/code.replace(' ', '-')
                (root/SOURCE.parent).mkdir(parents=True)
                source=json.loads((ROOT/SOURCE).read_text(encoding='utf-8'))
                entry=next(e for e in source['entries'] if e['code']==code and e['service']=='Next Day Air')
                entry['destinationModifier']='+1'
                (root/SOURCE).write_text(json.dumps(source),encoding='utf-8')
                sheet=Path('docs/superpowers/specs/2026-11-08-ranked-question-wording-review.md')
                (root/sheet).write_text((ROOT/sheet).read_text(encoding='utf-8'),encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'combined markers'):
                    export_reviewed_bank(self.output_dir,repo_root=root)
                self.assertFalse(self.output_dir.exists())
    def test_export_refuses_existing_output_without_writes(self):
        self.output_dir.mkdir(); (self.output_dir/'sentinel').write_text('keep',encoding='utf-8')
        with self.assertRaises(FileExistsError):export_reviewed_bank(self.output_dir)
        self.assertEqual(list(self.output_dir.iterdir()),[self.output_dir/'sentinel'])
    def test_export_is_reproducible_across_output_directories(self):
        self.export(); other=Path(self.tmp.name)/'other'; export_reviewed_bank(other)
        for name in ('routes-v1.json','manifest.json'):self.assertEqual((self.output_dir/name).read_bytes(),(other/name).read_bytes())
    def assert_published_artifacts_equal_export(self, published_dir):
        for name in ('routes-v1.json','manifest.json'):
            # Git may convert tracked JSON to CRLF in a Windows checkout.
            # Preserve every other byte, including formatting and Unicode.
            fresh=(self.output_dir/name).read_bytes().replace(b'\r\n',b'\n')
            published=(published_dir/name).read_bytes().replace(b'\r\n',b'\n')
            self.assertEqual(fresh,published)
    def test_published_artifact_equals_fresh_export(self):
        self.export()
        self.assert_published_artifacts_equal_export(ROOT/'backend/data/ranked')
    def test_published_artifact_comparison_accepts_crlf_checkout(self):
        self.export()
        checkout=Path(self.tmp.name)/'crlf-checkout'; checkout.mkdir()
        for name in ('routes-v1.json','manifest.json'):
            data=(ROOT/'backend/data/ranked'/name).read_bytes().replace(b'\r\n',b'\n')
            self.assertIn(b'\n',data)
            (checkout/name).write_bytes(data.replace(b'\n',b'\r\n'))
        self.assert_published_artifacts_equal_export(checkout)
        for name in ('routes-v1.json','manifest.json'):
            with self.subTest(changed_artifact=name):
                path=checkout/name; original=path.read_bytes()
                path.write_bytes(original+b' ')
                with self.assertRaises(AssertionError):
                    self.assert_published_artifacts_equal_export(checkout)
                path.write_bytes(original)
    def test_all20_approved_examples_are_preserved(self):
        _,bank=self.export(); by={q.source.review_ref:q for q in bank.questions}; count=0
        for e in self.source['entries']:
            if 'rangeExampleReview' in e:
                count+=1;self.assertEqual(by[e['approvedReview']].presentation.routing_code,e['rangeExampleReview']['displayedRoutingCode'])
        self.assertEqual(count,20)
    def test_all_source_rows_are_accounted_for(self):
        _,bank=self.export(); by={q.source.review_ref:q for q in bank.questions}
        self.assertEqual(len(by),283); self.assertEqual(set(by),{e['approvedReview'] for e in self.source['entries']})
        for e in self.source['entries']:
            q=by[e['approvedReview']]
            self.assertEqual(q.context.service,{'Ground':'GND','Next Day Air':'NDA','2 Day Air':'2DA','3 Day Select':'3DS'}[e['service']])
            self.assertEqual(q.source.source_revision,self.source['sourceRevision'])
            if 'rangeExampleReview' in e:
                self.assertTrue({x['sourceReviewRef'] for x in e['rangeExampleReview']['sourceExclusions']} <= {x.review_ref for x in q.exclusions})
            self.assertEqual((q.source.row_id,q.source.row_kind,q.source.state_label,q.source.code_label,q.source.provenance,q.difficulty,q.correct_belt),(e['id'],e['kind'],e['state'],e['code'],e['provenance'],e['difficulty'],e['expectedBelt']))

def vars_copy(c):return {'prompt':c.prompt,'explanation':c.explanation}
