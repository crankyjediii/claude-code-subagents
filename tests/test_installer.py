from __future__ import annotations

import hashlib
import os
import pty
import select
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'install-agents.sh'
AGENT_NAMES = {path.stem for path in (ROOT / 'categories').glob('*/agents/*.md')}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent tests ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.target = self.base / 'target with spaces'
        self.home = self.base / 'isolated home'
        self.home.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'TMPDIR': str(self.base)}

    def run_cli(self, *args, success=True, script=SCRIPT, env=None):
        result = subprocess.run(['/bin/bash', str(script), *args, '--target', str(self.target)],
                                cwd=self.base, env=env or self.env, text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def install(self, name='python-specialist', **kwargs):
        return self.run_cli('--install', name, **kwargs)

    def agent(self, name='python-specialist'):
        return self.target / f'{name}.md'

    def mock_remote(self):
        copied = self.base / 'standalone.sh'
        shutil.copyfile(SCRIPT, copied)
        mock_bin = self.base / 'bin'
        mock_bin.mkdir()
        curl = mock_bin / 'curl'
        curl.write_text('''#!/usr/bin/env python3
import os, pathlib, shutil, sys
args = sys.argv[1:]
assert args[args.index('--proto') + 1] == '=https'
assert args[args.index('--proto-redir') + 1] == '=https'
assert '--fail' in args and '--location' in args
url = next(a for a in args if a.startswith('https://'))
prefix = 'https://raw.githubusercontent.com/testing/fixture/test/'
assert url.startswith(prefix), url
relative = url[len(prefix):]
output = pathlib.Path(args[args.index('-o') + 1])
if os.environ.get('MOCK_FETCH_FAIL') == relative:
    output.write_text('partial transfer')
    sys.exit(22)
source = pathlib.Path(os.environ['FIXTURE_ROOT']) / relative
if relative.endswith('/python-specialist.md') and os.environ.get('MOCK_DURING_DOWNLOAD_EDIT'):
    target = pathlib.Path(os.environ['MOCK_DURING_DOWNLOAD_EDIT'])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('created during download')
shutil.copyfile(source, output)
if os.environ.get('MOCK_FETCH_TAMPER') == relative:
    with output.open('a') as stream: stream.write('tampered content')
if relative == 'tools/catalog.tsv' and os.environ.get('MOCK_BAD_PATH'):
    output.write_text(output.read_text().replace('categories/01-core-development/agents/api-designer.md', '../escape.md'))
''')
        curl.chmod(0o755)
        env = {**self.env, 'PATH': str(mock_bin) + os.pathsep + self.env['PATH'], 'FIXTURE_ROOT': str(ROOT)}
        return copied, env

    def remote(self, *args, **kwargs):
        copied, env = self.mock_remote()
        env.update(kwargs.pop('changes', {}))
        return self.run_cli('--repo', 'testing/fixture', '--ref', 'test', *args, script=copied, env=env, **kwargs)

    def test_help_does_not_create_target(self):
        result = self.run_cli('--help')
        self.assertIn('--uninstall', result.stdout)
        self.assertFalse(self.target.exists())

    def test_catalog_lists_every_agent_without_target_changes(self):
        result = self.run_cli('--list')
        self.assertEqual({line.split()[0] for line in result.stdout.splitlines()}, AGENT_NAMES)
        self.assertFalse(self.target.exists())

    def test_local_install_and_uninstall_with_spaces(self):
        self.install()
        original = ROOT / 'categories/02-language-specialists/agents/python-specialist.md'
        self.assertEqual(self.agent().read_bytes(), original.read_bytes())
        marker = self.target / '.voltagent-state/python-specialist'
        self.assertEqual(marker.read_text().strip(), hashlib.sha256(original.read_bytes()).hexdigest())
        self.run_cli('--uninstall', 'python-specialist')
        self.assertFalse(self.agent().exists())
        self.assertFalse(marker.exists())

    def test_multiple_names_and_duplicate_selection(self):
        self.install('python-specialist,code-reviewer,python-specialist')
        self.assertEqual(len(list(self.target.glob('*.md'))), 2)

    def test_category_plugin_and_folder_alias(self):
        self.run_cli('--install', '--category', 'voltagent-lang')
        expected = {path.stem for path in (ROOT / 'categories/02-language-specialists/agents').glob('*.md')}
        self.assertEqual({path.stem for path in self.target.glob('*.md')}, expected)
        self.run_cli('--uninstall', '--category', '02-language-specialists')
        self.assertFalse(list(self.target.glob('*.md')))

    def test_install_all_then_uninstall_only_managed_files(self):
        self.run_cli('--install', '--all')
        self.assertEqual({path.stem for path in self.target.glob('*.md')}, AGENT_NAMES)
        unrelated = self.target / 'personal.md'
        unrelated.write_text('my agent')
        self.run_cli('--uninstall', '--all')
        self.assertEqual(list(self.target.glob('*.md')), [unrelated])

    def test_install_dry_run_creates_nothing(self):
        result = self.run_cli('--install', '--all', '--dry-run')
        self.assertEqual(len(result.stdout.splitlines()), len(AGENT_NAMES))
        self.assertFalse(self.target.exists())

    def test_uninstall_dry_run_keeps_file_and_marker(self):
        self.install()
        self.run_cli('--uninstall', 'python-specialist', '--dry-run')
        self.assertTrue(self.agent().exists())
        self.assertTrue((self.target / '.voltagent-state/python-specialist').exists())

    def test_unmanaged_conflict_refuses_entire_batch(self):
        self.target.mkdir()
        self.agent().write_text('custom')
        self.install('code-reviewer,python-specialist', success=False)
        self.assertEqual(self.agent().read_text(), 'custom')
        self.assertFalse(self.agent('code-reviewer').exists())

    def test_force_install_preserves_backup(self):
        self.target.mkdir()
        self.agent().write_text('custom')
        self.run_cli('--install', 'python-specialist', '--force')
        backups = list((self.target / '.voltagent-backups').glob('*/python-specialist.md'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'custom')

    def test_modified_managed_agent_is_preserved(self):
        self.install()
        self.agent().write_text('edited')
        self.install(success=False)
        self.run_cli('--uninstall', 'python-specialist', success=False)
        self.assertEqual(self.agent().read_text(), 'edited')

    def test_force_uninstall_backs_up_modified_file(self):
        self.install()
        self.agent().write_text('edited')
        self.run_cli('--uninstall', 'python-specialist', '--force')
        backups = list((self.target / '.voltagent-backups').glob('*/python-specialist.md'))
        self.assertEqual(backups[0].read_text(), 'edited')
        self.assertFalse(self.agent().exists())

    def test_repeated_install_is_idempotent(self):
        self.install()
        self.install()
        self.assertFalse((self.target / '.voltagent-backups').exists())

    def test_managed_upgrade_backs_up_old_version(self):
        self.install()
        self.agent().write_text('old managed version')
        (self.target / '.voltagent-state/python-specialist').write_text(hashlib.sha256(self.agent().read_bytes()).hexdigest() + '\n')
        self.install()
        backup = next((self.target / '.voltagent-backups').glob('*/python-specialist.md'))
        self.assertEqual(backup.read_text(), 'old managed version')

    def test_uninstall_does_not_remove_unmanaged_file(self):
        self.target.mkdir()
        self.agent().write_text('personal')
        self.run_cli('--uninstall', 'python-specialist', '--force', success=False)
        self.assertEqual(self.agent().read_text(), 'personal')

    def test_installed_reports_modifications_and_missing_files(self):
        self.install('python-specialist,code-reviewer')
        self.agent().write_text('edited')
        self.agent('code-reviewer').unlink()
        result = self.run_cli('--installed')
        self.assertIn('modified', result.stdout)
        self.assertIn('missing', result.stdout)

    def test_global_and_project_targets(self):
        for flags, expected in [(['--global'], self.home / '.claude/agents'),
                                (['--project', str(self.base / 'a project')], self.base / 'a project/.claude/agents')]:
            result = subprocess.run(['/bin/bash', str(SCRIPT), '--install', 'python-specialist', *flags],
                                    cwd=self.base, env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((expected / 'python-specialist.md').is_file())

    def test_client_formats_lifecycle(self):
        import tomllib
        for client, extension in [('codex', 'toml'), ('cursor', 'md'), ('opencode', 'md')]:
            with self.subTest(client=client):
                self.run_cli('--client', client, '--install', 'python-specialist')
                file = self.target / f'python-specialist.{extension}'
                content = file.read_text()
                if client == 'codex':
                    data = tomllib.loads(content)
                    self.assertEqual(data['name'], 'python-specialist')
                    self.assertIn('You are the python specialist.', data['developer_instructions'])
                else:
                    self.assertIn('name: python-specialist', content)
                    self.assertNotIn('tools:', content.split('---')[1])
                    self.assertNotIn('model:', content.split('---')[1])
                    if client == 'opencode': self.assertIn('mode: subagent', content)
                self.run_cli('--client', client, '--install', 'python-specialist')
                self.assertFalse((self.target / '.voltagent-backups').exists())
                result = self.run_cli('--client', client, '--installed')
                self.assertIn('installed', result.stdout)
                file.write_text('customized')
                self.run_cli('--client', client, '--uninstall', '--all', success=False)
                self.run_cli('--client', client, '--uninstall', '--all', '--force')
                self.assertFalse(file.exists())
                backup = next((self.target / '.voltagent-backups').glob(f'*/python-specialist.{extension}'))
                self.assertEqual(backup.read_text(), 'customized')
                shutil.rmtree(self.target)

    def test_client_paths_and_argument_order(self):
        for client, global_path in [('codex', '.codex/agents'), ('cursor', '.cursor/agents'),
                                    ('opencode', '.config/opencode/agents')]:
            for scope in ('global', 'project'):
                flags = ['--global'] if scope == 'global' else ['--project', str(self.base / 'project')]
                result = subprocess.run(['/bin/bash', str(SCRIPT), *flags, '--client', client,
                                         '--install', 'python-specialist'], cwd=self.base,
                                        env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                target = self.home / global_path if scope == 'global' else self.base / 'project' / f'.{client}/agents'
                self.assertTrue((target / ('python-specialist.toml' if client == 'codex' else 'python-specialist.md')).exists())

    def test_unknown_client_is_rejected(self):
        self.run_cli('--client', 'unknown', '--install', '--all', success=False)
        self.assertFalse(self.target.exists())

    def test_noninteractive_without_action_has_clear_error(self):
        result = self.run_cli(success=False)
        self.assertIn('terminal', result.stderr)
        self.assertFalse(self.target.exists())

    def test_rejects_invalid_arguments_without_target_changes(self):
        cases = [('--install', '../escape'), ('--install', 'a,,b'), ('--install', 'missing-agent'),
                 ('--install', '--all', '--category', 'voltagent-lang'), ('--install',),
                 ('--repo', '../bad', '--list'), ('--ref', '../main', '--list'),
                 ('--list', '--category', 'missing'), ('--list', '--installed'), ('--unknown',),
                 ('--local', str(ROOT), '--standalone', '--list')]
        for args in cases:
            with self.subTest(args=args): self.run_cli(*args, success=False)
        self.assertFalse(self.target.exists())

    def test_rejects_agent_and_broken_symlinks_even_with_force(self):
        self.target.mkdir()
        external = self.base / 'external'
        external.write_text('preserve')
        for link_target in (external, self.base / 'missing'):
            with self.subTest(link_target=link_target):
                self.agent().symlink_to(link_target)
                self.run_cli('--install', 'python-specialist', '--force', success=False)
                self.agent().unlink()
        self.assertEqual(external.read_text(), 'preserve')

    def test_rejects_symlinked_target_parent(self):
        real = self.base / 'real'
        real.mkdir()
        linked = self.base / 'linked'
        linked.symlink_to(real, target_is_directory=True)
        self.target = linked / 'agents'
        self.install(success=False)
        self.assertFalse((real / 'agents').exists())

    def test_rejects_symlinked_state(self):
        self.target.mkdir()
        external = self.base / 'state'
        external.mkdir()
        (self.target / '.voltagent-state').symlink_to(external, target_is_directory=True)
        self.install(success=False)
        self.assertFalse(list(external.iterdir()))

    def test_rejects_directory_at_agent_path(self):
        self.agent().mkdir(parents=True)
        self.install(success=False)

    def test_remote_download_and_checksum(self):
        self.remote('--install', 'python-specialist')
        self.assertTrue(self.agent().read_text().startswith('---\nname: python-specialist'))
        self.assertFalse(list(self.base.glob('voltagent.*')))

    def test_failed_download_writes_no_agents(self):
        result = self.remote('--install', 'api-designer,python-specialist', success=False,
                             changes={'MOCK_FETCH_FAIL': 'categories/02-language-specialists/agents/python-specialist.md'})
        self.assertIn('Download failed', result.stderr)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.base.glob('voltagent.*')))

    def test_tampered_download_writes_no_agents(self):
        result = self.remote('--install', 'api-designer,python-specialist', success=False,
                             changes={'MOCK_FETCH_TAMPER': 'categories/02-language-specialists/agents/python-specialist.md'})
        self.assertIn('Checksum mismatch', result.stderr)
        self.assertFalse(self.target.exists())

    def test_rejects_catalog_path_traversal(self):
        result = self.remote('--install', '--all', success=False, changes={'MOCK_BAD_PATH': '1'})
        self.assertIn('Unsafe catalog path', result.stderr)
        self.assertFalse(self.target.exists())

    def test_offline_uninstall_with_standalone_copy(self):
        self.install()
        copied = self.base / 'offline.sh'
        shutil.copyfile(SCRIPT, copied)
        self.run_cli('--standalone', '--repo', 'missing/not-used', '--uninstall', 'python-specialist', script=copied)
        self.assertFalse(self.agent().exists())

    def test_all_uninstall_with_empty_target_is_harmless(self):
        self.run_cli('--uninstall', '--all')
        self.assertFalse(self.target.exists())

    def test_category_uninstall_removes_only_installed_members(self):
        self.install('python-specialist')
        unrelated = self.agent('ruby-specialist')
        unrelated.write_text('personal ruby agent')
        self.run_cli('--uninstall', '--category', 'voltagent-lang')
        self.assertFalse(self.agent().exists())
        self.assertEqual(unrelated.read_text(), 'personal ruby agent')

    def test_empty_category_uninstall_is_harmless(self):
        self.run_cli('--uninstall', '--category', 'voltagent-lang')
        self.assertFalse(self.target.exists())

    def test_rejects_multiline_selection_without_partial_install(self):
        self.run_cli('--install', 'python-specialist\n,code-reviewer', success=False)
        self.assertFalse(self.target.exists())

    def test_identical_unmanaged_file_requires_explicit_adoption(self):
        self.target.mkdir()
        original = ROOT / 'categories/02-language-specialists/agents/python-specialist.md'
        shutil.copyfile(original, self.agent())
        result = self.install(success=False)
        self.assertIn('unmanaged', result.stderr)
        self.assertFalse((self.target / '.voltagent-state').exists())
        self.run_cli('--install', 'python-specialist', '--force')
        backups = list((self.target / '.voltagent-backups').glob('*/python-specialist.md'))
        self.assertEqual(backups[0].read_bytes(), original.read_bytes())

    def test_existing_target_lock_blocks_install_and_uninstall(self):
        self.install()
        lock = self.target / '.voltagent-lock'
        lock.mkdir()
        (lock / 'pid').write_text('123')
        for args in (('--install', 'python-specialist'), ('--uninstall', 'python-specialist')):
            result = self.run_cli(*args, success=False)
            self.assertIn('Target is locked', result.stderr)
            self.assertTrue(self.agent().exists())
            self.assertEqual((lock / 'pid').read_text(), '123')

    def test_successful_writes_release_their_lock(self):
        self.install()
        self.assertFalse((self.target / '.voltagent-lock').exists())
        self.run_cli('--uninstall', 'python-specialist')
        self.assertFalse((self.target / '.voltagent-lock').exists())

    def test_dry_run_does_not_take_existing_lock(self):
        self.install()
        lock = self.target / '.voltagent-lock'
        lock.mkdir()
        self.run_cli('--install', 'python-specialist', '--dry-run')
        self.assertTrue(lock.is_dir())

    def test_file_created_during_download_is_not_overwritten(self):
        result = self.remote('--install', 'python-specialist', success=False,
                             changes={'MOCK_DURING_DOWNLOAD_EDIT': str(self.agent())})
        self.assertIn('unmanaged', result.stderr)
        self.assertEqual(self.agent().read_text(), 'created during download')
        self.assertFalse((self.target / '.voltagent-state').exists())
        self.assertFalse((self.target / '.voltagent-lock').exists())

    def test_corrupt_state_is_reported_and_never_overwritten(self):
        self.install()
        marker = self.target / '.voltagent-state/python-specialist'
        marker.write_text('not a checksum')
        for args in (('--installed',), ('--install', 'python-specialist'), ('--uninstall', 'python-specialist')):
            result = self.run_cli(*args, success=False)
            self.assertIn('Invalid installation record', result.stderr)
        self.assertEqual(marker.read_text(), 'not a checksum')
        self.assertTrue(self.agent().exists())

    def test_state_directory_cannot_be_a_regular_file(self):
        self.target.mkdir()
        (self.target / '.voltagent-state').write_text('personal file')
        result = self.install(success=False)
        self.assertIn('not a directory', result.stderr)
        self.assertEqual((self.target / '.voltagent-state').read_text(), 'personal file')

    def test_failed_atomic_rename_cleans_staged_files_and_lock(self):
        mock_bin = self.base / 'bin'
        mock_bin.mkdir()
        wrapper = mock_bin / 'mv'
        wrapper.write_text('#!/bin/sh\nexit 1\n')
        wrapper.chmod(0o755)
        env = {**self.env, 'PATH': str(mock_bin) + os.pathsep + self.env['PATH']}
        self.install(success=False, env=env)
        self.assertFalse(self.agent().exists())
        self.assertFalse(list(self.target.glob('.voltagent-agent.*')))
        self.assertFalse((self.target / '.voltagent-lock').exists())

    def test_missing_managed_file_can_be_uninstalled(self):
        self.install()
        self.agent().unlink()
        self.run_cli('--uninstall', 'python-specialist')
        self.assertFalse((self.target / '.voltagent-state/python-specialist').exists())

    def test_interactive_category_and_name_selection(self):
        # A real PTY catches menu/read issues not exercised by noninteractive flags.
        master, slave = pty.openpty()
        proc = subprocess.Popen(['/bin/bash', str(SCRIPT), '--target', str(self.target)],
                                cwd=self.base, env=self.env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        self.addCleanup(os.close, master)
        output = b''
        prompts = [(b'Category number,', b'2\n'), (b'Action:', b'i\n'),
                   (b'Agent names separated', b'python-specialist\n'), (b'[y/N]', b'y\n')]
        deadline = time.monotonic() + 15
        while proc.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try: output += os.read(master, 65536)
                except OSError: break
                if prompts and prompts[0][0] in output:
                    _, answer = prompts.pop(0)
                    os.write(master, answer)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        self.assertEqual(proc.returncode, 0, output.decode(errors='replace'))
        self.assertFalse(prompts, output.decode(errors='replace'))
        self.assertTrue(self.agent().is_file())


if __name__ == '__main__':
    unittest.main()
