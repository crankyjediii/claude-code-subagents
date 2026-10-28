from __future__ import annotations

import io
import json
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from release import build, snapshot, tar_gz_bytes, notes
from check_release import verify_checksums, extract

COMMIT = 'a' * 40
LICENSE = b'MIT License\n\nCopyright test contributors\n'


def fixture(include_license=True):
    files = {
        'collection.json': (json.dumps({'version': '1.1.0', 'repository': 'testing/fixture', 'validation': {'claude-code': '2.1.309'},
                                       'categories': [{'directory': '01-testing', 'plugin': 'test-plugin'}]}).encode(), 0o644),
        'LICENSE': (LICENSE, 0o644),
        'CHANGELOG.md': (b'# Changelog\n\n## 1.1.0\n\n- Add tested release assets.\n', 0o644),
        'install-agents.sh': (b"#!/usr/bin/env bash\nREF='main'\n", 0o755),
        'categories/01-testing/.claude-plugin/plugin.json': (b'{"name":"test-plugin","version":"1.1.0"}', 0o644),
        'categories/01-testing/agents/example.md': (b'agent definition\n', 0o644),
    }
    if include_license:
        files['categories/01-testing/LICENSE'] = (LICENSE, 0o644)
    return tar_gz_bytes(files, '')


class ReleaseTests(unittest.TestCase):
    def test_build_is_byte_identical_for_identical_committed_inputs(self):
        self.assertEqual(build(fixture(), COMMIT), build(fixture(), COMMIT))

    def test_every_plugin_carries_license_and_preserves_agent_bytes(self):
        artifacts = build(fixture(), COMMIT)
        with zipfile.ZipFile(io.BytesIO(artifacts['test-plugin-1.1.0.zip'])) as archive:
            self.assertEqual(archive.read('test-plugin/LICENSE'), LICENSE)
            self.assertEqual(archive.read('test-plugin/agents/example.md'), b'agent definition\n')

    def test_missing_plugin_license_blocks_build(self):
        with self.assertRaisesRegex(ValueError, 'license is missing'):
            build(fixture(False), COMMIT)

    def test_downloadable_installer_is_pinned_while_source_preserves_default(self):
        artifacts = build(fixture(), COMMIT)
        self.assertIn(f"REF='{COMMIT}'".encode(), artifacts['install-agents.sh'])
        with zipfile.ZipFile(io.BytesIO(artifacts['claude-code-subagents-1.1.0.zip'])) as archive:
            self.assertIn(b"REF='main'", archive.read('claude-code-subagents-1.1.0/install-agents.sh'))
            self.assertEqual((archive.getinfo('claude-code-subagents-1.1.0/install-agents.sh').external_attr >> 16) & 0o777, 0o755)

    def test_tag_version_mismatch_blocks_build(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            build(fixture(), COMMIT, 'v9.0.0')

    def test_manifest_and_checksums_cover_assets_and_detect_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, data in build(fixture(), COMMIT).items():
                (root / name).write_bytes(data)
            self.assertEqual(verify_checksums(root)['commit'], COMMIT)
            (root / 'install-agents.sh').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                verify_checksums(root)

    def test_source_snapshot_rejects_symlinks_and_path_traversal(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)):
            with self.subTest(name=name):
                raw = io.BytesIO()
                with tarfile.open(fileobj=raw, mode='w') as archive:
                    member = tarfile.TarInfo(name)
                    member.type, member.linkname = kind, '/outside'
                    archive.addfile(member)
                with self.assertRaises(ValueError):
                    snapshot(raw.getvalue())

    def test_zip_extraction_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as source:
                source.writestr('../escape', 'bad')
            with self.assertRaisesRegex(ValueError, 'Unsafe ZIP member'):
                extract(archive, root / 'extracted')
            self.assertFalse((root / 'escape').exists())

    def test_notes_are_version_specific_and_do_not_claim_model_execution(self):
        content = notes(fixture(), COMMIT)
        self.assertIn('Add tested release assets.', content)
        self.assertIn(COMMIT, content)
        self.assertIn('not executed model benchmarks', content)


if __name__ == '__main__':
    unittest.main()
