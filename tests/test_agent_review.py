import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_agents import report, review_records


class AgentReviewTests(unittest.TestCase):
    def test_every_current_definition_has_a_traceable_review_record(self):
        records, errors = review_records()
        self.assertFalse(errors)
        self.assertGreaterEqual(len(records), 161)
        self.assertEqual((ROOT / 'docs/AGENT_REVIEW.md').read_text(), report())

    def fixture(self):
        # Only one source is copied per record, keeping the review boundary real.
        import shutil
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'repo'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        return root

    def test_unreviewed_prompt_edit_is_detected(self):
        root = self.fixture()
        path = root / 'categories/04-quality-security/agents/code-reviewer.md'
        path.write_text(path.read_text().replace('do not modify', 'modify'))
        # Make the test independent of the exact prose being replaced.
        path.write_text(path.read_text() + '\nNew behavior requiring review.\n')
        self.assertTrue(any('code-reviewer: source changed' in error for error in review_records(root)[1]))

    def test_read_only_review_cannot_silently_gain_shell_execution(self):
        root = self.fixture()
        path = root / 'categories/04-quality-security/agents/code-reviewer.md'
        path.write_text(path.read_text().replace('tools: Read, Glob, Grep', 'tools: Read, Glob, Grep, Bash'))
        records_path = root / 'evals/cases.jsonl'
        records = [json.loads(line) for line in records_path.read_text().splitlines()]
        for record in records:
            if record['agent'] == 'code-reviewer':
                record['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        records_path.write_text(''.join(json.dumps(record) + '\n' for record in records))
        self.assertTrue(any('inspection profile' in error for error in review_records(root)[1]))

    def test_missing_review_is_detected(self):
        root = self.fixture()
        path = root / 'evals/cases.jsonl'
        path.write_text('\n'.join(path.read_text().splitlines()[1:]) + '\n')
        self.assertTrue(any('coverage differs' in error for error in review_records(root)[1]))


if __name__ == '__main__':
    unittest.main()
