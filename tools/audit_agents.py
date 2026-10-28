#!/usr/bin/env python3
"""Check reviewed-source coverage and render a traceable per-agent review index."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from sync import ROOT, frontmatter, inventory

MODES = {'analysis', 'research', 'documents', 'analysis-with-execution', 'implementation', 'coordination'}


def review_records(root: Path = ROOT) -> tuple[list[dict], list[str]]:
    _, agents = inventory(root)
    records = [json.loads(line) for line in (root / 'evals/cases.jsonl').read_text().splitlines() if line.strip()]
    names = [entry['agent'] for entry in records]
    expected = {agent['name']: agent for agent in agents}
    errors = []
    if len(names) != len(set(names)):
        errors.append('Duplicate per-agent review records')
    if set(names) != set(expected):
        errors.append(f'Review coverage differs: missing={sorted(set(expected) - set(names))}; unknown={sorted(set(names) - set(expected))}')
    for entry in records:
        name = entry['agent']
        if name not in expected:
            continue
        agent = expected[name]
        fields, body = frontmatter(root / agent['path'])
        tools = set(fields['tools'].split(', '))
        if hashlib.sha256((root / agent['path']).read_bytes()).hexdigest() != entry['sha256']:
            errors.append(f'{name}: source changed since the recorded definition review')
        if entry['category'] != agent['directory'] or entry['mode'] not in MODES:
            errors.append(f'{name}: invalid review category or profile')
        if entry.get('review_status') != 'definition-reviewed' or entry.get('execution_status') != 'not-run':
            errors.append(f'{name}: illustrative review records must not claim runtime results')
        for key in ('request', 'expected', 'scope'):
            if not isinstance(entry.get(key), str) or len(entry[key]) < 30 or entry[key] not in body:
                errors.append(f'{name}: missing or stale {key} review context')
        if entry['mode'] in {'analysis', 'research'} and tools & {'Bash', 'Write', 'Edit', 'Agent'}:
            errors.append(f'{name}: inspection profile includes execution, writes, or delegation')
        if entry['mode'] == 'documents' and tools & {'Bash', 'Agent'}:
            errors.append(f'{name}: documents profile includes shell execution or delegation')
        if ('Agent' in tools) != (entry['mode'] == 'coordination'):
            errors.append(f'{name}: delegation does not match coordination profile')
    return records, errors


def report(root: Path = ROOT) -> str:
    records, errors = review_records(root)
    if errors:
        raise ValueError('\n'.join(errors))
    _, agents = inventory(root)
    paths = {agent['name']: agent['path'] for agent in agents}
    counts = Counter(entry['mode'] for entry in records)
    lines = ['# Per-agent source review', '',
             'This index records a source-level review of every category definition. Each record names an illustrative task, the expected result, the tool profile, and the reviewed source digest. The review checked routing, task specificity, verification instructions, scope, and vendor neutrality. It is not a runtime score or an independent security certification.', '',
             'The examples also appear in their agent definitions. They are not held-out evaluation cases. No end-to-end model execution is claimed for this case set. Installation, discovery, and installer behavior are exercised separately; see the [release audit](AUDIT.md).', '',
             'Run `python3 tools/audit_agents.py --check` from the repository root to verify coverage and source digests. A source edit invalidates its review record until its request, expected behavior, scope, and tools have been reviewed again. Update that record deliberately; do not automatically advance its digest merely to pass CI.', '',
             '## Tool profiles', '', '| Profile | Definitions |', '| :-- | --: |']
    for mode, count in sorted(counts.items()):
        lines.append(f'| {mode} | {count} |')
    lines.extend(['', 'Bash can change files and contact services. Delegation can launch other tool-bearing agents. Only the analysis and research profiles exclude shell execution, direct writes, and delegation. See [profile definitions](USAGE.md#tool-profiles).', ''])
    for category in sorted({entry['category'] for entry in records}):
        lines.extend([f'## {category}', '', '| Definition | Tool profile | Reviewed task and expected result | Source digest |', '| :-- | :-- | :-- | :-- |'])
        for entry in sorted((r for r in records if r['category'] == category), key=lambda r: r['agent']):
            name = entry['agent']
            request = entry['request'].replace('|', '\\|')
            expected = entry['expected'].replace('|', '\\|')
            lines.append(f"| [{name}](../{paths[name]}) | {entry['mode']} | **Task:** {request}<br>**Check:** {expected} | `{entry['sha256'][:12]}` |")
        lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check the report without writing')
    args = parser.parse_args()
    try:
        records, errors = review_records()
        if errors:
            raise ValueError('\n'.join(errors))
        content = report()
        path = ROOT / 'docs/AGENT_REVIEW.md'
        if args.check:
            if not path.is_file() or path.read_text() != content:
                raise ValueError('Per-agent review report is stale; run python3 tools/audit_agents.py')
        else:
            path.write_text(content)
        print(f'Review coverage verified for {len(records)} definitions. These records do not claim model execution.')
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
