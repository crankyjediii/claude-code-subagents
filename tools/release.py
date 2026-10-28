#!/usr/bin/env python3
"""Build deterministic release assets from one committed Git tree."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def snapshot(archive: bytes) -> dict[str, tuple[bytes, int]]:
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError(f'Unsafe archive path: {member.name}')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f'Release sources must be regular files: {member.name}')
            if member.name in files:
                raise ValueError(f'Duplicate source: {member.name}')
            files[member.name] = (source.extractfile(member).read(), member.mode & 0o777)
    return files


def zip_bytes(files: dict[str, tuple[bytes, int]], prefix: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, (data, mode) in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return output.getvalue()


def tar_gz_bytes(files: dict[str, tuple[bytes, int]], prefix: str) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for name, (data, mode) in sorted(files.items()):
            info = tarfile.TarInfo(prefix + name)
            info.size, info.mode, info.mtime = len(data), mode, 0
            archive.addfile(info, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, filename='', mode='wb', compresslevel=9, mtime=0) as stream:
        stream.write(raw.getvalue())
    return compressed.getvalue()


def build(archive: bytes, revision: str, tag: str | None = None) -> dict[str, bytes]:
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('A full Git commit hash is required')
    files = snapshot(archive)
    config = json.loads(files['collection.json'][0])
    version = config['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', version):
        raise ValueError('Invalid release version')
    expected_tag = f'v{version}'
    if tag is not None and tag != expected_tag:
        raise ValueError(f'Tag {tag} does not match collection version {expected_tag}')
    license_data = files['LICENSE'][0]
    if not license_data.startswith(b'MIT License\n'):
        raise ValueError('MIT license is missing')
    prefix = f'claude-code-subagents-{version}'
    artifacts = {
        f'{prefix}.zip': zip_bytes(files, prefix + '/'),
        f'{prefix}.tar.gz': tar_gz_bytes(files, prefix + '/'),
    }
    categories = []
    seen_plugins = set()
    for category in config['categories']:
        directory, plugin = category['directory'], category['plugin']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', plugin) or plugin in seen_plugins:
            raise ValueError('Invalid or duplicate plugin name')
        seen_plugins.add(plugin)
        source_prefix = f'categories/{directory}/'
        contents = {name[len(source_prefix):]: value for name, value in files.items() if name.startswith(source_prefix)}
        if contents.get('LICENSE', (b'', 0))[0] != license_data:
            raise ValueError(f'{plugin}: distributed license is missing or stale')
        manifest = json.loads(contents['.claude-plugin/plugin.json'][0])
        if manifest['name'] != plugin or manifest['version'] != version:
            raise ValueError(f'{plugin}: manifest name or version differs')
        agents = sorted(name for name in contents if name.startswith('agents/') and name.endswith('.md'))
        if not agents:
            raise ValueError(f'{plugin}: no definitions')
        filename = f'{plugin}-{version}.zip'
        artifacts[filename] = zip_bytes(contents, plugin + '/')
        categories.append({'plugin': plugin, 'directory': directory, 'agents': len(agents), 'asset': filename})
    installer = files['install-agents.sh'][0]
    if installer.count(b"REF='main'") != 1:
        raise ValueError('Expected one installer default ref to pin')
    artifacts['install-agents.sh'] = installer.replace(b"REF='main'", f"REF='{revision}'".encode(), 1)
    metadata = {'version': version, 'tag': expected_tag, 'commit': revision,
                'repository': config['repository'], 'agent_count': sum(c['agents'] for c in categories),
                'categories': categories, 'source_prefix': prefix,
                'installer_default_ref': revision, 'validation': config['validation'],
                'artifacts': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(artifacts.items())}}
    artifacts['release-manifest.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    artifacts['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                    for name, data in sorted(artifacts.items())).encode()
    return artifacts


def notes(archive: bytes, revision: str) -> str:
    files = snapshot(archive)
    config = json.loads(files['collection.json'][0])
    version, repo = config['version'], config['repository']
    count = sum('/agents/' in name and name.endswith('.md') for name in files)
    changelog = files['CHANGELOG.md'][0].decode()
    heading = f'## {version}\n'
    if heading not in changelog:
        raise ValueError('Release changelog section is missing')
    changes = changelog.split(heading, 1)[1].split('\n## ', 1)[0].strip()
    return f'''{count} standalone development agents across {len(config['categories'])} category plugins, distributed under MIT.

{changes}

### Install

```sh
claude plugin marketplace add {repo}
claude plugin install voltagent-core-dev@voltagent-subagents
```

The attached `install-agents.sh` defaults to commit `{revision}`. Download and review it, then run `bash install-agents.sh`. Source ZIP and tar archives contain the full repository; the ten plugin ZIPs can be extracted and loaded locally with Claude Code. Every plugin includes its MIT license.

`SHA256SUMS` covers all attached assets except itself. `release-manifest.json` records the source commit, counts, and artifact digests. Verify downloaded assets with `sha256sum -c SHA256SUMS` on Linux or `shasum -a 256 -c SHA256SUMS` on macOS after downloading the complete set.

The release gate verifies the exact archives and all category plugin inventories. Installer tests run on Linux and macOS. The per-agent records are source reviews and illustrative tasks, not executed model benchmarks.
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD', help='Committed source revision')
    parser.add_argument('--tag', help='Require this tag to match the collection version')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--notes', action='store_true', help='Print version-specific release notes instead')
    args = parser.parse_args()
    try:
        revision = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', args.ref + '^{commit}'], cwd=ROOT, text=True).strip()
        if args.ref == 'HEAD' and not args.notes and subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
            raise ValueError('Commit source changes before building HEAD release assets')
        archive = subprocess.check_output(['git', 'archive', '--format=tar', revision], cwd=ROOT)
        if args.notes:
            print(notes(archive, revision))
            return 0
        artifacts = build(archive, revision, args.tag)
        args.output.mkdir(parents=True, exist_ok=True)
        if any(args.output.iterdir()):
            raise ValueError('Output directory must be empty; use a fresh directory')
        for name, data in artifacts.items():
            path = args.output / name
            path.write_bytes(data)
            path.chmod(0o755 if name == 'install-agents.sh' else 0o644)
        print(f'Built {len(artifacts)} assets from {revision} in {args.output}')
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f'Release build failed: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
