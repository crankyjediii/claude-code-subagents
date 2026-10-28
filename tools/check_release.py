#!/usr/bin/env python3
"""Verify checksums, extracted source behavior, and packaged plugin discovery."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def verify_checksums(directory: Path) -> dict:
    records = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, separator, name = line.partition('  ')
        if not separator or not re.fullmatch(r'[0-9a-f]{64}', digest) or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in records:
            raise ValueError('Invalid or duplicate checksum record')
        file = directory / name
        if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Checksum mismatch: {name}')
        records[name] = digest
    actual = {path.name for path in directory.iterdir()}
    if actual != set(records) | {'SHA256SUMS'}:
        raise ValueError('Asset directory and checksum list differ')
    manifest = json.loads((directory / 'release-manifest.json').read_text())
    if not re.fullmatch(r'[0-9a-f]{40}', manifest['commit']) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', manifest['version']):
        raise ValueError('Invalid release identity')
    if manifest['tag'] != 'v' + manifest['version'] or manifest['source_prefix'] != 'claude-code-subagents-' + manifest['version']:
        raise ValueError('Release tag, version, and source prefix differ')
    for category in manifest['categories']:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', category['plugin']) or not re.fullmatch(r'\d{2}-[a-z0-9-]+', category['directory']):
            raise ValueError('Invalid release category')
        if category['asset'] != f"{category['plugin']}-{manifest['version']}.zip":
            raise ValueError('Invalid category asset name')
    if manifest['artifacts'] != {key: value for key, value in records.items() if key != 'release-manifest.json'}:
        raise ValueError('Manifest and checksum list differ')
    installer = (directory / 'install-agents.sh').read_text()
    if f"REF='{manifest['commit']}'" not in installer or manifest['installer_default_ref'] != manifest['commit']:
        raise ValueError('Release installer is not pinned to the recorded commit')
    return manifest


def extract(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(mode):
                raise ValueError(f'Unsafe ZIP member: {member.filename}')
        archive.extractall(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--online', action='store_true', help='Also install using the commit-pinned downloadable installer')
    args = parser.parse_args()
    directory = args.directory.resolve()
    manifest = verify_checksums(directory)
    with tempfile.TemporaryDirectory(prefix='release-check-') as temporary:
        area = Path(temporary)
        extract(directory / f"{manifest['source_prefix']}.zip", area)
        root = area / manifest['source_prefix']
        zip_files = {f"{manifest['source_prefix']}/{path.relative_to(root).as_posix()}": path.read_bytes() for path in root.rglob('*') if path.is_file()}
        with tarfile.open(directory / f"{manifest['source_prefix']}.tar.gz") as archive:
            tar_files = {}
            for member in archive.getmembers():
                if not member.isfile() or PurePosixPath(member.name).is_absolute() or '..' in PurePosixPath(member.name).parts:
                    raise ValueError('Unsafe source tar archive')
                tar_files[member.name] = archive.extractfile(member).read()
            if tar_files != zip_files:
                raise ValueError('Source ZIP and tar contents differ')

        def run(command: list[str], cwd: Path, env=None) -> str:
            result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=120)
            if result.returncode:
                raise RuntimeError(f'{command} failed:\n{result.stdout}\n{result.stderr}')
            return result.stdout

        run([sys.executable, 'tools/validate.py'], root)
        run([sys.executable, 'tools/audit_agents.py', '--check'], root)
        target = area / 'installed'
        for action in (['--install', 'python-specialist,code-reviewer'], ['--uninstall', '--category', 'voltagent-lang'], ['--uninstall', '--all']):
            run(['bash', 'install-agents.sh', '--local', str(root), '--target', str(target), *action], root)
        if list(target.glob('*.md')) or (target / '.voltagent-lock').exists():
            raise ValueError('Extracted source install/uninstall did not clean up')
        if args.online:
            remote = area / 'remote-install'
            for action in (['--install', 'python-specialist'], ['--uninstall', '--all']):
                run(['bash', str(directory / 'install-agents.sh'), '--standalone', '--target', str(remote), *action], area)
            if list(remote.glob('*.md')) or (remote / '.voltagent-lock').exists():
                raise ValueError('Pinned downloadable installer did not clean up')
        plugin_root = area / 'plugins'
        plugin_root.mkdir()
        entries = []
        for category in manifest['categories']:
            extract(directory / category['asset'], plugin_root)
            plugin = category['plugin']
            packaged = plugin_root / plugin
            if (packaged / 'LICENSE').read_bytes() != (root / 'LICENSE').read_bytes():
                raise ValueError(f'{plugin}: license not distributed')
            agents = {path.name: path.read_bytes() for path in (packaged / 'agents').glob('*.md')}
            original = {path.name: path.read_bytes() for path in (root / 'categories' / category['directory'] / 'agents').glob('*.md')}
            if agents != original or len(agents) != category['agents']:
                raise ValueError(f'{plugin}: packaged definitions differ from source')
            entries.append({'name': plugin, 'source': f'./{plugin}'})
        config_dir = plugin_root / '.claude-plugin'
        config_dir.mkdir()
        (config_dir / 'marketplace.json').write_text(json.dumps({'name': 'release-artifact-check', 'owner': {'name': 'Contributors'}, 'plugins': entries}))
        env = {**os.environ, 'CLAUDE_CONFIG_DIR': str(area / 'claude-config')}
        run(['claude', 'plugin', 'marketplace', 'add', str(plugin_root)], area, env)
        for category in manifest['categories']:
            plugin = category['plugin']
            run(['claude', 'plugin', 'validate', '--strict', '--profile', 'directory', str(plugin_root / plugin)], area, env)
            run(['claude', 'plugin', 'install', f'{plugin}@release-artifact-check'], area, env)
            details = run(['claude', 'plugin', 'details', plugin], area, env)
            found = re.search(r'Agents \((\d+)\)', details)
            if not found or int(found.group(1)) != category['agents'] or manifest['version'] not in details:
                raise ValueError(f'{plugin}: extracted artifact discovery or version differs')
        print(f"Verified {manifest['tag']}: {manifest['agent_count']} agents, {len(entries)} packaged plugins, all checksums, and extracted source installation.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
