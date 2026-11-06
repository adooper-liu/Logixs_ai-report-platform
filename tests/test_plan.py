"""Design-package regression tests only; no platform runtime is exercised."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plan_validator', ROOT / 'tools/validate_plan.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
        for rel in ['project.json'] + project['documents'] + project['design_contracts'] + project['examples'] + project.get('implementation_evidence', []):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        for module in project['modules']:
            target = self.root / module['path']
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / module['path'] / 'README.md', target / 'README.md')
        old_root = validator.ROOT
        validator.ROOT = self.root
        self.addCleanup(setattr, validator, 'ROOT', old_root)

    def modify(self, rel, action):
        path = self.root / rel
        doc = json.loads(path.read_text(encoding='utf-8'))
        action(doc)
        path.write_text(json.dumps(doc), encoding='utf-8')

    def check(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return validator.validate_plan()

    def test_valid_package(self):
        self.assertEqual(self.check(), 0)

    def test_cross_project_input_rejected(self):
        self.modify('examples/synthetic-platform-plan.json', lambda d: d['pipelines'][0]['inputs'][0].update(stream_id='support-tickets'))
        with self.assertRaisesRegex(ValueError, 'Cross-project input'):
            self.check()

    def test_production_claim_rejected(self):
        self.modify('project.json', lambda d: d.update(production_ready=True))
        with self.assertRaisesRegex(ValueError, 'production_ready'):
            self.check()

    def test_runtime_without_scope_rejected(self):
        self.modify('project.json', lambda d: d.update(runtime_scope='full_platform'))
        with self.assertRaisesRegex(ValueError, 'Runtime scope'):
            self.check()

    def test_premature_p0_acceptance_rejected(self):
        self.modify('project.json', lambda d: d['phase_progress']['P0'].update(acceptance_complete=True))
        with self.assertRaisesRegex(ValueError, 'acceptance is incomplete'):
            self.check()

    def test_missing_implementation_evidence_rejected(self):
        self.modify('project.json', lambda d: d['implementation_evidence'].append('missing-runtime.py'))
        with self.assertRaisesRegex(ValueError, 'Missing implementation evidence'):
            self.check()

    def test_external_path_rejected(self):
        self.modify('project.json', lambda d: d['documents'].append('../outside.md'))
        with self.assertRaisesRegex(ValueError, 'Path leaves'):
            self.check()

    def test_broken_doc_link_rejected(self):
        with (self.root / 'README.md').open('a', encoding='utf-8') as handle:
            handle.write('\n[broken](missing-document.md)\n')
        with self.assertRaisesRegex(ValueError, 'Broken local link'):
            self.check()

    def test_snapshot_scope_required(self):
        self.modify('examples/synthetic-platform-plan.json', lambda d: d['pipelines'][1]['inputs'][0].update(scope_required_for_replace=False))
        with self.assertRaisesRegex(ValueError, 'explicit scope'):
            self.check()

    def test_duplicate_proposal_rejected(self):
        self.modify('examples/synthetic-ai-recommendation.json', lambda d: d['proposals'].append(copy.deepcopy(d['proposals'][0])))
        with self.assertRaisesRegex(ValueError, 'Duplicate proposal'):
            self.check()

    def test_semantically_invalid_decimal_rejected(self):
        def mutate(doc):
            p = doc['proposals'][0]
            p.update(operator='cast_decimal', impact='type_conversion')
            p['parameters'].update(precision=4, scale=6, locale='en-US')
        self.modify('examples/synthetic-ai-recommendation.json', mutate)
        with self.assertRaisesRegex(ValueError, 'precision/scale'):
            self.check()

    def test_append_identity_required(self):
        self.modify('examples/synthetic-platform-plan.json', lambda d: d['pipelines'][1]['inputs'][1].pop('idempotency_identity'))
        with self.assertRaisesRegex(ValueError, 'Append requires identity'):
            self.check()

    def test_forced_review_rejected(self):
        self.modify('examples/synthetic-platform-plan.json', lambda d: d['pipelines'][0].update(manual_business_review_required=True))
        with self.assertRaisesRegex(ValueError, 'mandatory review'):
            self.check()


if __name__ == '__main__':
    unittest.main()
