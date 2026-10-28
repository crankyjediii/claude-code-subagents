from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from sync import generated, inventory
from validate import validate


class CollectionTests(unittest.TestCase):
    def test_complete_distribution_and_contained_plugin_paths(self):
        config, agents = inventory()
        self.assertEqual(len(agents), 170)
        self.assertEqual(len(config['categories']), 10)
        self.assertEqual(validate(), [])
        for category in config['categories']:
            folder = ROOT / 'categories' / category['directory']
            manifest = json.loads((folder / '.claude-plugin/plugin.json').read_text())
            self.assertEqual(manifest['name'], category['plugin'])
            agents_in_plugin = list((folder / 'agents').glob('*.md'))
            self.assertEqual(len(agents_in_plugin), 17)
            for agent in agents_in_plugin:
                self.assertTrue(agent.resolve().is_relative_to(folder.resolve()))

    def test_generation_is_deterministic_and_clean(self):
        self.assertEqual(generated(), generated())
        for relative, content in generated().items():
            self.assertEqual((ROOT / relative).read_text(), content, relative)

    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'repo'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        return root

    def test_agent_edit_requires_catalog_refresh(self):
        root = self.fixture()
        agent = root / 'categories/01-core-development/agents/api-designer.md'
        agent.write_text(agent.read_text() + '\nAdditional contract check.\n')
        self.assertTrue(any('catalog.tsv' in error for error in validate(root)))

    def test_duplicate_agent_name_is_rejected(self):
        root = self.fixture()
        source = root / 'categories/01-core-development/agents/api-designer.md'
        shutil.copyfile(source, root / 'categories/02-language-specialists/agents/api-designer.md')
        with self.assertRaisesRegex(ValueError, 'duplicate agent'):
            inventory(root)

    def test_numbering_mismatch_is_rejected(self):
        root = self.fixture()
        path = root / 'collection.json'
        config = json.loads(path.read_text())
        config['categories'].reverse()
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'ordering'):
            inventory(root)

    def test_new_agent_updates_count_index_catalog_and_manifest(self):
        root = self.fixture()
        source = root / 'categories/01-core-development/agents/api-designer.md'
        text = source.read_text().replace('api-designer', 'api-contract-checker')
        (source.parent / 'api-contract-checker.md').write_text(text)
        outputs = generated(root)
        self.assertIn('171 standalone', outputs['README.md'])
        self.assertIn('subagents: 171', outputs['docs/agent-count.svg'])
        self.assertIn('api-contract-checker', outputs['tools/catalog.tsv'])
        self.assertIn('18 agents', outputs['categories/01-core-development/README.md'])

    def test_broken_local_link_is_rejected(self):
        root = self.fixture()
        path = root / 'CONTRIBUTING.md'
        path.write_text(path.read_text() + '\n[Missing file](missing.md)\n')
        self.assertTrue(any('missing.md' in error for error in validate(root)))


if __name__ == '__main__':
    unittest.main()
