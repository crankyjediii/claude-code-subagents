#!/usr/bin/env python3
"""Generate distribution metadata from category Markdown. No third-party imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from branding import assets

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
START, END = '<!-- catalog:start -->', '<!-- catalog:end -->'


def frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n') or '\n---\n' not in text[4:]:
        raise ValueError(f'{path}: missing YAML frontmatter')
    header, body = text[4:].split('\n---\n', 1)
    fields = {}
    # This repository deliberately uses a small YAML subset; JSON-quoted values
    # allow colons, Unicode, and escapes without a runtime YAML dependency.
    for line in header.splitlines():
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition(': ')
        if not sep or key in fields or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', key):
            raise ValueError(f'{path}: invalid or duplicate frontmatter field {line!r}')
        if value.startswith('"'):
            value = json.loads(value)
        elif ': ' in value or ' #' in value or value.startswith(('>', '|', "'", '[', '{')):
            raise ValueError(f'{path}: use a JSON-quoted scalar for {key}')
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{path}: empty or non-string {key}')
        fields[key] = value
    return fields, body


def inventory(root: Path = ROOT) -> tuple[dict, list[dict]]:
    config = json.loads((root / 'collection.json').read_text())
    categories = config['categories']
    if len(categories) != 10:
        raise ValueError('Exactly 10 categories are required')
    if config['branch'] != 'main' or not re.fullmatch(r'[\w.-]+/[\w.-]+', config['repository']):
        raise ValueError('Invalid repository configuration')
    found = {p.name for p in (root / 'categories').iterdir() if p.is_dir()}
    expected = {c['directory'] for c in categories}
    if found != expected or len(expected) != 10:
        raise ValueError('Category configuration and folders differ')
    names, plugins, records = set(), set(), []
    for number, category in enumerate(categories, 1):
        folder, plugin = category['directory'], category['plugin']
        if not folder.startswith(f'{number:02}-') or not SLUG.fullmatch(folder):
            raise ValueError(f'Invalid category ordering: {folder}')
        if not SLUG.fullmatch(plugin) or plugin in plugins:
            raise ValueError(f'Invalid or duplicate plugin: {plugin}')
        plugins.add(plugin)
        category_root = root / 'categories' / folder
        agents_root = category_root / 'agents'
        if category_root.is_symlink() or agents_root.is_symlink():
            raise ValueError(f'Category and agent directories may not be symlinks: {folder}')
        files = sorted(agents_root.glob('*.md'))
        if set(agents_root.rglob('*.md')) != set(files):
            raise ValueError(f'Nested agent definitions are not supported by the flat catalog: {folder}')
        if any(path.name != 'README.md' for path in category_root.glob('*.md')):
            raise ValueError(f'Agent definition outside agents directory: {folder}')
        if not files:
            raise ValueError(f'Empty category: {folder}')
        for path in files:
            if path.is_symlink():
                raise ValueError(f'Agent may not be a symlink: {path}')
            fields, body = frontmatter(path)
            name, description = fields.get('name', ''), fields.get('description', '')
            if name != path.stem or not SLUG.fullmatch(name) or name in names:
                raise ValueError(f'Invalid or duplicate agent name: {path}')
            if not 20 <= len(description) <= 240 or any(c in description for c in '|\n\r'):
                raise ValueError(f'Invalid routing description: {path}')
            if set(fields) != {'name', 'description', 'tools', 'model'} or fields['model'] != 'inherit':
                raise ValueError(f'Unsupported frontmatter: {path}')
            tools = fields['tools'].split(', ')
            allowed = {'Read', 'Glob', 'Grep', 'Bash', 'Write', 'Edit', 'Agent', 'WebFetch', 'WebSearch'}
            if not set(tools) <= allowed or len(tools) != len(set(tools)):
                raise ValueError(f'Unknown or duplicate tools: {path}')
            if len(body.split()) < 160 or any(h not in body for h in ('## Scope and tool use', '## Approach', '## Task boundaries', '## Example task', '## Completion')):
                raise ValueError(f'Incomplete agent instructions: {path}')
            if re.search(r'\b(TODO|FIXME|PLACEHOLDER)\b', body):
                raise ValueError(f'Unfinished agent: {path}')
            names.add(name)
            records.append({**category, 'name': name, 'description': description,
                            'path': path.relative_to(root).as_posix(),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if len(records) < 161:
        raise ValueError(f'Expected at least 161 agents; found {len(records)}')
    return config, records


def encoded(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def generated(root: Path = ROOT) -> dict[str, str | bytes]:
    config, records = inventory(root)
    repo_url = f"https://github.com/{config['repository']}"
    outputs = {}
    entries, index = [], []
    index.extend(['| Category | Plugin | Agents |', '| :-- | :-- | --: |'])
    for category in config['categories']:
        group = [r for r in records if r['directory'] == category['directory']]
        number = category['directory'][:2]
        index.append(f"| [{number} · {category['title']}](categories/{category['directory']}/README.md) | `{category['plugin']}` | {len(group)} |")
    index.extend(['', 'Expand a category to browse its agents.', ''])
    catalog = []
    for category in config['categories']:
        group = [r for r in records if r['directory'] == category['directory']]
        folder, plugin, title = category['directory'], category['plugin'], category['title']
        manifest = {'name': plugin, 'version': config['version'],
                    'description': f'{title}: {len(group)} task-focused Claude Code agents.',
                    'author': {'name': 'Collection contributors'},
                    'repository': repo_url, 'homepage': repo_url, 'license': 'MIT',
                    'keywords': ['claude-code', 'subagents', folder[3:]]}
        outputs[f'categories/{folder}/.claude-plugin/plugin.json'] = encoded(manifest)
        outputs[f'categories/{folder}/LICENSE'] = (root / 'LICENSE').read_text()
        entries.append({'name': plugin, 'source': f'./categories/{folder}',
                        'description': manifest['description']})
        note = ''
        if plugin == 'voltagent-meta':
            note = ('\nThese orchestration agents work best with specialists from other categories installed. '
                    'They discover available agents and provide a sequential fallback when delegation is unavailable.\n')
        cat_lines = [f'# {title}', '', f'Plugin: `{plugin}` · {len(group)} agents', note,
                     '```sh', f"claude plugin install {plugin}@{config['marketplace']}", '```', '']
        index.extend(['<details>', f'<summary><strong>{folder[:2]} · {title}</strong> · {len(group)} agents</summary>', '',
                      f'Plugin: `{plugin}` · [Category guide](categories/{folder}/README.md)', ''])
        for r in group:
            description = r['description'].removeprefix('Use when you need to ')
            description = description[0].upper() + description[1:]
            cat_lines.append(f"- [{r['name']}](agents/{r['name']}.md): {description}")
            index.append(f"- [{r['name']}]({r['path']}): {description}")
            catalog.append('|'.join(str(r[k]) for k in ('directory', 'plugin', 'name', 'description', 'path', 'sha256')))
        index.extend(['', '</details>', ''])
        outputs[f'categories/{folder}/README.md'] = '\n'.join(cat_lines).rstrip() + '\n'
    outputs['.claude-plugin/marketplace.json'] = encoded({
        'name': config['marketplace'], 'owner': {'name': 'Collection contributors'},
        'metadata': {'description': f"{len(records)} development subagents in 10 category plugins.",
                     'version': config['version']}, 'plugins': entries})
    outputs['tools/catalog.tsv'] = '\n'.join(catalog) + '\n'
    count = len(records)
    outputs.update(assets(count, config['categories']))
    outputs['docs/agent-count.svg'] = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="146" height="20" role="img" aria-label="subagents: {count}">'
        '<title>Subagent count</title><rect width="100" height="20" fill="#394150"/>'
        '<rect x="100" width="46" height="20" fill="#23734d"/>'
        '<g fill="white" text-anchor="middle" font-family="Verdana,sans-serif" font-size="11">'
        f'<text x="50" y="14">subagents</text><text x="123" y="14">{count}</text></g></svg>\n')
    readme = (root / 'README.md').read_text()
    readme = re.sub(r'^\d+ standalone development agents in \d+ categories\.',
                    f'{len(records)} standalone development agents in {len(config["categories"])} categories.',
                    readme, count=1, flags=re.MULTILINE)
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError('README needs exactly one catalog marker pair')
    before, rest = readme.split(START)
    _, after = rest.split(END)
    outputs['README.md'] = before + START + '\n\n' + '\n'.join(index).rstrip() + '\n\n' + END + after
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report drift without changing files')
    args = parser.parse_args()
    try:
        outputs = generated()
        changed = []
        for relative, content in outputs.items():
            path = ROOT / relative
            data = content if isinstance(content, bytes) else content.encode('utf-8')
            if not path.exists() or path.read_bytes() != data:
                changed.append(relative)
                if not args.check:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
        if changed and args.check:
            print('Generated files are stale. Run python3 tools/sync.py:\n' + '\n'.join(changed), file=sys.stderr)
            return 1
        _, agents = inventory()
        print(f"{'Checked' if args.check else 'Synchronized'} {len(agents)} agents, 10 plugins; {len(changed)} changed files.")
        return 0
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f'Collection error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
