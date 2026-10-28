#!/usr/bin/env python3
"""Validate source files, generated metadata, and local Markdown links."""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sync import ROOT, frontmatter, generated, inventory


class HTMLReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'href', 'src'} and value:
                self.targets.append(value)
            if key == 'id' and value:
                self.ids.add(value)


def references(file: Path) -> tuple[list[str], set[str]]:
    text = re.sub(r'```.*?```', '', file.read_text(), flags=re.DOTALL)
    parser = HTMLReferences()
    parser.feed(text)
    targets = re.findall(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)', text) + parser.targets
    ids = set(parser.ids)
    seen = {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, flags=re.MULTILINE):
        plain = re.sub(r'<[^>]*>|[`*_~]', '', heading).lower()
        slug = re.sub(r'[^\w -]', '', plain).replace(' ', '-')
        number = seen.get(slug, 0)
        seen[slug] = number + 1
        ids.add(slug if number == 0 else f'{slug}-{number}')
    return targets, ids


def validate(root: Path = ROOT) -> list[str]:
    errors = []
    try:
        config, records = inventory(root)
        expected = generated(root)
    except (ValueError, KeyError, OSError) as error:
        return [str(error)]
    for relative, content in expected.items():
        path = root / relative
        data = content if isinstance(content, bytes) else content.encode('utf-8')
        if not path.is_file() or path.read_bytes() != data:
            errors.append(f'Stale generated file: {relative}; run python3 tools/sync.py')
    market = json.loads(expected['.claude-plugin/marketplace.json'])
    for entry in market['plugins']:
        plugin_root = root / entry['source']
        manifest = json.loads(expected[f"{entry['source'][2:]}/.claude-plugin/plugin.json"])
        if manifest['name'] != entry['name']:
            errors.append(f"Plugin names differ: {entry['name']}")
        for file in (plugin_root / 'agents').glob('*.md'):
            if not file.is_file() or not file.resolve().is_relative_to(plugin_root.resolve()):
                errors.append(f'Plugin agent missing or outside root: {file}')
    installer_fields, installer_body = frontmatter(root / 'agent-installer.md')
    if installer_fields.get('name') != 'agent-installer' or '--standalone' not in installer_body:
        errors.append('Standalone agent installer is incomplete')
    expected_repo = config['repository']
    for relative in ('README.md', 'agent-installer.md', 'install-agents.sh'):
        if expected_repo not in (root / relative).read_text():
            errors.append(f'Repository identity is missing from {relative}')
    if not (root / 'LICENSE').read_text().startswith('MIT License\n'):
        errors.append('MIT license missing')
    bodies = {}
    for record in records:
        _, body = frontmatter(root / record['path'])
        if body in bodies:
            errors.append(f"Identical agent bodies: {record['path']} and {bodies[body]}")
        bodies[body] = record['path']
    for file in sorted(root.rglob('*.md')):
        if '.git' in file.parts:
            continue
        targets, _ = references(file)
        for target in targets:
            split = urlsplit(target.strip('<>'))
            if split.scheme or split.netloc:
                continue
            dest = (file.parent / unquote(split.path)).resolve() if split.path else file.resolve()
            if not dest.is_relative_to(root.resolve()) or not dest.exists():
                errors.append(f'{file.relative_to(root)}: broken or escaping local link {target}')
            elif split.fragment and dest.is_file() and dest.suffix in {'.md', '.svg'}:
                if unquote(split.fragment) not in references(dest)[1]:
                    errors.append(f'{file.relative_to(root)}: missing local anchor {target}')
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    _, records = inventory()
    print(f'Validated {len(records)} category agents, the standalone agent installer, 10 plugins, generated metadata, and local links.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
